---
name: returns-and-fraud-signals
description: Reduces fake cash-on-delivery (COD) orders, courier refusals (RTO) and costly returns for WooCommerce and Shopify stores - scores COD orders with transparent rules (invalid phone, earlier refused or returned deliveries, low delivery success rate, first order with high value, value far above median, repeat orders from one phone, test/fake names, short addresses, disposable emails, bulk quantities, trusted-customer credit) and recommends call, SMS/WhatsApp confirmation or advance delivery charge; and analyses return rates by SKU (Wilson lower bound so small samples are not flagged), reason category, serial returners, district and courier. Customer phones and emails are masked. Use when the user mentions fake orders, COD refusals, high return-to-origin rate, parcel returns, which products get returned most, customers who keep refusing deliveries, or wants rules for confirming COD orders.
license: MIT
compatibility: Python 3.8+ standard library. Works offline on CSV exports; no courier or fraud APIs are called.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Returns and fraud signals

Cut losses from refused COD parcels and avoidable returns with rules the store owner can read
and adjust, not a black box. Signals support a decision (confirm, ask for advance payment,
fix a product page); they never prove fraud.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Too many fake COD orders", "customers refuse parcels at the door", "RTO is 25%"
- Deciding which orders to call before handing them to the courier
- "Which products get returned most and why?", size/fit complaints, damaged-in-transit claims
- Customers or areas with repeated refusals; comparing couriers

## When not to use

- Card fraud chargebacks on prepaid orders: use the payment gateway's fraud tools (the script
  can score prepaid orders with `--all`, but card fraud needs gateway signals)
- Blocking customers automatically or sharing customer lists with other stores: not without a
  clear legal basis and the user's decision
- Cleaning messy exports: run `order-export-cleanup` first

## Privacy and fairness

- Work on local copies; output masks phones (`+880171****678`) and emails.
- Do not use protected characteristics or proxies for them (religion, ethnicity, gender) as
  signals. Area-level rates are for courier and logistics decisions, not for refusing service
  to a whole district.
- High risk means "confirm first", not "cancel". Keep a human in the loop.

## Workflow

1. **Collect data.**
   - Orders to check now (raw export or `orders-clean.csv` from `order-export-cleanup`).
   - History: past orders or courier reports with phone and delivery status (delivered,
     returned, refused, RTO). Courier merchant panels export this; the more history, the better.
   - For returns analysis: order lines (order id, SKU, quantity, phone/email, district, courier)
     and a returns list (order id, SKU, quantity, reason), or order lines with a status column.
2. **Score open COD orders (read-only).**
   ```bash
   python3 scripts/cod_risk.py --orders orders-clean.csv --history courier-history.csv
   python3 scripts/cod_risk.py --orders orders-clean.csv --history courier-history.csv --high-value 5000 --json
   python3 scripts/cod_risk.py --orders orders-clean.csv --history courier-history.csv --out scored.csv
   ```
   `--high-value` should match the store's currency and basket size (default 3000, e.g. BDT).
   Prepaid orders are skipped unless `--all`. Exit 1 when high-risk orders exist.
   Rules, points and tuning are in [references/cod-rules.md](references/cod-rules.md).
3. **Recommend actions per level**: high -> phone call plus advance delivery charge (or hold);
   medium -> SMS/WhatsApp confirmation with a reply; low -> ship. Draft the confirmation
   message if asked, but sending messages or cancelling orders is the user's action.
4. **Analyse returns.**
   ```bash
   python3 scripts/return_rate.py --orders order-lines.csv --returns returns.csv
   python3 scripts/return_rate.py --orders order-lines-with-status.csv --json > returns-report.json
   ```
   SKUs are flagged only with `--min-units` (10) sold and a return rate whose Wilson lower bound
   is above the store average. Serial returners: 3+ returned orders, or half of 3+ orders.
5. **Turn findings into fixes** using [references/playbook.md](references/playbook.md): size
   charts and fit notes for size/fit returns, packaging for damage, photo/description fixes
   for "not as described", courier change for one courier's high refusal rate, prepayment
   rules for repeat refusers.
6. **Measure**: track RTO rate and return rate per SKU monthly; re-run with new history and
   compare. Adjust rule points when confirmed-good orders keep scoring high.

## Output

```
COD check: 86 orders - high 4, medium 9, low 73
  70 HIGH  7006 +880161****678  2 earlier refusals, success 1/3 -> call + advance delivery charge
  70 HIGH  7002 +880181****678  test name, 3-char address, disposable email, 6 items, first order 9800
  40 MED   7005 (invalid phone) -> confirm by SMS; fix the number first

Returns (90 days): 14.9% of units, 29% of orders
  TEE-M  28% (33/120), size/fit -> add measured size chart in cm, "runs small" note
  Serial returner ***111: 3 of 4 orders refused -> prepaid only
  By courier: Steadfast 32% vs Pathao 28% (similar; not the main cause)
```
