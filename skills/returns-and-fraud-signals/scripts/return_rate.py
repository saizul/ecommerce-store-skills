#!/usr/bin/env python3
"""Analyse return and refusal rates by SKU, reason, customer, district and courier.

Input: order lines (order id, sku, quantity; optional customer phone/email, district/city,
courier, status) plus either a returns CSV (order id, sku, quantity, reason) or a status
column on the order lines (returned / refused / RTO). Reports the overall unit return rate,
SKUs whose return rate is significantly above the store average (Wilson lower bound, so
small samples are not flagged), reason categories (size/fit, damaged, wrong item, not as
described, quality, changed mind, late delivery, refused/unreachable), serial returners
and rates per district and courier. Customer identifiers are masked. Read-only.

Exit codes: 0 = nothing flagged, 1 = flagged SKUs or customers, 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict

LINE_COLS = {
    "order_id": ["order id", "order number", "order_number", "order_id", "name", "invoice"],
    "sku": ["sku", "lineitem sku", "item sku", "product sku", "variant sku"],
    "qty": ["qty", "quantity", "lineitem quantity", "item quantity"],
    "customer": [
        "phone_e164",
        "billing phone",
        "phone",
        "customer phone",
        "billing email",
        "email",
        "customer",
    ],
    "district": ["district", "billing city", "city", "shipping city", "billing state"],
    "courier": ["courier", "shipping method", "carrier", "delivery partner"],
    "status": ["status", "order status", "delivery status", "line status"],
    "reason": ["reason", "return reason"],
}
RETURN_COLS = {
    "order_id": LINE_COLS["order_id"],
    "sku": LINE_COLS["sku"],
    "qty": ["qty", "quantity", "returned qty", "return quantity"],
    "reason": ["reason", "return reason", "note", "comment"],
}
RETURNED = re.compile(r"return|refus|rto|undeliver|failed\s*deliver|refund", re.I)
REASONS = [
    (
        "refused/unreachable",
        r"refus|unreach|not\s*pick|switch(ed)?\s*off|didn'?t\s*receive|no\s*answer|fake|rto",
    ),
    ("size/fit", r"size|fit|small|large|tight|loose|length"),
    ("damaged", r"damag|broken|torn|crack|leak|defect"),
    ("wrong item", r"wrong|different\s*item|mismatch|incorrect|missing"),
    ("not as described", r"not\s*as\s*(described|shown|pictured)|colou?r|looks?\s*different|picture"),
    ("quality", r"quality|cheap|fabric|material|poor"),
    ("late delivery", r"late|delay|took\s*too\s*long"),
    (
        "changed mind",
        r"changed?\s*(my\s*)?mind|no\s*longer|don'?t\s*(want|need)|mistake|ordered\s*by\s*mistake",
    ),
]
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def categorize(reason: str) -> str:
    r = (reason or "").strip()
    if not r:
        return "unspecified"
    for label, pattern in REASONS:
        if re.search(pattern, r, re.I):
            return label
    return "other"


def wilson_lower(k: float, n: float, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def customer_key(raw: str) -> str:
    v = (raw or "").translate(BN_DIGITS).strip().lower()
    if "@" in v:
        return v
    digits = re.sub(r"\D", "", v)
    return digits[-10:] if len(digits) >= 10 else digits


def mask(key: str) -> str:
    if "@" in key:
        user, _, domain = key.partition("@")
        return user[:2] + "***@" + domain
    return ("***" + key[-3:]) if key else ""


def qty(value) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", str(value or "")) or 1)
    except ValueError:
        return 1.0


def read(path: str, cols: dict, required: list[str]) -> tuple[list[dict], set]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        lookup = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
        mapping = {}
        for key, aliases in cols.items():
            for a in aliases:
                if a in lookup:
                    mapping[key] = lookup[a]
                    break
        missing = [k for k in required if k not in mapping]
        if missing:
            raise ValueError(f"{path}: cannot find column(s) {missing}")
        rows = [{k: (row.get(c) or "").strip() for k, c in mapping.items()} for row in reader]
    return rows, set(mapping)


def analyse(lines: list[dict], returns: list[dict] | None, opts) -> dict:
    sold = Counter()
    order_info: dict[str, dict] = {}
    for ln in lines:
        if not ln.get("sku"):
            continue
        sold[ln["sku"]] += qty(ln.get("qty"))
        info = order_info.setdefault(ln.get("order_id", ""), {"customer": "", "district": "", "courier": ""})
        for k in ("customer", "district", "courier"):
            if ln.get(k) and not info[k]:
                info[k] = {"customer": customer_key, "district": str.title}.get(k, str.strip)(ln[k].strip())

    returned = Counter()
    reasons = Counter()
    sku_reasons: dict[str, Counter] = defaultdict(Counter)
    returned_orders: set[str] = set()
    if returns is not None:
        events = [
            (r.get("order_id", ""), r.get("sku", ""), qty(r.get("qty")), r.get("reason", "")) for r in returns
        ]
    else:
        events = [
            (
                ln.get("order_id", ""),
                ln.get("sku", ""),
                qty(ln.get("qty")),
                ln.get("reason") or ln.get("status", ""),
            )
            for ln in lines
            if RETURNED.search(ln.get("status", ""))
        ]
    for oid, sku, q, reason in events:
        if not sku:
            continue
        cat = categorize(reason)
        returned[sku] += q
        reasons[cat] += q
        sku_reasons[sku][cat] += q
        returned_orders.add(oid)

    total_sold = sum(sold.values())
    total_returned = sum(returned.values())
    overall = total_returned / total_sold if total_sold else 0.0

    skus = []
    for sku in sorted(set(sold) | set(returned)):
        n, k = sold.get(sku, 0), returned.get(sku, 0)
        rate = k / n if n else None
        lower = wilson_lower(min(k, n), n) if n else 0.0
        flagged = n >= opts.min_units and lower > overall and (rate or 0) >= opts.min_rate
        skus.append(
            {
                "sku": sku,
                "sold": n,
                "returned": k,
                "rate": None if rate is None else round(rate, 3),
                "wilson_lower": round(lower, 3),
                "top_reason": sku_reasons[sku].most_common(1)[0][0] if sku_reasons[sku] else "",
                "flagged": flagged,
                "note": "" if n else "returns without sales in this file (sold earlier?)",
            }
        )
    skus.sort(key=lambda s: (not s["flagged"], -(s["rate"] or 0)))

    per_customer: dict[str, dict] = defaultdict(lambda: {"orders": 0, "returned_orders": 0})
    for oid, info in order_info.items():
        if info["customer"]:
            per_customer[info["customer"]]["orders"] += 1
            if oid in returned_orders:
                per_customer[info["customer"]]["returned_orders"] += 1
    serial = []
    for key, c in per_customer.items():
        share = c["returned_orders"] / c["orders"] if c["orders"] else 0
        if c["returned_orders"] >= opts.serial_returns or (c["orders"] >= 3 and share >= 0.5):
            serial.append({"customer": mask(key), **c, "share": round(share, 2)})
    serial.sort(key=lambda s: -s["returned_orders"])

    def group_rates(field: str) -> list[dict]:
        orders = Counter(info[field] for info in order_info.values() if info[field])
        rets = Counter(
            order_info[o][field] for o in returned_orders if o in order_info and order_info[o][field]
        )
        rows = [
            {field: g, "orders": n, "returned_orders": rets.get(g, 0), "rate": round(rets.get(g, 0) / n, 3)}
            for g, n in orders.items()
        ]
        return sorted(rows, key=lambda r: -r["rate"])

    total_orders = len(order_info)
    return {
        "orders": total_orders,
        "units_sold": total_sold,
        "units_returned": total_returned,
        "unit_return_rate": round(overall, 4),
        "order_return_rate": round(len(returned_orders & set(order_info)) / total_orders, 4)
        if total_orders
        else 0,
        "reasons": {k: v for k, v in reasons.most_common()},
        "flagged_skus": [s["sku"] for s in skus if s["flagged"]],
        "skus": skus,
        "serial_returners": serial,
        "by_district": group_rates("district"),
        "by_courier": group_rates("courier"),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--orders", required=True, help="order lines CSV (order id, sku, quantity, ...)")
    p.add_argument(
        "--returns", help="returns CSV (order id, sku, quantity, reason); else uses a status column"
    )
    p.add_argument("--min-units", type=int, default=10, help="minimum units sold before a SKU can be flagged")
    p.add_argument(
        "--min-rate", type=float, default=0.05, help="minimum return rate to flag a SKU (default 0.05)"
    )
    p.add_argument(
        "--serial-returns", type=int, default=3, help="returned orders that mark a serial returner"
    )
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        lines, have = read(args.orders, LINE_COLS, ["order_id", "sku"])
        returns = None
        if args.returns:
            returns, _ = read(args.returns, RETURN_COLS, ["sku"])
        elif "status" not in have:
            raise ValueError("give --returns or an orders file with a status column")
        report = analyse(lines, returns, args)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        r = report
        print(
            f"{r['orders']} orders, {r['units_sold']:.0f} units sold, {r['units_returned']:.0f} returned "
            f"({r['unit_return_rate']:.1%} of units, {r['order_return_rate']:.1%} of orders)"
        )
        if r["reasons"]:
            print("reasons: " + ", ".join(f"{k} {v:.0f}" for k, v in r["reasons"].items()))
        print("\nSKUs (flagged first):")
        for s in r["skus"][:15]:
            rate = "-" if s["rate"] is None else f"{s['rate']:.0%}"
            flag = "FLAG" if s["flagged"] else "    "
            print(
                f"  {flag} {s['sku']:<14} sold {s['sold']:>5.0f} returned {s['returned']:>4.0f} "
                f"{rate:>5}  {s['top_reason']}"
            )
        if r["serial_returners"]:
            print("\nSerial returners:")
            for c in r["serial_returners"]:
                print(f"  {c['customer']}: {c['returned_orders']} of {c['orders']} orders returned")
        for field in ("district", "courier"):
            rows = r[f"by_{field}"]
            if rows:
                print(
                    f"\nBy {field}: "
                    + ", ".join(f"{x[field]} {x['rate']:.0%} ({x['orders']})" for x in rows[:8])
                )
    return 1 if report["flagged_skus"] or report["serial_returners"] else 0


if __name__ == "__main__":
    sys.exit(main())
