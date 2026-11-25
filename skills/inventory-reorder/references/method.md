# Reorder method used by reorder.py

## Formulas

For each SKU, over the window (default 90 days ending `--as-of`):

```
daily demand d_i   = units sold on day i (0 on days without sales; refunds reduce the day, floor 0)
average demand  D  = sum(d_i) / days
variability     sd = population standard deviation of d_i
safety stock    SS = z * sd * sqrt(L)            L = lead time in days
reorder point  ROP = D * L + SS
position         P = on_hand + on_order
days of stock  DoS = P / D
order-up-to      S = D * (L + cover_days) + SS
order quantity   Q = S - P   if P <= ROP, rounded up to the case pack, at least the MOQ
```

`z` comes from the service level (probability of not running out during the lead time):

| Service level | z |
| --- | --- |
| 80% | 0.84 |
| 85% | 1.04 |
| 90% | 1.28 |
| 95% | 1.645 |
| 97.5% | 1.96 |
| 98% | 2.05 |
| 99% | 2.33 |
| 99.5% | 2.58 |

Use 95% for most products, 98-99% for best sellers and products that bring repeat customers,
85-90% for slow, expensive or perishable items.

## Statuses

| Status | Rule | Action |
| --- | --- | --- |
| `stockout` | sold in the window, on hand <= 0 | order now; check lost sales |
| `reorder` | position <= reorder point | order the suggested quantity |
| `new` | first sale fewer than `--min-history` (28) days ago | watch; numbers are unstable |
| `ok` | otherwise | nothing |
| `overstock` | days of stock > `--overstock-days` (180) | stop reordering; `excess_units` above 180 days |
| `dead` | no sales in the window, stock on hand | discount, bundle or delist |

## When to adjust the inputs

- **Stockouts in the window**: days with zero stock are counted as zero demand, so demand is
  underestimated. Shorten the window to an in-stock period, or remove those days from the sales
  file and re-run.
- **One-off bulk/wholesale orders**: remove them from the sales file or they inflate both
  demand and safety stock.
- **Seasonality (Eid, Puja, winter, back to school, Black Friday)**: use last year's same period
  as the window (`--as-of` last year + `--window`), or scale the suggested quantity by the
  expected uplift. State the assumption.
- **Promotions planned**: add the expected extra units on top of the suggestion.
- **Lead time varies**: use the longer realistic lead time, not the supplier's best case.
  Imports in Bangladesh often need 30-60 days including LC and customs.
- **Case packs and MOQ**: put them in the stock file; the script rounds up.
- **Cash constraints**: sort by `order_value` and margin; order best sellers first.

## Shopify and WooCommerce exports

| Data | WooCommerce | Shopify |
| --- | --- | --- |
| Sales by line | order export with line items (`Order Date`, `SKU`, `Quantity`), or Analytics > Products with daily interval | Orders export: `Created at`, `Lineitem sku`, `Lineitem quantity` |
| Stock | Products > Export: `SKU`, `Stock` (enable "Manage stock") | Products > Inventory > Export: `SKU`, `Available` |

Exclude cancelled, failed and test orders from the sales history.
