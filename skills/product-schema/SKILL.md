---
name: product-schema
description: Generates and validates Product, Offer, AggregateOffer, AggregateRating and Review JSON-LD structured data for e-commerce product pages - builds clean JSON-LD from product data or a WooCommerce/Shopify CSV export, and checks saved page HTML or JSON for missing name/image/offers, price with currency symbols or thousands separators, non-ISO currencies, invalid availability/itemCondition URLs, out-of-range ratings, missing review counts, expired priceValidUntil, bad GTIN check digits and duplicate Product markup from multiple plugins. Use when the user asks about product rich results, price/stars not showing in Google, "Invalid price format" or "Missing field offers" in Search Console, product schema markup, JSON-LD for a product page, or conflicting schema from Yoast, Rank Math, WooCommerce, a Shopify theme or a reviews app.
license: MIT
compatibility: Python 3.8+ standard library. Works offline on saved HTML or JSON.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Product schema (JSON-LD)

Make every product page output exactly one correct Product block with price, currency,
availability and (when real reviews exist) ratings, so it qualifies for product snippets and
merchant listings.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Search Console "Product snippets" or "Merchant listings" errors: "Missing field 'offers'",
  "Invalid price format", "Missing field 'image'", "Either 'offers', 'review' or 'aggregateRating'
  should be specified"
- Stars or price not showing in Google results for product pages
- Writing JSON-LD for a custom theme, headless store or landing page
- Two plugins (theme, SEO plugin, reviews app) printing conflicting Product markup

## When not to use

- Merchant Center feed problems: use `product-feed-validator`
- Organization, Breadcrumb, FAQ or Article markup (out of scope here)
- Fake or incentivised reviews. Never generate `aggregateRating` or `review` that does not come
  from real customer reviews shown on the page; it violates Google's guidelines and can lead to
  a manual action.

## Workflow

1. **Get the page source.** Ask for a saved copy (`curl -sL -A 'Mozilla/5.0' URL -o page.html`
   or browser "Save page"). The page must be the rendered product page; for JavaScript-only
   storefronts ask for the HTML from the browser's DOM (Copy outerHTML) instead.
2. **Validate (read-only).**
   ```bash
   python3 scripts/product_schema.py validate page.html
   python3 scripts/product_schema.py validate page.html --verbose   # include recommendations
   python3 scripts/product_schema.py validate schema.json --json
   ```
   It reads every `<script type="application/ld+json">` block, follows `@graph`, and reports
   errors (block rich results), warnings (likely ignored data) and, with `--verbose`,
   recommendations (brand, sku, gtin, shippingDetails, hasMerchantReturnPolicy).
3. **Find who prints the markup.** For duplicates or wrong values, identify the source before
   fixing; see [references/platforms.md](references/platforms.md) (WooCommerce core, Yoast
   WooCommerce SEO, Rank Math, Shopify `structured_data` filter, review apps).
   Decision: keep one source of truth (usually the SEO plugin or the theme), disable the other.
4. **Generate correct JSON-LD** when the store needs custom markup:
   ```bash
   python3 scripts/product_schema.py generate product.json --script-tag
   python3 scripts/product_schema.py generate products.csv --currency BDT > schema.jsonl
   ```
   Input keys: `name`, `description`, `image` (list or comma-separated), `url`, `sku`, `gtin`,
   `mpn`, `brand`, `price` (any format, normalised to `1250.00`), `currency`, `availability`
   (`in_stock`, `out_of_stock`, `preorder`, `backorder`...), `condition`, `price_valid_until`,
   `rating_value`, `review_count`, `seller`. WooCommerce and Shopify CSV headers are mapped
   automatically. Invalid GTINs stop generation instead of being emitted.
   Field rules and templates (variants, AggregateOffer, shipping, return policy) are in
   [references/google-requirements.md](references/google-requirements.md).
5. **Propose the change** (theme template, plugin setting or snippet) and wait for the user's
   confirmation before editing theme files or plugin settings. Recommend testing on a staging
   copy or a duplicate theme (Shopify) first.
6. **Verify**: re-save the page, re-run `validate`, then ask the user to run Google's Rich
   Results Test on the live URL and request indexing in Search Console.

## Output

```
page.html: 2 JSON-LD blocks, 2 Products, 4 errors
Cause: theme and Rank Math both print Product markup; the theme's copy has price "$1,299.00".
Fix: disable the theme's schema (Theme settings > SEO > Product schema: off), keep Rank Math.
Remaining after fix: add priceCurrency "BDT" in Rank Math > WooCommerce settings.
Recommended: shippingDetails and hasMerchantReturnPolicy (snippet in google-requirements.md).
```
