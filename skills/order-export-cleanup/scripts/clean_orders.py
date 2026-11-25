#!/usr/bin/env python3
"""Clean a WooCommerce / Shopify order CSV export for couriers, CRMs and analysis.

Normalises phone numbers to E.164 (Bangladesh +880 rules built in: 01XXXXXXXXX,
880..., Bangla digits, Excel-mangled numbers, operator detection), tidies names and
addresses, maps Bangladesh city/district spellings to the 64 official districts, checks
postcodes, flags cash-on-delivery orders, merges Shopify line-item rows, drops exact
duplicate rows and flags likely duplicate orders (same phone + same total within a time
window).

Dry run by default: prints a report with masked phone numbers. Writes a cleaned copy
only with --out (never overwrites the input).

Exit codes: 0 = clean, 1 = rows need attention, 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from collections import Counter

ALIASES = {
    "order_id": ["order id", "order number", "order_number", "order_id", "order no", "name", "id"],
    "date": ["order date", "date", "created at", "created_at", "date created", "order_date", "paid at"],
    "full_name": ["billing name", "customer name", "billing full name", "full name", "shipping name"],
    "first_name": ["billing first name", "first name", "billing_first_name"],
    "last_name": ["billing last name", "last name", "billing_last_name"],
    "phone": [
        "billing phone",
        "phone",
        "shipping phone",
        "phone number",
        "customer phone",
        "mobile",
        "billing_phone",
    ],
    "email": ["billing email", "email", "customer email", "billing_email"],
    "address1": [
        "billing address 1",
        "billing address1",
        "address 1",
        "address",
        "billing street",
        "shipping address1",
        "shipping address 1",
        "billing_address_1",
    ],
    "address2": [
        "billing address 2",
        "billing address2",
        "address 2",
        "shipping address2",
        "billing_address_2",
    ],
    "city": ["billing city", "city", "shipping city", "billing_city"],
    "state": [
        "billing state",
        "state",
        "district",
        "billing province",
        "shipping province",
        "province",
        "billing_state",
    ],
    "postcode": [
        "billing postcode",
        "billing zip",
        "postcode",
        "zip",
        "postal code",
        "shipping zip",
        "billing_postcode",
    ],
    "country": ["billing country", "country", "shipping country", "billing_country"],
    "payment": ["payment method title", "payment method", "payment_method", "payment gateway", "gateway"],
    "total": ["order total", "total", "order_total", "order total amount", "order amount"],
}
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
BD_OPERATORS = {
    "013": "Grameenphone",
    "017": "Grameenphone",
    "014": "Banglalink",
    "019": "Banglalink",
    "015": "Teletalk",
    "016": "Robi (Airtel)",
    "018": "Robi",
}
CALLING_CODES = {
    "BD": "880",
    "IN": "91",
    "PK": "92",
    "NP": "977",
    "LK": "94",
    "US": "1",
    "CA": "1",
    "GB": "44",
    "AE": "971",
    "SA": "966",
    "QA": "974",
    "KW": "965",
    "OM": "968",
    "MY": "60",
    "SG": "65",
    "AU": "61",
}
COUNTRY_NAMES = {
    "bangladesh": "BD",
    "india": "IN",
    "pakistan": "PK",
    "united kingdom": "GB",
    "united states": "US",
}
DISTRICTS = [
    "Bagerhat",
    "Bandarban",
    "Barguna",
    "Barishal",
    "Bhola",
    "Bogura",
    "Brahmanbaria",
    "Chandpur",
    "Chapainawabganj",
    "Chattogram",
    "Chuadanga",
    "Cox's Bazar",
    "Cumilla",
    "Dhaka",
    "Dinajpur",
    "Faridpur",
    "Feni",
    "Gaibandha",
    "Gazipur",
    "Gopalganj",
    "Habiganj",
    "Jamalpur",
    "Jashore",
    "Jhalokathi",
    "Jhenaidah",
    "Joypurhat",
    "Khagrachhari",
    "Khulna",
    "Kishoreganj",
    "Kurigram",
    "Kushtia",
    "Lakshmipur",
    "Lalmonirhat",
    "Madaripur",
    "Magura",
    "Manikganj",
    "Meherpur",
    "Moulvibazar",
    "Munshiganj",
    "Mymensingh",
    "Naogaon",
    "Narail",
    "Narayanganj",
    "Narsingdi",
    "Natore",
    "Netrokona",
    "Nilphamari",
    "Noakhali",
    "Pabna",
    "Panchagarh",
    "Patuakhali",
    "Pirojpur",
    "Rajbari",
    "Rajshahi",
    "Rangamati",
    "Rangpur",
    "Satkhira",
    "Shariatpur",
    "Sherpur",
    "Sirajganj",
    "Sunamganj",
    "Sylhet",
    "Tangail",
    "Thakurgaon",
]
DISTRICT_ALIASES = {
    "chittagong": "Chattogram",
    "ctg": "Chattogram",
    "chattagram": "Chattogram",
    "comilla": "Cumilla",
    "kumilla": "Cumilla",
    "barisal": "Barishal",
    "jessore": "Jashore",
    "jashor": "Jashore",
    "bogra": "Bogura",
    "coxs bazar": "Cox's Bazar",
    "coxsbazar": "Cox's Bazar",
    "cox bazar": "Cox's Bazar",
    "chapai nawabganj": "Chapainawabganj",
    "chapai": "Chapainawabganj",
    "nawabganj": "Chapainawabganj",
    "moulvi bazar": "Moulvibazar",
    "maulvibazar": "Moulvibazar",
    "maulvi bazar": "Moulvibazar",
    "jhalakati": "Jhalokathi",
    "jhalokati": "Jhalokathi",
    "netrakona": "Netrokona",
    "laxmipur": "Lakshmipur",
    "lakshmipur": "Lakshmipur",
    "b baria": "Brahmanbaria",
    "khagrachari": "Khagrachhari",
    "jhenaidaha": "Jhenaidah",
    "jaipurhat": "Joypurhat",
    "dhk": "Dhaka",
    "dhaka city": "Dhaka",
    "narayangonj": "Narayanganj",
    "kishorganj": "Kishoreganj",
    "potuakhali": "Patuakhali",
    "habigonj": "Habiganj",
    "sunamgonj": "Sunamganj",
    "gazipur city": "Gazipur",
    "ঢাকা": "Dhaka",
    "চট্টগ্রাম": "Chattogram",
    "সিলেট": "Sylhet",
    "খুলনা": "Khulna",
    "রাজশাহী": "Rajshahi",
    "বরিশাল": "Barishal",
    "রংপুর": "Rangpur",
    "ময়মনসিংহ": "Mymensingh",
    "কুমিল্লা": "Cumilla",
    "গাজীপুর": "Gazipur",
    "নারায়ণগঞ্জ": "Narayanganj",
}
COD_RE = re.compile(r"cash\s*on\s*delivery|\bcod\b|cash_on_delivery|ক্যাশ\s*অন\s*ডেলিভারি|পণ্য\s*হাতে", re.I)
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%B %d, %Y %I:%M %p",
    "%B %d, %Y",
]
ADDED = [
    "phone_e164",
    "phone_valid",
    "phone_operator",
    "district",
    "is_cod",
    "total_clean",
    "duplicate_of",
    "issues",
]


def _norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9ঀ-৿ ]", "", re.sub(r"[._-]+", " ", text.lower())).strip()


DISTRICT_LOOKUP = {_norm_key(d): d for d in DISTRICTS}
DISTRICT_LOOKUP.update({_norm_key(k): v for k, v in DISTRICT_ALIASES.items()})


def country_code(value: str, default: str) -> str:
    v = (value or "").strip()
    if not v:
        return default
    if len(v) == 2:
        return v.upper()
    return COUNTRY_NAMES.get(v.lower(), default)


def normalize_phone(raw: str, country: str = "BD") -> dict:
    """Return {'e164', 'valid', 'operator', 'issues'} for one phone field."""
    issues: list[str] = []
    text = (raw or "").translate(BN_DIGITS).strip()
    if not text:
        return {"e164": "", "valid": False, "operator": "", "issues": ["phone_missing"]}
    if re.fullmatch(r"\d(?:\.\d+)?e\+?\d+", text, re.I):
        return {"e164": "", "valid": False, "operator": "", "issues": ["phone_excel_corrupted"]}
    parts = [p for p in re.split(r"[,/;|]|\s{2,}|\bor\b", text) if re.search(r"\d{6,}", re.sub(r"\D", "", p))]
    if len(parts) > 1:
        issues.append("multiple_phones")
        text = parts[0]
    plus = text.lstrip().startswith("+")
    digits = re.sub(r"\D", "", text)
    if digits.startswith("00"):
        digits, plus = digits[2:], True

    if country == "BD" or digits.startswith("880") and (plus or len(digits) == 13):
        local = None
        if digits.startswith("880") and len(digits) == 13:
            local = "0" + digits[3:]
        elif digits.startswith("8800") and len(digits) == 14:
            local = digits[3:]
        elif len(digits) == 11 and digits.startswith("0"):
            local = digits
        elif len(digits) == 10 and digits.startswith("1"):
            local = "0" + digits
        if local and re.fullmatch(r"01[3-9]\d{8}", local):
            return {
                "e164": "+880" + local[1:],
                "valid": True,
                "operator": BD_OPERATORS[local[:3]],
                "issues": issues,
            }
        if plus and not digits.startswith("880") and 8 <= len(digits) <= 15:
            return {"e164": "+" + digits, "valid": True, "operator": "", "issues": issues + ["phone_foreign"]}
        return {"e164": "", "valid": False, "operator": "", "issues": issues + ["phone_invalid"]}

    cc = CALLING_CODES.get(country, "")
    if plus or (cc and digits.startswith(cc) and len(digits) > len(cc) + 6):
        e164 = "+" + digits
    elif cc:
        e164 = "+" + cc + digits.lstrip("0")
    else:
        e164 = "+" + digits if len(digits) >= 8 else ""
    ok = 8 <= len(e164) - 1 <= 15
    return {
        "e164": e164 if ok else "",
        "valid": ok,
        "operator": "",
        "issues": issues + ([] if ok else ["phone_invalid"]),
    }


def mask_phone(e164: str) -> str:
    return e164[:7] + "****" + e164[-3:] if len(e164) > 10 else ("****" if e164 else "")


def find_district(*fields: str) -> str:
    for field in fields:
        if not field:
            continue
        key = _norm_key(field)
        if key in DISTRICT_LOOKUP:
            return DISTRICT_LOOKUP[key]
        for part in reversed(re.split(r"[,\n]", field)):
            pk = _norm_key(part)
            if pk in DISTRICT_LOOKUP:
                return DISTRICT_LOOKUP[pk]
        words = key.split()
        for size in (2, 1):
            for i in range(len(words) - size, -1, -1):
                chunk = " ".join(words[i : i + size])
                if chunk in DISTRICT_LOOKUP:
                    return DISTRICT_LOOKUP[chunk]
    return ""


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()
    text = re.sub(r"\s*,\s*(,\s*)*", ", ", text)
    return text.strip(" ,;.-")


def tidy_name(text: str) -> str:
    text = tidy(text)
    if text and re.fullmatch(r"[A-Za-z .'-]+", text) and (text.islower() or text.isupper()):
        text = " ".join(w.capitalize() for w in text.split())
    return text


def field(row: dict, mapping: dict, name: str) -> str:
    return row.get(mapping[name], "") if name in mapping else ""


def parse_total(value: str) -> float | None:
    v = re.sub(r"[^\d.,-]", "", (value or "").translate(BN_DIGITS))
    if not v:
        return None
    if "," in v and "." in v:
        v = v.replace(",", "") if v.rfind(".") > v.rfind(",") else v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", "") if len(v.rsplit(",", 1)[1]) == 3 else v.replace(",", ".")
    try:
        return round(float(v), 2)
    except ValueError:
        return None


def parse_date(value: str):
    v = (value or "").strip()
    v = re.sub(r"\s*[+-]\d{4}$|\s*UTC$|Z$", "", v)
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def map_columns(header: list[str], overrides: dict) -> dict:
    lookup = {h.strip().lower(): h for h in header}
    mapping = {}
    for field, aliases in ALIASES.items():
        if field in overrides:
            if overrides[field] not in header:
                raise ValueError(f"--map {field}={overrides[field]}: column not found")
            mapping[field] = overrides[field]
            continue
        for alias in aliases:
            if alias in lookup:
                mapping[field] = lookup[alias]
                break
    if "order_id" not in mapping:
        raise ValueError("cannot find an order id column; use --map order_id=<column>")
    if "phone" not in mapping:
        raise ValueError("cannot find a phone column; use --map phone=<column>")
    return mapping


def merge_line_items(rows: list[dict], key: str) -> tuple[list[dict], int]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        oid = row[key]
        if oid not in merged:
            merged[oid] = dict(row)
            merged[oid]["_lines"] = 1
            order.append(oid)
        else:
            base = merged[oid]
            base["_lines"] += 1
            for k, v in row.items():
                if not base.get(k) and v:
                    base[k] = v
    return [merged[o] for o in order], len(rows) - len(order)


def clean(rows: list[dict], mapping: dict, opts) -> tuple[list[dict], dict]:
    m = mapping
    stats = Counter()
    seen_rows = set()
    unique = []
    for row in rows:
        sig = tuple(sorted(row.items()))
        if sig in seen_rows:
            stats["exact_duplicates_dropped"] += 1
            continue
        seen_rows.add(sig)
        unique.append(row)
    merged_lines = 0
    if opts.merge_lines:
        unique, merged_lines = merge_line_items(unique, m["order_id"])
    stats["line_rows_merged"] = merged_lines

    out = []
    first_id: dict[str, int] = {}
    by_phone_total: dict[tuple, list] = {}
    for row in unique:
        r = dict(row)
        r.pop("_lines", None)
        issues: list[str] = []
        cc = country_code(field(row, m, "country"), opts.country)
        phone = normalize_phone(field(row, m, "phone"), cc)
        issues += phone["issues"]
        r.update(
            phone_e164=phone["e164"],
            phone_valid="yes" if phone["valid"] else "no",
            phone_operator=phone["operator"],
        )
        for f in ("full_name", "first_name", "last_name"):
            if f in m:
                r[m[f]] = tidy_name(r[m[f]])
        for f in ("address1", "address2", "city", "state"):
            if f in m:
                r[m[f]] = tidy(r[m[f]])
        district = ""
        if cc == "BD":
            district = find_district(
                r.get(m.get("state", ""), ""),
                r.get(m.get("city", ""), ""),
                r.get(m.get("address2", ""), ""),
                r.get(m.get("address1", ""), ""),
            )
            if not district:
                issues.append("district_unknown")
            pc = (field(row, m, "postcode") or "").translate(BN_DIGITS).strip()
            if pc and not re.fullmatch(r"\d{4}", pc):
                issues.append("postcode_invalid")
            if "postcode" in m:
                r[m["postcode"]] = pc
        address = " ".join(r.get(m[f], "") for f in ("address1", "address2") if f in m).strip()
        if "address1" in m and len(address) < opts.min_address:
            issues.append("address_too_short")
        r["district"] = district
        r["is_cod"] = "yes" if COD_RE.search(field(row, m, "payment")) else "no"
        total = parse_total(field(row, m, "total"))
        r["total_clean"] = "" if total is None else f"{total:.2f}"
        oid = row[m["order_id"]]
        dup_of = ""
        if oid in first_id:
            issues.append("duplicate_order_id")
            dup_of = oid
        else:
            first_id[oid] = len(out)
        if phone["valid"] and total is not None and not dup_of:
            when = parse_date(field(row, m, "date"))
            for prev_id, prev_when in by_phone_total.get((phone["e164"], total), []):
                if (
                    when is None
                    or prev_when is None
                    or abs((when - prev_when).total_seconds()) <= opts.dup_hours * 3600
                ):
                    issues.append("possible_duplicate")
                    dup_of = prev_id
                    break
            by_phone_total.setdefault((phone["e164"], total), []).append((oid, when))
        r["duplicate_of"] = dup_of
        r["issues"] = ";".join(issues)
        out.append(r)
        stats.update(issues)

    attention = {
        "phone_missing",
        "phone_invalid",
        "phone_excel_corrupted",
        "duplicate_order_id",
        "possible_duplicate",
        "address_too_short",
    }
    flagged = [r for r in out if attention & set(filter(None, r["issues"].split(";")))]
    cod = sum(r["is_cod"] == "yes" for r in out)
    summary = {
        "rows_in": len(rows),
        "orders_out": len(out),
        "exact_duplicates_dropped": stats.pop("exact_duplicates_dropped", 0),
        "line_rows_merged": stats.pop("line_rows_merged", 0),
        "valid_phones": sum(r["phone_valid"] == "yes" for r in out),
        "cod_orders": cod,
        "cod_share": round(100 * cod / len(out), 1) if out else 0.0,
        "operators": dict(Counter(r["phone_operator"] for r in out if r["phone_operator"]).most_common()),
        "issues": dict(stats.most_common()),
        "needs_attention": len(flagged),
        "flagged": [
            {
                "order_id": r[m["order_id"]],
                "phone": mask_phone(r["phone_e164"]) or "(none)",
                "issues": r["issues"],
                "duplicate_of": r["duplicate_of"],
            }
            for r in flagged
        ],
        "columns": mapping,
    }
    return out, summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("csv", help="order export CSV")
    p.add_argument("--out", help="write the cleaned CSV here (default: report only, nothing written)")
    p.add_argument("--country", default="BD", help="default country code for phones (default BD)")
    p.add_argument(
        "--dup-hours", type=float, default=24, help="window for same phone + same total (default 24)"
    )
    p.add_argument("--min-address", type=int, default=10, help="flag addresses shorter than this")
    p.add_argument(
        "--merge-lines", action="store_true", help="merge rows sharing an order id (auto for Shopify)"
    )
    p.add_argument(
        "--map", action="append", default=[], metavar="FIELD=COLUMN", help="override a column mapping"
    )
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    args = p.parse_args(argv)
    args.country = args.country.upper()
    overrides = {}
    for item in args.map:
        if "=" not in item:
            print(f"error: --map needs FIELD=COLUMN, got {item!r}", file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        overrides[k.strip()] = v.strip()
    if args.out and os.path.abspath(args.out) == os.path.abspath(args.csv):
        print("error: --out must not be the input file", file=sys.stderr)
        return 2
    try:
        with open(args.csv, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = list(reader.fieldnames or [])
            rows = [{k: (v or "") for k, v in row.items() if k is not None} for row in reader]
        mapping = map_columns(header, overrides)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if any(h.strip().lower() == "lineitem name" for h in header):
        args.merge_lines = True
    out, summary = clean(rows, mapping, args)
    if args.out:
        fields = header + [c for c in ADDED if c not in header]
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(out)
        summary["written"] = args.out
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        s = summary
        print(
            f"{s['rows_in']} rows -> {s['orders_out']} orders "
            f"({s['exact_duplicates_dropped']} exact duplicate rows dropped, "
            f"{s['line_rows_merged']} line rows merged)"
        )
        print(
            f"valid phones {s['valid_phones']}/{s['orders_out']}, COD {s['cod_orders']} ({s['cod_share']}%)"
        )
        if s["operators"]:
            print("operators: " + ", ".join(f"{k} {v}" for k, v in s["operators"].items()))
        if s["issues"]:
            print("issues: " + ", ".join(f"{k} {v}" for k, v in s["issues"].items()))
        for f in s["flagged"][:25]:
            extra = f" (duplicate of {f['duplicate_of']})" if f["duplicate_of"] else ""
            print(f"  - {f['order_id']} {f['phone']}: {f['issues']}{extra}")
        print(f"written: {args.out}" if args.out else "dry run: nothing written (use --out cleaned.csv)")
    return 1 if summary["needs_attention"] else 0


if __name__ == "__main__":
    sys.exit(main())
