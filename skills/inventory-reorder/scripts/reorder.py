#!/usr/bin/env python3
"""Compute reorder points, safety stock, days of stock and order quantities per SKU.

Input: a sales history CSV (date, sku, quantity; order-line exports work) and a stock CSV
(sku, on hand, optional lead time, on order, MOQ, case pack, unit cost, name). Daily demand
counts zero-sale days in the window, safety stock = z * sd(daily demand) * sqrt(lead time),
reorder point = average daily demand * lead time + safety stock, and the suggested order
brings stock up to cover lead time + --cover-days, rounded to case pack and MOQ.

Statuses: stockout, reorder, ok, overstock, dead (no sales in the window), new (short history).
With --budget, order lines are funded in priority order (stockouts first, then the
fewest days of stock); a line that does not fit is cut to the largest case-pack multiple
that still meets its MOQ, or deferred. Lines without a unit cost are never cut.
Read-only; writes a purchase-order CSV only with --out.

Exit codes: 0 = nothing to reorder, 1 = stockouts or reorders needed, 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
from collections import defaultdict

Z = {0.80: 0.84, 0.85: 1.04, 0.90: 1.28, 0.95: 1.645, 0.975: 1.96, 0.98: 2.05, 0.99: 2.33, 0.995: 2.58}
SALES_COLS = {
    "date": ["date", "order date", "created at", "created_at", "day", "paid at"],
    "sku": ["sku", "lineitem sku", "item sku", "product sku", "variant sku"],
    "qty": ["qty", "quantity", "lineitem quantity", "units", "item quantity", "quantity sold"],
}
STOCK_COLS = {
    "sku": ["sku", "variant sku", "product sku"],
    "on_hand": ["on_hand", "on hand", "stock", "stock quantity", "inventory", "available", "qty", "quantity"],
    "on_order": ["on_order", "on order", "incoming"],
    "lead_time": ["lead_time_days", "lead time", "lead_time", "lead time days"],
    "moq": ["moq", "min order", "minimum order"],
    "case_pack": ["case_pack", "case pack", "pack size", "carton"],
    "unit_cost": ["unit_cost", "cost", "unit cost", "cost per item"],
    "name": ["name", "title", "product", "product name"],
}
STATUS_ORDER = {"stockout": 0, "reorder": 1, "new": 2, "ok": 3, "overstock": 4, "dead": 5}


def num(value, default=0.0) -> float:
    v = re.sub(r"[^\d.\-]", "", str(value or "").replace(",", ""))
    try:
        return float(v) if v not in ("", "-", ".") else default
    except ValueError:
        return default


def parse_day(value: str):
    v = (value or "").strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ):
        for candidate in (v[:19], v[:16], v[:10]):
            try:
                return dt.datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def read_csv(path: str, cols: dict, required: list[str]) -> list[dict]:
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
            raise ValueError(f"{path}: cannot find column(s) {missing}; headers are {list(lookup)}")
        return [{k: (row.get(col) or "").strip() for k, col in mapping.items()} for row in reader]


def z_for(level: float) -> float:
    if level in Z:
        return Z[level]
    closest = min(Z, key=lambda k: abs(k - level))
    return Z[closest]


def compute(sales: list[dict], stock: list[dict], opts) -> dict:
    daily: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    first_sale: dict[str, dt.date] = {}
    skipped = 0
    dates = []
    for row in sales:
        day = parse_day(row["date"])
        if day is None or not row["sku"]:
            skipped += 1
            continue
        daily[row["sku"]][day] += num(row["qty"])
        dates.append(day)
        first_sale[row["sku"]] = min(first_sale.get(row["sku"], day), day)
    if not dates:
        raise ValueError("no usable sales rows (need date, sku and quantity)")
    as_of = dt.date.fromisoformat(opts.as_of) if opts.as_of else max(dates)
    start = as_of - dt.timedelta(days=opts.window - 1)
    z = z_for(opts.service_level)

    results = []
    terms: dict[str, tuple[float, float, float]] = {}
    stock_skus = set()
    for item in stock:
        sku = item["sku"]
        if not sku:
            continue
        stock_skus.add(sku)
        on_hand = num(item.get("on_hand"))
        on_order = num(item.get("on_order"))
        lead = num(item.get("lead_time"), opts.lead_time) or opts.lead_time
        moq = num(item.get("moq"), 0)
        pack = num(item.get("case_pack"), 1) or 1
        cost = num(item.get("unit_cost"), 0)
        terms[sku] = (pack, moq, cost)
        sku_start = start
        short = False
        if sku in first_sale and first_sale[sku] > start:
            sku_start = first_sale[sku]
            short = (as_of - sku_start).days + 1 < opts.min_history
        days = max(1, (as_of - sku_start).days + 1)
        series = [max(0.0, daily[sku].get(sku_start + dt.timedelta(days=i), 0.0)) for i in range(days)]
        total = sum(series)
        avg = total / days
        sd = math.sqrt(sum((x - avg) ** 2 for x in series) / days)
        safety = z * sd * math.sqrt(lead)
        rop = avg * lead + safety
        position = on_hand + on_order
        dos = position / avg if avg > 0 else None
        target = avg * (lead + opts.cover_days) + safety
        qty = 0
        if position <= rop and avg > 0:
            need = max(0.0, target - position)
            qty = math.ceil(need / pack) * pack if need > 0 else 0
            if moq and 0 < qty < moq:
                qty = math.ceil(moq / pack) * pack
        if total == 0:
            status = "dead" if on_hand > 0 else "ok"
        elif on_hand <= 0:
            status = "stockout"
        elif position <= rop:
            status = "reorder"
        elif short:
            status = "new"
        elif dos is not None and dos > opts.overstock_days:
            status = "overstock"
        else:
            status = "ok"
        stockout_date = (
            (as_of + dt.timedelta(days=int(on_hand / avg))).isoformat() if avg > 0 and on_hand > 0 else None
        )
        results.append(
            {
                "sku": sku,
                "name": item.get("name", ""),
                "status": status,
                "on_hand": on_hand,
                "on_order": on_order,
                "sold_in_window": round(total, 2),
                "history_days": days,
                "avg_daily": round(avg, 3),
                "sd_daily": round(sd, 3),
                "lead_time_days": lead,
                "safety_stock": round(safety, 1),
                "reorder_point": round(rop, 1),
                "days_of_stock": None if dos is None else round(dos, 1),
                "est_stockout_date": stockout_date,
                "order_qty": int(qty),
                "order_value": round(qty * cost, 2) if cost else None,
                "excess_units": round(max(0.0, position - avg * opts.overstock_days), 1)
                if status == "overstock"
                else 0,
            }
        )
    unknown = sorted(s for s in daily if s not in stock_skus)
    results.sort(
        key=lambda r: (
            STATUS_ORDER[r["status"]],
            r["days_of_stock"] if r["days_of_stock"] is not None else 1e9,
        )
    )
    budget = getattr(opts, "budget", None)
    budget_info = apply_budget(results, terms, budget) if budget is not None else None
    counts = defaultdict(int)
    for r in results:
        counts[r["status"]] += 1
    out = {
        "as_of": as_of.isoformat(),
        "window_days": opts.window,
        "service_level": opts.service_level,
        "z": z,
        "skus": len(results),
        "counts": dict(counts),
        "order_lines": sum(1 for r in results if r["order_qty"] > 0),
        "order_value": round(sum(r["order_value"] or 0 for r in results), 2),
        "sold_but_not_in_stock_file": unknown,
        "skipped_sales_rows": skipped,
        "results": results,
    }
    if budget_info is not None:
        out["budget"] = budget_info
    return out


def apply_budget(results: list[dict], terms: dict, budget: float) -> dict:
    """Fund order lines in the given (priority) order until the budget runs out.

    A line that does not fit is reduced to the largest case-pack multiple that fits and
    still meets the MOQ; otherwise it is deferred (order_qty 0). The suggested quantity is
    kept in ``suggested_qty`` for every line that was cut or deferred.
    """
    remaining = budget
    cut = deferred = 0
    deferred_value = 0.0
    for r in results:
        qty = r["order_qty"]
        if qty <= 0:
            continue
        pack, moq, cost = terms.get(r["sku"], (1, 0, 0))
        if not cost:
            r["budget_note"] = "no unit cost; not limited by budget"
            continue
        if qty * cost <= remaining + 1e-9:
            remaining -= qty * cost
            continue
        fit = math.floor((remaining + 1e-9) / cost / pack) * pack
        r["suggested_qty"] = qty
        if fit > 0 and fit >= moq:
            r["order_qty"] = int(fit)
            r["budget_note"] = "cut to fit budget"
            cut += 1
        else:
            r["order_qty"] = 0
            r["budget_note"] = "deferred: over budget"
            deferred += 1
        deferred_value += (qty - r["order_qty"]) * cost
        r["order_value"] = round(r["order_qty"] * cost, 2)
        remaining -= r["order_qty"] * cost
    return {
        "limit": budget,
        "spent": round(budget - remaining, 2),
        "remaining": round(remaining, 2),
        "lines_cut": cut,
        "lines_deferred": deferred,
        "unfunded_value": round(deferred_value, 2),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sales", required=True, help="sales history CSV (date, sku, quantity)")
    p.add_argument("--stock", required=True, help="current stock CSV (sku, on_hand, ...)")
    p.add_argument("--as-of", help="end date of the window, YYYY-MM-DD (default: last sales date)")
    p.add_argument("--window", type=int, default=90, help="days of history to use (default 90)")
    p.add_argument(
        "--lead-time", type=float, default=14, help="default supplier lead time in days (default 14)"
    )
    p.add_argument(
        "--cover-days", type=float, default=30, help="days of demand an order should cover (default 30)"
    )
    p.add_argument("--service-level", type=float, default=0.95, help="0.80-0.995 (default 0.95)")
    p.add_argument("--overstock-days", type=float, default=180, help="days of stock counted as overstock")
    p.add_argument("--min-history", type=int, default=28, help="SKUs selling for fewer days are 'new'")
    p.add_argument(
        "--budget",
        type=float,
        help="maximum purchase value; fund stockouts first, then lowest days of stock",
    )
    p.add_argument("--out", help="write a purchase-order CSV (SKUs with order_qty > 0)")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    if not 0.5 <= args.service_level < 1:
        print("error: --service-level must be between 0.5 and 1", file=sys.stderr)
        return 2
    if args.budget is not None and args.budget < 0:
        print("error: --budget must be zero or more", file=sys.stderr)
        return 2
    try:
        sales = read_csv(args.sales, SALES_COLS, ["date", "sku", "qty"])
        stock = read_csv(args.stock, STOCK_COLS, ["sku", "on_hand"])
        report = compute(sales, stock, args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["sku", "name", "order_qty", "order_value", "status", "days_of_stock", "est_stockout_date"]
            )
            for r in report["results"]:
                if r["order_qty"] > 0:
                    w.writerow(
                        [
                            r["sku"],
                            r["name"],
                            r["order_qty"],
                            r["order_value"] or "",
                            r["status"],
                            r["days_of_stock"],
                            r["est_stockout_date"] or "",
                        ]
                    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        c = report["counts"]
        print(
            f"As of {report['as_of']} ({report['window_days']}-day window, service level "
            f"{report['service_level']:.0%}): {report['skus']} SKUs | "
            + ", ".join(f"{k} {c[k]}" for k in STATUS_ORDER if c.get(k))
        )
        print(f"{'SKU':<14} {'status':<9} {'on hand':>7} {'avg/day':>7} {'ROP':>6} {'DoS':>6} {'order':>6}")
        for r in report["results"]:
            dos = "-" if r["days_of_stock"] is None else f"{r['days_of_stock']:.0f}"
            print(
                f"{r['sku'][:14]:<14} {r['status']:<9} {r['on_hand']:>7.0f} {r['avg_daily']:>7.2f} "
                f"{r['reorder_point']:>6.0f} {dos:>6} {r['order_qty']:>6}"
            )
        if report["order_value"]:
            print(f"Suggested purchase value: {report['order_value']:.2f}")
        if "budget" in report:
            b = report["budget"]
            print(
                f"Budget {b['limit']:.2f}: spent {b['spent']:.2f}, {b['lines_cut']} line(s) cut, "
                f"{b['lines_deferred']} deferred, unfunded {b['unfunded_value']:.2f}"
            )
        if report["sold_but_not_in_stock_file"]:
            print("Sold but missing from stock file: " + ", ".join(report["sold_but_not_in_stock_file"]))
        if args.out:
            print(f"Purchase order written to {args.out}")
    return 1 if c_needs(report) else 0


def c_needs(report: dict) -> bool:
    return bool(report["counts"].get("stockout") or report["counts"].get("reorder"))


if __name__ == "__main__":
    sys.exit(main())
