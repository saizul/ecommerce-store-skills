# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-25

### Added

- `product-feed-validator`: Google Merchant Center feed validator for CSV/TSV and RSS/Atom XML:
  required attributes, GTIN length/check digit/restricted prefixes, price and sale_price format,
  availability and availability_date, image/link URLs, title and description limits, promo text,
  duplicate ids, identifier_exists conflicts, mixed currencies.
- `product-schema`: Product/Offer/AggregateRating JSON-LD generator (JSON or WooCommerce/Shopify
  CSV) and validator for saved HTML/JSON, including duplicate markup detection and ProductGroup
  variants.
- `checkout-cro-audit`: cart/checkout HTML scanner and a 29-item prioritized checklist scorer.
- `product-content-writer`: copy framework, category templates and a 0-100 description scorer
  with Bangla support and duplicate-copy detection.
- `order-export-cleanup`: order CSV normaliser with Bangladesh +880 phone rules, 64-district
  mapping, postcode checks, COD flags, Shopify line-item merge and duplicate detection.
- `inventory-reorder`: reorder point, safety stock, days of stock and purchase-order calculator
  with MOQ and case-pack rounding.
- `store-speed-audit`: page asset/bloat scanner (WordPress plugins, Shopify app extensions,
  third-party hosts, render-blocking JS, image attributes) and product image weight audit.
- `returns-and-fraud-signals`: rule-based COD risk scoring with delivery history and return-rate
  analysis by SKU (Wilson bound), reason, customer, district and courier.
- Claude Code plugin marketplace manifest, `tools/validate_skills.py`, CI and release workflows.

[Unreleased]: https://github.com/saizul/ecommerce-store-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/ecommerce-store-skills/releases/tag/v0.1.0
