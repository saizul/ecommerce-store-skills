#!/usr/bin/env python3
"""Score cash-on-delivery (COD) orders for refusal / fake-order risk with transparent rules.

Each order gets points for: invalid phone, earlier refused/returned deliveries for the same
phone, a low delivery success rate, a first order with a high value, a value far above the
batch median, several orders from one phone within 24 hours, test/fake-looking names,
very short addresses, disposable email domains and bulk quantities. Customers with a
good delivery record get points removed. Levels: high >= 60, medium >= 30, low.

Input: an order CSV (raw export or the output of order-export-cleanup) and optionally a
history CSV of past orders with a status column (delivered, returned, refused, ...).
Phones are masked in all output. Read-only; writes a scored CSV only with --out.

Exit codes: 0 = no high-risk orders, 1 = high-risk orders found, 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
from collections import defaultdict

COLS = {
    "order_id": ["order id", "order number", "order_number", "order_id", "name", "id", "invoice"],
    "date": ["order date", "date", "created at", "created_at", "date created"],
    "phone": [
        "phone_e164",
        "billing phone",
        "phone",
        "shipping phone",
        "customer phone",
        "mobile",
        "recipient phone",
    ],
    "name": ["billing name", "customer name", "full name", "shipping name", "recipient name"],
    "first_name": ["billing first name", "first name"],
    "last_name": ["billing last name", "last name"],
    "address": [
        "billing address 1",
        "billing address1",
        "address 1",
        "address",
        "shipping address1",
        "recipient address",
    ],
    "email": ["billing email", "email", "customer email"],
    "payment": ["is_cod", "payment method title", "payment method", "payment_method", "gateway"],
    "total": ["total_clean", "order total", "total", "order_total", "cod amount", "amount"],
    "qty": ["quantity", "qty", "lineitem quantity", "items", "item count"],
    "status": ["status", "order status", "delivery status", "courier status"],
}
SUCCESS = re.compile(r"deliver|complete|paid|success", re.I)
FAILURE = re.compile(
    r"return|refus|rto|undeliver|fail|reject|not\s*received|cancel+ed\s*by\s*(customer|courier)", re.I
)
COD_RE = re.compile(r"^yes$|cash\s*on\s*delivery|\bcod\b|cash_on_delivery|ক্যাশ\s*অন", re.I)
FAKE_NAME = re.compile(
    r"^(test|asdf|qwer|xxx+|abc|aaa+|demo|fake|na|n/a|none|customer|user)\b|^(.)\2{2,}$|\d{3,}", re.I
)
DISPOSABLE = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "temp-mail.org",
    "yopmail.com",
    "trashmail.com",
    "sharklasers.com",
    "getnada.com",
    "dispostable.com",
    "throwawaymail.com",
}
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
RULES = {
    "invalid_phone": 40,
    "prior_failed_delivery": 25,
    "prior_failed_cap": 50,
    "low_success_rate": 20,
    "first_order_high_value": 15,
    "far_above_median": 10,
    "repeat_in_batch": 15,
    "fake_name": 20,
    "short_address": 15,
    "disposable_email": 10,
    "bulk_quantity": 10,
    "trusted_customer": -20,
}


def phone_key(raw: str) -> str:
    """Normalise to a comparable key: +8801XXXXXXXXX for BD mobiles, else digits."""
    digits = re.sub(r"\D", "", (raw or "").translate(BN_DIGITS))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("8800") and len(digits) == 14:
        digits = "880" + digits[4:]
    if len(digits) == 11 and digits.startswith("01"):
        digits = "880" + digits[1:]
    elif len(digits) == 10 and digits.startswith("1"):
        digits = "880" + digits
    if re.fullmatch(r"8801[3-9]\d{8}", digits):
        return "+" + digits
    return "+" + digits if 8 <= len(digits) <= 15 and (raw or "").strip().startswith(("+", "00")) else ""


def mask(key: str) -> str:
    return key[:7] + "****" + key[-3:] if len(key) > 10 else "(invalid)"


def num(value) -> float | None:
    v = re.sub(r"[^\d.]", "", str(value or "").translate(BN_DIGITS).replace(",", ""))
    try:
        return float(v) if v else None
    except ValueError:
        return None


def parse_dt(value: str):
    v = re.sub(r"\s*[+-]\d{4}$", "", (value or "").strip())
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return dt.datetime.strptime(v[:19], fmt)
        except ValueError:
            continue
    return None


def read(path: str) -> tuple[list[dict], dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        lookup = {h.strip().lower(): h for h in header}
        mapping = {}
        for key, aliases in COLS.items():
            for a in aliases:
                if a in lookup:
                    mapping[key] = lookup[a]
                    break
        rows = [{k: (v or "") for k, v in row.items() if k is not None} for row in reader]
    return rows, mapping


def get(row, mapping, key) -> str:
    return (row.get(mapping[key]) or "").strip() if key in mapping else ""


def load_history(path: str) -> dict:
    rows, m = read(path)
    if "phone" not in m or "status" not in m:
        raise ValueError(f"{path}: history needs phone and status columns")
    hist: dict[str, dict] = defaultdict(lambda: {"delivered": 0, "failed": 0, "other": 0})
    for row in rows:
        key = phone_key(get(row, m, "phone"))
        if not key:
            continue
        status = get(row, m, "status")
        if FAILURE.search(status):
            hist[key]["failed"] += 1
        elif SUCCESS.search(status):
            hist[key]["delivered"] += 1
        else:
            hist[key]["other"] += 1
    return dict(hist)


def _hit(reasons: list, rule: str, detail: str, points: int | None = None) -> None:
    reasons.append((rule, RULES[rule] if points is None else points, detail))


def score(rows: list[dict], m: dict, history: dict, opts) -> list[dict]:
    if "order_id" not in m:
        raise ValueError("orders CSV needs an order id column")
    totals = [t for t in (num(get(r, m, "total")) for r in rows) if t is not None]
    median = statistics.median(totals) if totals else 0
    by_phone: dict[str, list] = defaultdict(list)
    for r in rows:
        key = phone_key(get(r, m, "phone"))
        if key:
            by_phone[key].append(parse_dt(get(r, m, "date")))

    results = []
    for r in rows:
        payment = get(r, m, "payment")
        is_cod = bool(COD_RE.search(payment)) if "payment" in m else True
        if opts.cod_only and not is_cod:
            continue
        key = phone_key(get(r, m, "phone"))
        total = num(get(r, m, "total"))
        name = get(r, m, "name") or f"{get(r, m, 'first_name')} {get(r, m, 'last_name')}".strip()
        reasons: list[tuple[str, int, str]] = []

        if not key:
            _hit(reasons, "invalid_phone", "phone is missing or not a valid mobile number")
        h = history.get(key) if key else None
        if h:
            if h["failed"]:
                _hit(
                    reasons,
                    "prior_failed_delivery",
                    f"{h['failed']} earlier refused/returned delivery(ies)",
                    min(RULES["prior_failed_cap"], RULES["prior_failed_delivery"] * h["failed"]),
                )
            done = h["delivered"] + h["failed"]
            if done >= 2 and h["delivered"] / done < 0.5:
                _hit(reasons, "low_success_rate", f"delivery success {h['delivered']}/{done}")
            if h["delivered"] >= 3 and h["delivered"] / max(1, done) >= 0.9:
                _hit(reasons, "trusted_customer", f"{h['delivered']} successful deliveries")
        elif is_cod and total is not None and total >= opts.high_value:
            _hit(
                reasons, "first_order_high_value", f"first order, value {total:.0f} >= {opts.high_value:.0f}"
            )
        if total is not None and median and total >= 3 * median and total >= opts.high_value:
            _hit(reasons, "far_above_median", f"value {total:.0f} is {total / median:.1f}x the batch median")
        if key and len(by_phone[key]) > 1:
            when = parse_dt(get(r, m, "date"))
            close = [
                w
                for w in by_phone[key]
                if w is None or when is None or abs((w - when).total_seconds()) <= 86400
            ]
            if len(close) > 1:
                _hit(reasons, "repeat_in_batch", f"{len(close)} orders from this phone within 24 h")
        if name and FAKE_NAME.search(name.strip()) or (name and len(name.strip()) <= 2):
            _hit(reasons, "fake_name", f"name looks like a test or fake entry ({name[:20]!r})")
        address = get(r, m, "address")
        if "address" in m and len(address) < opts.min_address:
            _hit(reasons, "short_address", f"address has only {len(address)} characters")
        email = get(r, m, "email").lower()
        if "@" in email and email.rsplit("@", 1)[1] in DISPOSABLE:
            _hit(reasons, "disposable_email", "disposable email domain")
        qty = num(get(r, m, "qty"))
        if qty is not None and qty >= opts.bulk_qty:
            _hit(reasons, "bulk_quantity", f"{qty:.0f} items in one order")

        points = max(0, sum(p for _, p, _ in reasons))
        level = "high" if points >= 60 else "medium" if points >= 30 else "low"
        action = {
            "high": "call to confirm; ask for the delivery charge in advance (bKash/Nagad) or hold",
            "medium": "confirm by SMS/WhatsApp or a call before handing to the courier",
            "low": "ship normally",
        }[level]
        results.append(
            {
                "order_id": get(r, m, "order_id"),
                "phone": mask(key),
                "is_cod": is_cod,
                "total": total,
                "score": points,
                "level": level,
                "action": action,
                "reasons": [{"rule": a, "points": b, "detail": c} for a, b, c in reasons],
                "_row": r,
            }
        )
    results.sort(key=lambda x: -x["score"])
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--orders", required=True, help="orders CSV to score")
    p.add_argument("--history", help="past orders CSV with phone and delivery status")
    p.add_argument(
        "--high-value", type=float, default=3000, help="order value counted as high (default 3000)"
    )
    p.add_argument("--min-address", type=int, default=15, help="addresses shorter than this score points")
    p.add_argument("--bulk-qty", type=float, default=5, help="item count counted as bulk (default 5)")
    p.add_argument("--all", dest="cod_only", action="store_false", help="also score prepaid orders")
    p.add_argument("--out", help="write the orders with risk columns to this CSV")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    if args.out and os.path.abspath(args.out) == os.path.abspath(args.orders):
        print("error: --out must not be the input file", file=sys.stderr)
        return 2
    try:
        rows, mapping = read(args.orders)
        history = load_history(args.history) if args.history else {}
        results = score(rows, mapping, history, args)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    counts = {lvl: sum(r["level"] == lvl for r in results) for lvl in ("high", "medium", "low")}
    if args.out:
        header = list(rows[0].keys()) if rows else []
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh, fieldnames=header + ["risk_score", "risk_level", "risk_reasons", "risk_action"]
            )
            w.writeheader()
            for r in results:
                w.writerow(
                    {
                        **r["_row"],
                        "risk_score": r["score"],
                        "risk_level": r["level"],
                        "risk_reasons": "; ".join(x["detail"] for x in r["reasons"]),
                        "risk_action": r["action"],
                    }
                )
    for r in results:
        r.pop("_row")
    if args.json:
        print(
            json.dumps(
                {
                    "scored": len(results),
                    "counts": counts,
                    "history_phones": len(history),
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"{len(results)} orders scored: high {counts['high']}, "
            f"medium {counts['medium']}, low {counts['low']}"
            + (f" (history for {len(history)} phones)" if history else " (no history file)")
        )
        for r in results:
            if r["level"] == "low" and r["score"] == 0:
                continue
            print(
                f"\n{r['score']:>3} {r['level'].upper():<6} order {r['order_id']} "
                f"{r['phone']} total {r['total']}"
            )
            for x in r["reasons"]:
                print(f"      {x['points']:+d} {x['detail']}")
            print(f"      -> {r['action']}")
        if args.out:
            print(f"\nwritten: {args.out}")
    return 1 if counts["high"] else 0


if __name__ == "__main__":
    sys.exit(main())
