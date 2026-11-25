#!/usr/bin/env python3
"""Validate a Google Merchant Center product feed (CSV, TSV or RSS/Atom XML). Read-only.

Checks every item for the problems that get products disapproved or limited:
required attributes, GTIN length and check digit, price and sale_price format,
availability values, image and landing page URLs, title and description length,
duplicate ids, identifier_exists conflicts and promotional text in titles.

Exit codes: 0 = no findings at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

REQUIRED = ["id", "title", "description", "link", "image_link", "availability", "price"]
AVAILABILITY = {"in_stock", "out_of_stock", "preorder", "backorder"}
CONDITIONS = {"new", "refurbished", "used"}
IMAGE_EXT_OK = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"}
PRICE_RE = re.compile(r"^(\d+(?:\.\d{1,2})?)\s+([A-Z]{3})$")
PROMO_RE = re.compile(
    r"(free shipping|free delivery|\bsale\b|best price|cheapest|buy now|limited time|"
    r"\d+\s?% off|discount|\bdeal\b|clearance)",
    re.I,
)
PLACEHOLDER_RE = re.compile(r"(placeholder|no[-_]?image|noimage|default[-_]image|coming[-_]soon)", re.I)
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
LIMITS = {"id": 50, "title": 150, "description": 5000}


def norm_key(key: str) -> str:
    key = key.strip().lower()
    if key.startswith("g:"):
        key = key[2:]
    return re.sub(r"[\s-]+", "_", key)


def gtin_check(value: str) -> str | None:
    """Return None when value is a valid GTIN-8/12/13/14, else a reason."""
    digits = value.strip()
    if not digits.isdigit():
        return "contains characters other than digits"
    if len(digits) not in (8, 12, 13, 14):
        return f"has {len(digits)} digits (expected 8, 12, 13 or 14)"
    if set(digits) == {"0"}:
        return "is all zeros"
    body, check = digits[:-1], int(digits[-1])
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    expected = (10 - total % 10) % 10
    if expected != check:
        return f"check digit is {check}, expected {expected}"
    return None


def gtin_restricted(value: str) -> bool:
    """GS1 restricted-circulation / coupon prefixes that Google rejects."""
    g13 = value.zfill(14)[1:] if len(value) == 14 else value.zfill(13)
    return g13.startswith(("02", "04", "2", "98", "99")) and not g13.startswith(("978", "979"))


def parse_price(value: str):
    m = PRICE_RE.match(value.strip())
    if not m:
        return None
    return float(m.group(1)), m.group(2)


def read_items(path: str) -> tuple[list[dict], str]:
    if path == "-":
        raw = sys.stdin.buffer.read()
    else:
        with open(path, "rb") as fh:
            raw = fh.read()
    text = raw.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return read_xml(text), "xml"
    return read_delimited(text), "csv"


def read_delimited(text: str) -> list[dict]:
    first = text.splitlines()[0] if text else ""
    delimiter = "\t" if first.count("\t") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []
    header = [norm_key(h) for h in rows[0]]
    items = []
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        item: dict = {"_line": line_no}
        for key, value in zip(header, row):
            if not key:
                continue
            if key in item and value.strip():
                item[key] = f"{item[key]},{value.strip()}"
            elif key not in item:
                item[key] = value.strip()
        items.append(item)
    return items


def read_xml(text: str) -> list[dict]:
    if "<!ENTITY" in text:
        raise ValueError("XML feed declares entities; refusing to parse")
    root = ET.fromstring(text)
    items = []
    for n, node in enumerate(el for el in root.iter() if local(el.tag) in ("item", "entry")):
        item: dict = {"_line": f"item {n + 1}"}
        for child in node:
            key = norm_key(local(child.tag))
            if len(child):
                value = "present"
            elif key == "link" and child.get("href"):
                value = child.get("href", "")
            else:
                value = (child.text or "").strip()
            if key in item and value:
                item[key] = f"{item[key]},{value}"
            else:
                item[key] = value
        items.append(item)
    return items


def local(tag) -> str:
    tag = str(tag)
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def check_url(item, key, value, add, image=False):
    for url in [u.strip() for u in value.split(",") if u.strip()] if image else [value]:
        if not re.match(r"^https?://[^\s/]+\.[^\s/]+", url):
            add("error", f"{key}_invalid", f"{key} is not an absolute http(s) URL: {url[:80]}")
            continue
        if url.startswith("http://"):
            add("warning", f"{key}_http", f"{key} uses http://; use https://", "Serve over HTTPS")
        if image:
            if PLACEHOLDER_RE.search(url):
                add("error", "image_placeholder", f"{key} looks like a placeholder image: {url[:80]}")
            ext = url.split("?", 1)[0].rsplit(".", 1)[-1].lower() if "." in url.rsplit("/", 1)[-1] else ""
            if ext == "svg":
                add("error", "image_svg", f"{key} is SVG, which Merchant Center does not accept")
            elif ext and ext not in IMAGE_EXT_OK and len(ext) <= 5:
                add("warning", "image_format", f"{key} has unusual extension .{ext}")


def check_item(item: dict, opts) -> list[dict]:
    out: list[dict] = []
    ident = item.get("id") or f"(line {item['_line']})"

    def add(sev, code, message, fix=""):
        out.append(
            {
                "severity": sev,
                "code": code,
                "item": ident,
                "line": item["_line"],
                "message": message,
                "fix": fix,
            }
        )

    for key in REQUIRED:
        if not item.get(key):
            add("error", f"missing_{key}", f"missing required attribute {key}", f"Add {key} to every item")

    for key, limit in LIMITS.items():
        value = item.get(key, "")
        if len(value) > limit:
            add("error", f"{key}_too_long", f"{key} is {len(value)} characters (max {limit})")

    title = item.get("title", "")
    if title:
        if len(title) < opts.min_title:
            add(
                "warning",
                "title_short",
                f"title is only {len(title)} characters",
                "Add brand, product type and key attributes (size, colour, material)",
            )
        letters = [c for c in title if c.isalpha()]
        if len(letters) >= 10 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
            add("warning", "title_caps", "title is mostly capital letters", "Use normal capitalisation")
        promo = PROMO_RE.search(title)
        if promo:
            add(
                "warning",
                "title_promo",
                f"title contains promotional text '{promo.group(0)}'",
                "Move promotions to sale_price or Promotions",
            )

    desc = item.get("description", "")
    if desc:
        if title and desc.strip().lower() == title.strip().lower():
            add("warning", "description_is_title", "description is identical to the title")
        elif len(desc) < 50:
            add("warning", "description_short", f"description is only {len(desc)} characters")
        if re.search(r"<[a-z][^>]*>", desc, re.I):
            add("info", "description_html", "description contains HTML tags (stripped by Google)")

    if item.get("link"):
        check_url(item, "link", item["link"], add)
    if item.get("mobile_link"):
        check_url(item, "mobile_link", item["mobile_link"], add)
    if item.get("image_link"):
        check_url(item, "image_link", item["image_link"], add, image=True)
    extra = item.get("additional_image_link", "")
    if extra:
        check_url(item, "additional_image_link", extra, add, image=True)
        if len([u for u in extra.split(",") if u.strip()]) > 10:
            add("warning", "too_many_images", "more than 10 additional_image_link values")

    avail = item.get("availability", "")
    if avail:
        normalised = avail.strip().lower().replace(" ", "_")
        if normalised not in AVAILABILITY:
            add(
                "error",
                "availability_invalid",
                f"availability '{avail}' is not one of {sorted(AVAILABILITY)}",
            )
        elif normalised != avail:
            add("warning", "availability_format", f"availability '{avail}' should be written '{normalised}'")
        if normalised in ("preorder", "backorder") and not item.get("availability_date"):
            add("error", "missing_availability_date", f"{normalised} items need availability_date")

    currencies = []
    price = None
    if item.get("price"):
        parsed = parse_price(item["price"])
        if not parsed:
            add(
                "error",
                "price_format",
                f"price '{item['price']}' must look like '15.00 USD' (number, space, ISO 4217 code)",
            )
        else:
            price, cur = parsed
            currencies.append(cur)
            if price <= 0:
                add("error", "price_zero", "price must be greater than 0")
    if item.get("sale_price"):
        parsed = parse_price(item["sale_price"])
        if not parsed:
            add("error", "sale_price_format", f"sale_price '{item['sale_price']}' has an invalid format")
        else:
            sale, cur = parsed
            if currencies and cur != currencies[0]:
                add("error", "sale_price_currency", "sale_price currency differs from price currency")
            if price is not None and sale >= price:
                add(
                    "error",
                    "sale_price_not_lower",
                    f"sale_price {sale:.2f} is not lower than price {price:.2f}",
                )
    item["_currency"] = currencies[0] if currencies else None

    gtin = item.get("gtin", "")
    id_exists = item.get("identifier_exists", "").strip().lower()
    if gtin:
        cleaned = re.sub(r"[\s-]", "", gtin)
        if cleaned != gtin:
            add("warning", "gtin_formatting", "gtin contains spaces or hyphens", "Submit digits only")
        for value in [g for g in cleaned.split(",") if g]:
            reason = gtin_check(value)
            if reason:
                add("error", "gtin_invalid", f"gtin {value} {reason}", "Use the GTIN printed on the barcode")
            elif gtin_restricted(value):
                add("error", "gtin_restricted", f"gtin {value} uses a GS1 restricted-circulation prefix")
        if id_exists in ("no", "false"):
            add("warning", "identifier_conflict", "identifier_exists is 'no' but a gtin is set")
    elif id_exists not in ("no", "false"):
        if not item.get("mpn"):
            add(
                "warning",
                "missing_identifiers",
                "no gtin or mpn",
                "Add gtin, or brand + mpn, or identifier_exists=no for custom/handmade goods",
            )
        if not item.get("brand"):
            add("warning", "missing_brand", "no brand", "Add brand (your store name for own-label goods)")

    cond = item.get("condition", "").strip().lower()
    if cond and cond not in CONDITIONS:
        add("error", "condition_invalid", f"condition '{item['condition']}' is not new, refurbished or used")
    elif not cond:
        add("info", "missing_condition", "condition not set (Google assumes new)")
    if not item.get("google_product_category") and not item.get("product_type"):
        add("info", "missing_category", "no google_product_category or product_type")
    return out


def validate(items: list[dict], opts) -> dict:
    findings: list[dict] = []
    ids = Counter(i.get("id") for i in items if i.get("id"))
    for item in items:
        findings += check_item(item, opts)
        if item.get("id") and ids[item["id"]] > 1:
            findings.append(
                {
                    "severity": "error",
                    "code": "duplicate_id",
                    "item": item["id"],
                    "line": item["_line"],
                    "message": f"id '{item['id']}' appears {ids[item['id']]} times",
                    "fix": "Every item (including each variant) needs a unique id",
                }
            )
    currencies = Counter(i["_currency"] for i in items if i.get("_currency"))
    if len(currencies) > 1:
        findings.append(
            {
                "severity": "warning",
                "code": "mixed_currencies",
                "item": "(feed)",
                "line": "",
                "message": f"feed mixes currencies: {dict(currencies)}",
                "fix": "One feed per target country/currency",
            }
        )
    by_sev = Counter(f["severity"] for f in findings)
    by_code = Counter(f["code"] for f in findings)
    bad_items = {f["item"] for f in findings if f["severity"] == "error"}
    return {
        "items": len(items),
        "items_with_errors": len(bad_items),
        "counts": {s: by_sev.get(s, 0) for s in ("error", "warning", "info")},
        "by_code": dict(by_code.most_common()),
        "findings": findings,
    }


def print_text(report: dict, max_per_code: int) -> None:
    c = report["counts"]
    print(
        f"{report['items']} items, {report['items_with_errors']} with errors | "
        f"errors {c['error']}, warnings {c['warning']}, info {c['info']}"
    )
    grouped = defaultdict(list)
    for f in report["findings"]:
        grouped[(f["severity"], f["code"])].append(f)
    for (sev, code), group in sorted(
        grouped.items(), key=lambda kv: (-SEVERITY_ORDER[kv[0][0]], -len(kv[1]))
    ):
        print(f"\n[{sev.upper()}] {code} x{len(group)}")
        if group[0]["fix"]:
            print(f"  fix: {group[0]['fix']}")
        for f in group[:max_per_code]:
            print(f"  - {f['item']} ({f['line']}): {f['message']}")
        if len(group) > max_per_code:
            print(f"  ... {len(group) - max_per_code} more")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("feed", help="feed file (.csv, .tsv, .txt or .xml), or - for stdin")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--fail-on", choices=["error", "warning", "info"], default="error")
    p.add_argument("--min-title", type=int, default=25, help="warn below this title length (default 25)")
    p.add_argument("--max-per-code", type=int, default=5, help="examples shown per finding type")
    args = p.parse_args(argv)
    try:
        items, kind = read_items(args.feed)
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not items:
        print("error: no items found in feed", file=sys.stderr)
        return 2
    report = validate(items, args)
    report["format"] = kind
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report, args.max_per_code)
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f["severity"]] >= threshold for f in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
