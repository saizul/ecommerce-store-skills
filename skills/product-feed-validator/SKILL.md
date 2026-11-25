---
name: product-feed-validator
description: Validates a Google Merchant Center product feed (CSV, TSV or RSS/Atom XML from WooCommerce, Shopify or any feed plugin) before upload - required attributes, GTIN length and check digit, restricted GTIN prefixes, price and sale_price format, availability values and availability_date, image and landing page URLs (https, placeholders, SVG), title and description length, promotional text, duplicate ids, identifier_exists conflicts and mixed currencies - and explains how to fix each problem at the source. Use when the user mentions Merchant Center disapprovals, "invalid GTIN", "missing value [price]", product feed errors, Google Shopping feed, a feed file to check, or wants to audit a product feed export.
license: MIT
compatibility: Python 3.8+ standard library. Works offline on a local feed file.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Product feed validator

Find the feed problems that get products disapproved or limited in Google Merchant Center,
then fix them where the data comes from (the product in WooCommerce/Shopify or the feed plugin
mapping), not by hand-editing the exported file.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Merchant Center disapproved 300 products", "invalid GTIN", "missing value [image_link]"
- Before submitting a new feed or after changing a feed plugin, theme or product import
- The user has a feed URL or file (`.xml`, `.csv`, `.tsv`, `.txt`) from WooCommerce Product Feed
  plugins, Shopify's Google & YouTube app, or a custom export
- Comparing two feeds (old vs new export) for regressions

## When not to use

- Structured data on product pages (JSON-LD): use `product-schema`
- Writing better titles and descriptions: use `product-content-writer` (this skill only checks
  limits and obvious problems)
- Account-level suspensions (misrepresentation, policy): review the store's policies, contact
  details and checkout instead; no feed fix solves those

## Workflow

1. **Get the feed.** Ask for the file path. If the user only has a feed URL, ask them to download
   it (`curl -o feed.xml 'https://...'`) so the check runs on a local copy. Note the target country
   and currency.
2. **Run the validator (read-only).**
   ```bash
   python3 scripts/validate_feed.py feed.xml
   python3 scripts/validate_feed.py products.tsv --fail-on warning
   python3 scripts/validate_feed.py products.csv --json > feed-report.json
   ```
   Format is detected automatically (XML if the file starts with `<`, otherwise tab- or
   comma-delimited with a header row; `g:` prefixes are ignored). Exit 1 when findings at or
   above `--fail-on` (default `error`) exist.
3. **Triage by impact.** Errors disapprove items: fix those first, largest count first.
   Warnings limit performance (missing brand/identifiers, promo text, short titles). Info is
   context. Use [references/attributes.md](references/attributes.md) for the rules behind each
   code.
4. **Find the source of each problem** and propose fixes there:
   - GTIN errors: wrong or made-up barcodes. Never invent GTINs; for own-label or handmade goods
     set `identifier_exists=no` and provide brand + mpn where possible.
   - Price format: feed plugin outputs `$29.99` or omits the currency; fix the plugin's
     price field mapping (`price` + space + ISO currency code).
   - Placeholder images: products without a featured image in WooCommerce
     (`woocommerce-placeholder.png`) or Shopify; list the ids so the user can add photos or
     exclude them from the feed.
   - Availability: map stock status to `in_stock`, `out_of_stock`, `preorder`, `backorder`;
     preorder/backorder need `availability_date`.
   - Duplicate ids: variants exported with the parent id; switch the plugin to variant-level
     ids (`SKU` or `{parent}-{variation}`).
   See [references/platform-fixes.md](references/platform-fixes.md) for WooCommerce and Shopify
   specifics.
5. **Ask before changing anything.** Do not edit products, plugin settings or the live feed
   without the user's confirmation. Bulk edits (CSV re-import) need a backup export first.
6. **Re-run the validator** on the new export and compare counts.

## Output

```
Feed: products.tsv (1,240 items, 212 with errors)

Fix first (errors)
1. gtin_invalid x140 - check digit wrong on Acme imports; supplier sheet has 12-digit UPCs
   stored as numbers (leading zero lost). Fix in the import, then re-sync.
2. image_placeholder x51 - products without a featured image. Ids: ...
3. price_format x21 - variation prices exported without currency.

Then (warnings)
- missing_brand x300: set brand = "Acme" for own-label products in the feed plugin.

Verification: python3 scripts/validate_feed.py new-export.tsv -> 0 errors.
```
