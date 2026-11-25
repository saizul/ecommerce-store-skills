---
name: inventory-reorder
description: Computes reorder points, safety stock, days of stock, estimated stockout dates and suggested purchase quantities per SKU from a sales history CSV (WooCommerce/Shopify order-line exports work) and a current stock CSV, using average daily demand with zero-sale days counted, demand variability, supplier lead time, service level, MOQ and case-pack rounding; classifies every SKU as stockout, reorder, new, ok, overstock or dead stock and writes a purchase-order CSV. Use when the user asks what to reorder, how much stock to buy, when a product will run out, how many days of stock are left, what safety stock or reorder point to set, or wants to find overstock and dead inventory.
license: MIT
compatibility: Python 3.8+ standard library. Works offline on CSV files.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Inventory reorder

Answer "what do I need to order, how much, and by when" from the store's own sales history,
with numbers the user can check.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "What should I reorder this week?", "how many units should I buy?"
- "When will this run out?", "how many days of stock do I have?"
- Setting low-stock thresholds (WooCommerce "Low stock threshold", Shopify inventory alerts)
- Finding overstock and dead stock to discount or bundle before buying more

## When not to use

- Forecasting a brand-new product with no sales (use a comparable product's history or a
  launch estimate; the script marks short histories as `new`)
- Strong seasonality or a planned promotion: the method assumes recent demand continues;
  adjust the window or multiply demand (see the method reference)
- Multi-warehouse transfers, manufacturing BOMs or full demand planning systems

## Workflow

1. **Get two CSVs.**
   - Sales history (at least 60-90 days): one row per order line with date, SKU and quantity.
     WooCommerce: an order export with line items (or Analytics > Products by day). Shopify:
     Orders export (`Created at`, `Lineitem sku`, `Lineitem quantity`) or the "Sales by product
     variant" report by day. Exclude cancelled/failed orders before exporting if possible.
   - Current stock: SKU and on-hand quantity (WooCommerce product export `SKU`, `Stock`;
     Shopify inventory export `SKU`, `Available`). Optional columns: `On order`,
     `Lead time days`, `MOQ`, `Case pack`, `Cost`, `Name`.
   Ask for supplier lead times; if unknown use `--lead-time` (default 14 days) and say so.
2. **Run the calculation (read-only).**
   ```bash
   python3 scripts/reorder.py --sales sales.csv --stock stock.csv
   python3 scripts/reorder.py --sales sales.csv --stock stock.csv --service-level 0.98 --cover-days 45
   python3 scripts/reorder.py --sales sales.csv --stock stock.csv --json > reorder.json
   python3 scripts/reorder.py --sales sales.csv --stock stock.csv --out purchase-order.csv
   ```
   `--as-of` sets the end of the window (default: last sales date), `--window` the history length
   (90). Exit 1 when any SKU is in `stockout` or `reorder`.
3. **Sanity-check the inputs** before trusting the output: `skipped_sales_rows` (bad dates),
   `sold_but_not_in_stock_file` (SKU mismatches or deleted variants), stockouts during the
   window (demand looks lower than it really was), one-off bulk orders inflating demand.
   Explanations and adjustments are in [references/method.md](references/method.md).
4. **Present by urgency**: stockouts and reorders with quantity, value and stockout date; then
   `new` SKUs to watch; then overstock (`excess_units`) and dead stock with suggestions
   (bundle, discount, stop reordering). Show the assumptions (window, service level, lead times).
5. **Do not place orders or change stock settings.** Purchase orders and low-stock thresholds
   are proposals; the user decides and applies them. Suggested threshold per SKU = its
   `reorder_point`.

## Output

```
As of 2026-11-20 (90 days, 95% service level, default lead time 14 days)

Order now
  MUG-1  stockout since today, 2.0/day, lead 21 d -> order 108 (324.00)
  TEE-M  8 days left (runs out ~2026-11-28), ROP 77 -> order 190 (case pack 10, MOQ 50)
Watch
  NEWBAG new (10 days of sales, 3/day), 33 days of stock
Overstock / dead
  BOARD  400 days of stock (excess ~220 units): stop reordering, bundle with knives
  SPOON  no sales in 90 days, 25 on hand: discount or delist
Data notes: GHOST sold 6 units but is not in the stock file (renamed SKU?)
```
