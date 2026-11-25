#!/usr/bin/env python3
"""Generate and validate Product / Offer / AggregateRating JSON-LD for product pages.

  generate  build JSON-LD from a product JSON object/list or a CSV export
  validate  check JSON-LD in a .json file or every ld+json block in a saved .html page

Validation follows Google's product snippet and merchant listing requirements: name,
image, offers (price, priceCurrency, availability), AggregateOffer, AggregateRating and
Review fields, GTIN check digits, priceValidUntil dates and duplicate Product markup
(two plugins both printing schema). Read-only; network is never used.

Exit codes: 0 = valid (no errors), 1 = errors found, 2 = usage or input error.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys

SCHEMA = "https://schema.org/"
AVAILABILITY = {
    "in_stock": "InStock",
    "instock": "InStock",
    "out_of_stock": "OutOfStock",
    "outofstock": "OutOfStock",
    "preorder": "PreOrder",
    "backorder": "BackOrder",
    "onbackorder": "BackOrder",
    "discontinued": "Discontinued",
    "limited": "LimitedAvailability",
    "soldout": "SoldOut",
    "instoreonly": "InStoreOnly",
    "onlineonly": "OnlineOnly",
    "presale": "PreSale",
}
VALID_AVAILABILITY = set(AVAILABILITY.values()) | {"BackOrder", "PreOrder"}
CONDITION = {"new": "NewCondition", "used": "UsedCondition", "refurbished": "RefurbishedCondition"}
VALID_CONDITION = set(CONDITION.values()) | {"DamagedCondition"}
GTIN_KEYS = ("gtin", "gtin8", "gtin12", "gtin13", "gtin14", "isbn")
LD_RE = re.compile(r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
CSV_ALIASES = {
    "name": ["name", "title", "product name"],
    "description": ["description", "short description", "body (html)", "body_html"],
    "sku": ["sku", "variant sku"],
    "gtin": ["gtin", "barcode", "variant barcode", "gtin, upc, ean, or isbn", "ean", "upc"],
    "brand": ["brand", "vendor"],
    "image": ["image", "images", "image src", "image_link"],
    "url": ["url", "link", "permalink"],
    "price": ["price", "sale price", "variant price", "regular price"],
    "currency": ["currency", "pricecurrency"],
    "availability": ["availability", "stock status", "in stock?"],
    "condition": ["condition"],
    "rating_value": ["rating_value", "average rating", "rating"],
    "review_count": ["review_count", "review count", "reviews"],
    "price_valid_until": ["price_valid_until", "sale price dates to"],
}


# ---------------------------------------------------------------- helpers


def gtin_ok(value: str) -> bool:
    digits = str(value).strip()
    if not digits.isdigit() or len(digits) not in (8, 12, 13, 14) or set(digits) == {"0"}:
        return False
    total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == int(digits[-1])


def clean_price(value) -> str | None:
    """Return a schema.org price string ('1299.00') or None if it cannot be parsed."""
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"[^\d.,-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        text = (
            text.replace(",", "")
            if text.rfind(".") > text.rfind(",")
            else text.replace(".", "").replace(",", ".")
        )
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = head.replace(",", "") + ("." + tail if len(tail) <= 2 else tail)
    try:
        return f"{float(text):.2f}"
    except ValueError:
        return None


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def short_type(value) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    value = str(value or "")
    return value.rsplit("/", 1)[-1]


def types_of(node) -> set[str]:
    t = node.get("@type", [])
    return {short_type(x) for x in (t if isinstance(t, list) else [t])}


# ---------------------------------------------------------------- generate


def build_product(p: dict, default_currency: str = "") -> dict:
    name = p.get("name") or p.get("title")
    if not name:
        raise ValueError("product needs a name")
    data: dict = {"@context": "https://schema.org", "@type": "Product", "name": name}
    images = p.get("image") or p.get("images")
    if isinstance(images, str):
        images = [i.strip() for i in images.split(",") if i.strip()]
    if images:
        data["image"] = images
    if p.get("description"):
        data["description"] = strip_html(p["description"])[:5000]
    if p.get("sku"):
        data["sku"] = str(p["sku"])
    if p.get("mpn"):
        data["mpn"] = str(p["mpn"])
    gtin = str(p.get("gtin") or "").strip()
    if gtin:
        if not gtin_ok(gtin):
            raise ValueError(f"{name}: gtin {gtin} fails the check digit; fix it or leave it out")
        data["gtin"] = gtin
    if p.get("brand"):
        data["brand"] = {"@type": "Brand", "name": p["brand"]}
    if p.get("url"):
        data["url"] = p["url"]

    price = clean_price(p.get("price"))
    if price is not None:
        currency = (p.get("currency") or default_currency or "").upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError(f"{name}: price needs a 3-letter currency (use --currency)")
        avail_key = re.sub(r"[\s_-]", "", str(p.get("availability") or "in_stock").lower())
        avail_key = {"instock": "instock", "1": "instock", "yes": "instock", "0": "outofstock"}.get(
            avail_key, avail_key
        )
        offer: dict = {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": SCHEMA + AVAILABILITY.get(avail_key, "InStock"),
        }
        if p.get("url"):
            offer["url"] = p["url"]
        cond = str(p.get("condition") or "").lower()
        if cond in CONDITION:
            offer["itemCondition"] = SCHEMA + CONDITION[cond]
        if p.get("price_valid_until"):
            offer["priceValidUntil"] = str(p["price_valid_until"])[:10]
        if p.get("seller"):
            offer["seller"] = {"@type": "Organization", "name": p["seller"]}
        data["offers"] = offer

    rating, count = p.get("rating_value"), p.get("review_count")
    if rating not in (None, "") and count not in (None, "", "0", 0):
        try:
            rv, rc = float(rating), int(float(count))
        except ValueError as exc:
            raise ValueError(f"{name}: rating_value/review_count must be numbers") from exc
        if rc > 0 and rv > 0:
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": f"{rv:.1f}".rstrip("0").rstrip("."),
                "reviewCount": rc,
                "bestRating": str(p.get("best_rating") or 5),
                "worstRating": str(p.get("worst_rating") or 1),
            }
    return data


def rows_from_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        lookup = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
        rows = []
        for row in reader:
            item = {}
            for field, aliases in CSV_ALIASES.items():
                for alias in aliases:
                    if alias in lookup and (row.get(lookup[alias]) or "").strip():
                        item[field] = row[lookup[alias]].strip()
                        break
            if item.get("name"):
                rows.append(item)
        return rows


# ---------------------------------------------------------------- validate


def extract_nodes(doc) -> list[dict]:
    """Flatten @graph, lists and nested objects into Product-like nodes."""
    found: list[dict] = []

    def walk(node, top=False):
        if isinstance(node, list):
            for x in node:
                walk(x, top)
        elif isinstance(node, dict):
            if "@graph" in node:
                walk(node["@graph"], True)
            kinds = types_of(node)
            if "ProductGroup" in kinds:
                walk(node.get("hasVariant", []))
                return
            if kinds & {"Product", "IndividualProduct", "ProductModel"}:
                found.append(node)
                return
            for key, value in node.items():
                if key not in ("@graph", "offers", "review", "aggregateRating"):
                    walk(value)

    walk(doc, True)
    return found


def check_offer(offer: dict, where: str, add, today: dt.date) -> None:
    kind = types_of(offer)
    if "AggregateOffer" in kind:
        if offer.get("lowPrice") in (None, ""):
            add("error", f"{where}: AggregateOffer needs lowPrice")
        elif not _numeric(offer.get("lowPrice")):
            add("error", f"{where}: lowPrice '{offer.get('lowPrice')}' must be a plain number")
        if not offer.get("priceCurrency"):
            add("error", f"{where}: AggregateOffer needs priceCurrency")
        if not offer.get("offerCount"):
            add("info", f"{where}: AggregateOffer offerCount is recommended")
        return
    price = offer.get("price")
    spec = offer.get("priceSpecification")
    if price in (None, "") and isinstance(spec, dict):
        price = spec.get("price")
        offer = {**offer, "priceCurrency": offer.get("priceCurrency") or spec.get("priceCurrency")}
    if price in (None, ""):
        add("error", f"{where}: offer is missing price")
    elif not _numeric(price):
        add(
            "error",
            f"{where}: price '{price}' must be a number without currency symbols or thousands separators",
        )
    elif float(price) <= 0:
        add("warning", f"{where}: price is {price}; merchant listings need a price above 0")
    cur = offer.get("priceCurrency")
    if not cur:
        add("error", f"{where}: offer is missing priceCurrency")
    elif not re.fullmatch(r"[A-Z]{3}", str(cur)):
        add("error", f"{where}: priceCurrency '{cur}' must be an ISO 4217 code such as USD or BDT")
    avail = offer.get("availability")
    if not avail:
        add("warning", f"{where}: availability is recommended (https://schema.org/InStock)")
    else:
        short = short_type(avail)
        if short not in VALID_AVAILABILITY:
            add("error", f"{where}: availability '{avail}' is not a schema.org ItemAvailability value")
        elif not str(avail).startswith(("https://schema.org/", "http://schema.org/")):
            add("warning", f"{where}: write availability as the full URL https://schema.org/{short}")
    cond = offer.get("itemCondition")
    if cond and short_type(cond) not in VALID_CONDITION:
        add("error", f"{where}: itemCondition '{cond}' is not a schema.org OfferItemCondition")
    pvu = offer.get("priceValidUntil")
    if pvu:
        try:
            when = dt.date.fromisoformat(str(pvu)[:10])
            if when < today:
                add("warning", f"{where}: priceValidUntil {pvu} is in the past; Google may ignore the offer")
        except ValueError:
            add("error", f"{where}: priceValidUntil '{pvu}' must be an ISO date (YYYY-MM-DD)")
    if not offer.get("shippingDetails"):
        add("info", f"{where}: shippingDetails is recommended for merchant listings")
    if not offer.get("hasMerchantReturnPolicy"):
        add("info", f"{where}: hasMerchantReturnPolicy is recommended for merchant listings")


def _numeric(value) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", str(value).strip()))


def check_rating(rating, where: str, add) -> None:
    if not isinstance(rating, dict):
        add("error", f"{where}: aggregateRating must be an object")
        return
    value = rating.get("ratingValue")
    if value in (None, "") or not _numeric(value):
        add("error", f"{where}: aggregateRating.ratingValue must be a number")
        return
    best = float(rating.get("bestRating", 5)) if _numeric(rating.get("bestRating", 5)) else 5.0
    worst = float(rating.get("worstRating", 1)) if _numeric(rating.get("worstRating", 1)) else 1.0
    if not worst <= float(value) <= best:
        add(
            "error",
            f"{where}: ratingValue {value} is outside {worst:g}-{best:g} (set bestRating/worstRating)",
        )
    counts = [rating.get(k) for k in ("reviewCount", "ratingCount") if rating.get(k) not in (None, "")]
    if not counts:
        add("error", f"{where}: aggregateRating needs reviewCount or ratingCount")
    elif not all(_numeric(c) and float(c) > 0 for c in counts):
        add("error", f"{where}: reviewCount/ratingCount must be positive numbers")


def check_product(node: dict, idx: int, today: dt.date) -> list[dict]:
    out: list[dict] = []
    label = f"Product #{idx + 1}" + (f" '{node.get('name')}'" if node.get("name") else "")

    def add(sev, msg):
        out.append({"severity": sev, "product": idx + 1, "message": msg})

    if not node.get("name"):
        add("error", f"{label}: missing name")
    if not node.get("image"):
        add("error", f"{label}: missing image (required for merchant listings)")
    offers, rating, review = node.get("offers"), node.get("aggregateRating"), node.get("review")
    if not (offers or rating or review):
        add("error", f"{label}: needs at least one of offers, aggregateRating or review")
    for i, offer in enumerate(offers if isinstance(offers, list) else ([offers] if offers else [])):
        if isinstance(offer, dict):
            check_offer(offer, f"{label} offer {i + 1}", add, today)
        else:
            add("error", f"{label}: offers must be objects")
    if rating is not None:
        check_rating(rating, label, add)
    reviews = review if isinstance(review, list) else ([review] if review else [])
    for i, r in enumerate(reviews):
        if not isinstance(r, dict):
            continue
        if not r.get("author"):
            add("error", f"{label} review {i + 1}: missing author")
        rr = r.get("reviewRating")
        if not isinstance(rr, dict) or not _numeric(rr.get("ratingValue", "")):
            add("error", f"{label} review {i + 1}: reviewRating.ratingValue must be a number")
    for key in GTIN_KEYS:
        if node.get(key) and key != "isbn" and not gtin_ok(str(node[key])):
            add("error", f"{label}: {key} '{node[key]}' fails the GS1 check digit")
    for key in ("brand", "sku", "description"):
        if not node.get(key):
            add("info", f"{label}: {key} is recommended")
    if not any(node.get(k) for k in (*GTIN_KEYS, "mpn")):
        add("info", f"{label}: add gtin or mpn when the product has one")
    return out


def load_documents(path: str) -> tuple[list, list[str]]:
    text = read_text(path)
    errors = []
    blocks = LD_RE.findall(text) if "<script" in text.lower() else [text]
    docs = []
    for i, block in enumerate(blocks):
        cleaned = block.strip()
        cleaned = re.sub(r"^\s*<!\[CDATA\[|\]\]>\s*$", "", cleaned)
        try:
            docs.append(json.loads(cleaned))
        except json.JSONDecodeError as exc:
            errors.append(f"JSON-LD block {i + 1} is not valid JSON: {exc.msg} (line {exc.lineno})")
    return docs, errors


def validate(path: str, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    docs, parse_errors = load_documents(path)
    findings = [{"severity": "error", "product": None, "message": e} for e in parse_errors]
    products = []
    for doc in docs:
        products += extract_nodes(doc)
    if not products and not parse_errors:
        findings.append({"severity": "error", "product": None, "message": "no Product JSON-LD found"})
    names = [str(p.get("name", "")).strip().lower() for p in products]
    for name in {n for n in names if n and names.count(n) > 1}:
        findings.append(
            {
                "severity": "warning",
                "product": None,
                "message": f"Product '{name}' is marked up {names.count(name)} times; two plugins "
                "(theme + SEO plugin + reviews app) are probably both printing schema",
            }
        )
    for i, node in enumerate(products):
        findings += check_product(node, i, today)
    return {
        "source": path,
        "blocks": len(docs) + len(parse_errors),
        "products": len(products),
        "errors": sum(f["severity"] == "error" for f in findings),
        "warnings": sum(f["severity"] == "warning" for f in findings),
        "findings": findings,
    }


# ---------------------------------------------------------------- CLI


def cmd_generate(args) -> int:
    try:
        if args.input.lower().endswith(".csv"):
            products = rows_from_csv(args.input)
        else:
            loaded = json.loads(read_text(args.input))
            products = loaded if isinstance(loaded, list) else [loaded]
        built = [build_product(p, args.currency) for p in products]
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not built:
        print("error: no products in input", file=sys.stderr)
        return 2
    for data in built:
        body = json.dumps(data, indent=2, ensure_ascii=False)
        if args.script_tag:
            print(f'<script type="application/ld+json">\n{body}\n</script>')
        else:
            print(body)
    return 0


def cmd_validate(args) -> int:
    try:
        report = validate(args.file, dt.date.fromisoformat(args.today) if args.today else None)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['source']}: {report['blocks']} JSON-LD block(s), {report['products']} product(s), "
            f"{report['errors']} error(s), {report['warnings']} warning(s)"
        )
        for f in report["findings"]:
            if f["severity"] == "info" and not args.verbose:
                continue
            print(f"  [{f['severity'].upper()}] {f['message']}")
        if not args.verbose and any(f["severity"] == "info" for f in report["findings"]):
            print("  (recommendations hidden; use --verbose)")
    return 1 if report["errors"] else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="build JSON-LD from product JSON or CSV")
    g.add_argument("input", help="product .json (object or list), .csv export, or - for JSON on stdin")
    g.add_argument("--currency", default="", help="ISO currency when the input has none (e.g. BDT)")
    g.add_argument("--script-tag", action="store_true", help="wrap each product in a <script> tag")
    g.set_defaults(func=cmd_generate)
    v = sub.add_parser("validate", help="validate JSON-LD in a .json or saved .html file")
    v.add_argument("file", help="JSON-LD file or saved page HTML, or - for stdin")
    v.add_argument("--json", action="store_true", help="print JSON")
    v.add_argument("--verbose", action="store_true", help="also show recommendations")
    v.add_argument("--today", help=argparse.SUPPRESS)
    v.set_defaults(func=cmd_validate)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
