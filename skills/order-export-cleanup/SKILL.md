---
name: order-export-cleanup
description: Cleans WooCommerce and Shopify order CSV exports so they can go to a courier, CRM, SMS tool or spreadsheet - normalises phone numbers to E.164 with built-in Bangladesh +880 rules (01XXXXXXXXX, 880, 0088, Bangla digits, Excel scientific-notation damage, multiple numbers in one field, operator detection), tidies names and addresses, maps Bangladesh city spellings (Chittagong, Comilla, Bogra, Jessore, Barisal) to the 64 official districts, checks 4-digit postcodes, flags cash-on-delivery orders, merges Shopify line-item rows, drops exact duplicate rows and flags likely duplicate orders (same phone and total within 24 hours). Dry run by default with masked phone numbers. Use when the user has an order export to clean, needs courier-ready data (Pathao, Steadfast, RedX, Paperfly), sees broken or duplicate phone numbers, wants COD orders separated, or asks to deduplicate orders.
license: MIT
compatibility: Python 3.8+ standard library. Runs locally on the CSV; nothing is uploaded.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Order export cleanup

Turn a messy order export into a clean, deduplicated file with valid phone numbers, districts
and COD flags, without losing or changing the original export.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Clean this order export", "fix the phone numbers before I upload to the courier"
- Phone numbers that lost the leading zero or show as `1.71234E+09` after opening in Excel
- Duplicate orders from customers pressing "Place order" twice
- Splitting COD and prepaid orders, or counting orders per district
- Shopify exports with one row per line item that need one row per order

## When not to use

- Scoring which COD orders are risky: use `returns-and-fraud-signals` (run this cleanup first)
- Changing orders in the store itself (status, notes): do that in WooCommerce/Shopify admin
- Accounting or tax reports: use the platform's reports or an accounting export

## Privacy

Order exports contain personal data. Work on a local copy, never paste full rows into chat or
external tools, keep reports masked (the script masks phone numbers as `+880171****678`), and
delete working copies when done. Do not commit exports to git.

## Workflow

1. **Get the export.** WooCommerce: Orders > Export (or an export plugin) as CSV. Shopify:
   Orders > Export > CSV for Excel, Numbers or other spreadsheet programs. Ask the user not to
   open and re-save it in Excel first (that is what corrupts phone numbers).
2. **Dry run (writes nothing).**
   ```bash
   python3 scripts/clean_orders.py orders.csv
   python3 scripts/clean_orders.py orders.csv --json > cleanup-report.json
   ```
   Check the detected `columns` in the JSON. If a column is wrong or missing, map it:
   `--map phone="Shipping Phone" --map total="Order Total Amount"`. Non-Bangladesh stores set
   `--country IN` (or another ISO code); a per-row country column overrides it.
3. **Review the report with the user.** Explain counts: exact duplicates dropped, line rows
   merged, invalid phones, possible duplicates, COD share, operator split. Decide together:
   - `phone_invalid` / `phone_excel_corrupted`: get the number from the order in the admin or
     call/SMS the customer; a corrupted export cannot be recovered from the CSV.
   - `possible_duplicate`: same phone and same total within `--dup-hours` (24). Confirm with
     the customer before cancelling either order.
   - `district_unknown`: the courier needs a district/area; check the address.
   Phone and district rules are in [references/bd-rules.md](references/bd-rules.md).
4. **Write the cleaned copy.**
   ```bash
   python3 scripts/clean_orders.py orders.csv --out orders-clean.csv
   ```
   Original columns are kept (names/addresses tidied) and these are added: `phone_e164`,
   `phone_valid`, `phone_operator`, `district`, `is_cod`, `total_clean`, `duplicate_of`, `issues`.
   The script refuses to overwrite the input file.
5. **Prepare the next step** if asked: filter `is_cod=yes` for COD confirmation calls, map to the
   courier's bulk upload template (see [references/courier-templates.md](references/courier-templates.md)),
   or pass the file to `returns-and-fraud-signals`.

## Output

```
482 rows -> 455 orders (3 exact duplicate rows dropped, 24 line rows merged)
valid phones 441/455, COD 389 (85.5%)
issues: district_unknown 9, phone_invalid 8, possible_duplicate 6, phone_excel_corrupted 6
  - 10233 (none): phone_excel_corrupted   -> re-export; do not open in Excel first
  - 10240 +880171****678: possible_duplicate (duplicate of 10239) -> confirm with customer
Written: orders-clean.csv (original file untouched)
```
