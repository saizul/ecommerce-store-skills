---
name: product-content-writer
description: Writes and rewrites e-commerce product titles, descriptions and bullet points with a proven framework (title formula, benefit-led opening, scannable bullets, specs, sizing/care, objections, FAQ) and scores existing copy 0-100 with a script that checks description length, title length, focus keyword in title and first 100 words, keyword density, Flesch readability and sentence length, bullets, long paragraphs, concrete specs with units, filler phrases, ALL CAPS and duplicate manufacturer descriptions across a WooCommerce or Shopify catalogue export (Bangla text supported, readability skipped). Use when the user asks to write or improve product descriptions, product titles or bullet points, fix thin or duplicate product content, audit product copy across a store, or prepare product pages for SEO and Google Shopping.
license: MIT
compatibility: Python 3.8+ standard library. Works offline on text, HTML or CSV exports.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Product content writer

Write product copy that answers a shopper's questions fast and ranks for what people search,
then score it so improvements are measurable across the whole catalogue.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Write a description for this product", "improve these product titles", "add bullet points"
- Catalogue audits: thin, duplicate or copy-pasted manufacturer descriptions
- Preparing products for Google Shopping (titles) or a new SEO push
- Bilingual stores (English + Bangla) that need consistent product copy

## When not to use

- Feed attribute errors (GTIN, price format): use `product-feed-validator`
- Structured data: use `product-schema`
- Blog posts, category page essays or ad copy: different formats and goals
- Claims you cannot verify (medical, safety, "certified", "waterproof"): ask the user for proof
  before writing them; never invent specs, certifications, reviews or awards

## Workflow

1. **Collect facts before writing.** Ask for (or read from the product data): product type,
   brand, materials, dimensions/weight/capacity, variants, who it is for, use cases, care,
   warranty, delivery/returns promise, real customer questions or reviews, the focus keyword
   and the market/language. Missing facts become questions to the user, not guesses.
2. **Score the current copy (read-only)** so you have a baseline:
   ```bash
   python3 scripts/score_content.py --csv products-export.csv
   python3 scripts/score_content.py --csv products-export.csv --json --min-score 70 > scores.json
   python3 scripts/score_content.py --text description.html --title "Acme Organic Tee" --keyword "organic cotton t-shirt"
   ```
   WooCommerce (`Name`, `Short description`, `Description`) and Shopify (`Title`, `Body (HTML)`)
   columns are detected; a `Focus keyword` / `Keyword` column is used when present, otherwise
   `--keyword`. Lowest scores print first. Exit 1 if any product is below `--min-score` (60).
3. **Prioritise.** Start with best sellers and products with traffic but low conversion, then
   duplicates (`duplicate_of`) and thin pages. Do not rewrite 2,000 products in one go; agree a
   batch with the user.
4. **Write with the framework** in [references/framework.md](references/framework.md):
   - Title: `Brand + product type + key attribute + variant (size/colour/pack)`, keyword near the
     start, 25-90 characters on the page (feeds allow up to 150).
   - Opening (2-3 sentences): who it is for and the main benefit, keyword in the first sentence.
   - 3-7 bullets: benefit first, then the proof/spec ("Keeps drinks cold 24 h - double-wall
     steel").
   - Specs block with units, sizing/fit or compatibility, care, what is in the box.
   - Objection handling: delivery time, returns/exchange, warranty, authenticity.
   - Optional short FAQ from real customer questions.
   Category templates (apparel, electronics, beauty, food, furniture) are in
   [references/templates.md](references/templates.md).
5. **Re-score the new copy** and iterate until it reaches the target (default 70+, A/B grade),
   without stuffing the keyword (density above 3% is flagged).
6. **Hand over, do not publish.** Deliver copy as a table or CSV in the store's import format
   (WooCommerce: `ID`/`SKU`, `Name`, `Short description`, `Description`; Shopify: `Handle`,
   `Title`, `Body (HTML)`). Importing or editing live products happens only after the user
   confirms, with a backup export first.

## Output

```
Baseline: 120 products, average 52; 34 duplicates of supplier text; 41 under 60 words.

TEE-1  48 -> 91
Title: Acme Organic Cotton T-Shirt for Men - Navy, Regular Fit
Short description: Soft 180 gsm organic cotton tee that keeps its shape wash after wash.
Description: (HTML with opening, 5 bullets, specs, sizing, care, delivery/returns)
Open questions for you: shrinkage figure? GOTS certificate number?
```
