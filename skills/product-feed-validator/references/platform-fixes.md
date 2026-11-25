# Fixing feed problems at the source

Fix the product data or the feed mapping, then regenerate the feed. Hand-edited feed files are
overwritten on the next sync.

## WooCommerce

Feeds usually come from a plugin (Google Listings & Ads, Product Feed PRO, CTX Feed,
WooCommerce Product Feed and similar). Check the plugin's field mapping screen first.

| Finding | Typical cause | Fix |
| --- | --- | --- |
| `missing_identifiers` | WooCommerce core has a "GTIN, UPC, EAN or ISBN" field since 9.2, but older stores store it in a plugin field | Map the field your store uses; fill it in bulk with a CSV import (back up first) |
| `duplicate_id` | variable products exported with the parent id | Use variation-level ids in the plugin; set `item_group_id` to the parent id |
| `price_format` | currency not appended, or price includes the symbol | Map `price` to "regular price + currency"; map `sale_price` separately |
| `image_placeholder` | product has no featured image | Add images, or exclude these products with a plugin filter |
| `availability_invalid` | custom stock statuses (e.g. "on request") | Map each stock status to a Google value |
| `description_html` / long descriptions | shortcodes or page-builder markup in descriptions | Use the short description or a stripped field |

Useful WP-CLI read-only queries (run on the server, read-only):

```bash
wp wc product list --user=1 --fields=id,sku,name,status --per_page=100
wp post list --post_type=product --meta_key=_thumbnail_id --meta_compare='NOT EXISTS' --fields=ID,post_title
```

## Shopify

Feeds come from the Google & YouTube app or a feed app. Most fixes are product fields.

| Finding | Typical cause | Fix |
| --- | --- | --- |
| `missing_identifiers` | `Barcode` field empty on variants | Fill variant `Barcode` (bulk editor or product CSV `Variant Barcode`) |
| `missing_brand` | `Vendor` empty or set to the supplier | Set `Vendor` to the brand |
| `duplicate_id` | a feed app using the product id instead of variant ids | Use `shopify_<country>_<product id>_<variant id>` ids (the default of the Google app) |
| `title_promo` | "SALE" or "Free shipping" in product titles | Remove from titles; use compare-at prices and Merchant Center promotions |
| `availability_invalid` | "continue selling when out of stock" on | Decide per product; map to `backorder` with `availability_date` or stop overselling |

Product CSV columns that matter: `Title`, `Body (HTML)`, `Vendor`, `Variant SKU`,
`Variant Barcode`, `Variant Price`, `Variant Compare At Price`, `Image Src`, `Google Shopping / *`.

## After fixing

1. Regenerate or re-sync the feed.
2. Run `validate_feed.py` on the new export.
3. In Merchant Center, re-fetch the feed and watch Diagnostics for 24-72 hours.
