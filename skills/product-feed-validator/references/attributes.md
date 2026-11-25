# Feed attribute rules used by validate_feed.py

Based on the Google Merchant Center product data specification. Google changes details
over time; when a finding and the Merchant Center diagnostics disagree, trust Merchant Center
and open an issue so the check can be updated.

| Attribute | Rule checked | Code(s) |
| --- | --- | --- |
| `id` | required, max 50 chars, unique across the feed | `missing_id`, `id_too_long`, `duplicate_id` |
| `title` | required, max 150 chars; warning under `--min-title` (25), mostly capitals, promotional words | `title_too_long`, `title_short`, `title_caps`, `title_promo` |
| `description` | required, max 5000 chars; warning if identical to title or under 50 chars; info for HTML | `description_too_long`, `description_is_title`, `description_short`, `description_html` |
| `link` | required, absolute http(s) URL; warning for http | `link_invalid`, `link_http` |
| `image_link` | required, absolute URL; not a placeholder; not SVG | `image_link_invalid`, `image_placeholder`, `image_svg` |
| `additional_image_link` | up to 10, same URL checks | `too_many_images` |
| `availability` | `in_stock`, `out_of_stock`, `preorder`, `backorder`; preorder/backorder need `availability_date` | `availability_invalid`, `availability_format`, `missing_availability_date` |
| `price` | `<number> <ISO 4217>`, e.g. `15.00 USD`, `1200 BDT`; greater than 0 | `price_format`, `price_zero` |
| `sale_price` | same format and currency as price; lower than price | `sale_price_format`, `sale_price_currency`, `sale_price_not_lower` |
| `gtin` | digits only; 8, 12, 13 or 14 digits; valid GS1 check digit; no restricted prefixes (02, 04, 2x, 98, 99 in GTIN-13 form) | `gtin_invalid`, `gtin_restricted`, `gtin_formatting` |
| `brand`, `mpn` | needed when no GTIN unless `identifier_exists=no` | `missing_brand`, `missing_identifiers` |
| `identifier_exists` | `no` must not be combined with a GTIN | `identifier_conflict` |
| `condition` | `new`, `refurbished`, `used` | `condition_invalid`, `missing_condition` |
| `google_product_category` / `product_type` | info when both missing | `missing_category` |
| feed | one currency per feed | `mixed_currencies` |

## GTIN check digit

Take every digit except the last, from right to left, multiply alternately by 3 and 1, sum,
and the check digit is `(10 - sum % 10) % 10`. Example `400638133393?`: the sum is 89, so
the check digit is 1: `4006381333931`.

Common causes of invalid GTINs:

- Spreadsheet stored the barcode as a number: leading zeros dropped (UPC `036000291452`
  becomes `36000291452`, 11 digits) or written as `3.60003E+11`.
- Internal SKUs or supplier codes typed into the GTIN field.
- Made-up numbers to "satisfy" Google. These lead to disapprovals and can affect the account.

## What the validator does not check

- Whether the landing page price/availability matches the feed (crawl mismatch). Check a
  sample of product pages, ideally against their `product-schema` JSON-LD.
- Image content rules (watermarks, promotional overlays, minimum pixel size). Use
  `store-speed-audit`'s image script to list image dimensions locally.
- Shipping and tax settings, which usually live in Merchant Center rather than the feed.
- Country-specific required attributes (for example energy labels in the EU, apparel
  `age_group`, `gender`, `color`, `size` in some countries).
