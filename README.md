# ecommerce-store-skills

[![CI](https://github.com/saizul/ecommerce-store-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/ecommerce-store-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/saizul/ecommerce-store-skills?sort=semver)](https://github.com/saizul/ecommerce-store-skills/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/saizul/ecommerce-store-skills?style=social)](https://github.com/saizul/ecommerce-store-skills/stargazers)

**Agent Skills that help Claude Code and Codex run and improve online stores: fix feeds and schema, audit checkout and speed, clean orders, plan stock and cut COD losses.**

Eight skills for the jobs every WooCommerce or Shopify store owner (and the developer they
call) keeps doing by hand. Each skill is a step-by-step workflow plus a tested,
standard-library-only Python script, so the agent works from exact numbers instead of
guessing. Most work platform-agnostic on CSV, XML and saved HTML; Bangladesh specifics
(+880 phones, 64 districts, COD, bKash/Nagad) are built in where they matter.

- **Read-only by default.** Scripts read exports and saved pages and print reports. They
  never call store APIs, never edit products and never send messages. Anything that changes
  the live store is proposed and needs your confirmation.
- **Private by default.** Customer phone numbers and emails are masked in every report;
  nothing is uploaded anywhere.
- **Tested.** 130+ tests with synthetic fixtures, run on Python 3.11-3.13 in CI.
- **No dependencies.** Python 3.8+ standard library only. Copy a script anywhere and run it.

## Skills

| Skill | What it does | Try asking |
| --- | --- | --- |
| [product-feed-validator](skills/product-feed-validator/SKILL.md) | Validates a Google Merchant Center feed (CSV/TSV/XML): required attributes, GTIN check digits, price and sale_price format, availability, image/link URLs, title/description limits, duplicate ids, identifier_exists | "Merchant Center disapproved 300 products, here's the feed" |
| [product-schema](skills/product-schema/SKILL.md) | Generates Product/Offer/AggregateRating JSON-LD and validates saved pages: price format, currency, availability URLs, rating ranges, expired priceValidUntil, duplicate markup from two plugins | "Why aren't price and stars showing in Google for my products?" |
| [checkout-cro-audit](skills/checkout-cro-audit/SKILL.md) | Scans cart/checkout HTML (fields, forced accounts, input types, autocomplete, CAPTCHA, pop-ups, policy links) and scores a 29-item checklist into a prioritized fix list | "Lots of add-to-carts, few orders. What should I fix on checkout?" |
| [product-content-writer](skills/product-content-writer/SKILL.md) | Title/description/bullets framework and a 0-100 scorer: length, keyword use, readability, bullets, specs, filler, duplicate supplier copy (Bangla aware) | "Rewrite my 20 best sellers' descriptions and show before/after scores" |
| [order-export-cleanup](skills/order-export-cleanup/SKILL.md) | Normalises order CSVs: phones to E.164 (+880 rules, Excel damage, Bangla digits), districts, postcodes, COD flags, Shopify line-item merge, duplicate orders | "Clean this WooCommerce export before I upload it to the courier" |
| [inventory-reorder](skills/inventory-reorder/SKILL.md) | Reorder points, safety stock, days of stock, stockout dates and PO quantities (MOQ, case pack) from sales history; flags overstock and dead stock | "What do I need to reorder this week and how much?" |
| [store-speed-audit](skills/store-speed-audit/SKILL.md) | Per-plugin / per-app asset bloat, third-party tags, render-blocking JS, jQuery duplicates, CLS/LCP image issues, plus an image-folder weight audit with savings | "My product pages score 30 on mobile. What's slowing them down?" |
| [returns-and-fraud-signals](skills/returns-and-fraud-signals/SKILL.md) | Transparent COD risk rules (refusal history, fake names, invalid phones, repeat orders) and return-rate analysis by SKU, reason, customer, district and courier | "We get too many fake COD orders and refusals. Which orders should we call?" |

## Install

### Claude Code: plugin marketplace (recommended)

```text
/plugin marketplace add saizul/ecommerce-store-skills
/plugin install ecommerce-store-skills@ecommerce-store-skills
```

Or from your shell:

```bash
claude plugin marketplace add saizul/ecommerce-store-skills
claude plugin install ecommerce-store-skills@ecommerce-store-skills
```

Plugin skills are namespaced, e.g. `/ecommerce-store-skills:product-feed-validator`. Claude
also picks them up automatically when your request matches a skill's description. Update
later with `/plugin marketplace update ecommerce-store-skills`.

### Claude Code: copy the skills

```bash
git clone https://github.com/saizul/ecommerce-store-skills.git
# all projects (personal skills)
mkdir -p ~/.claude/skills && cp -r ecommerce-store-skills/skills/* ~/.claude/skills/
# or just one project
mkdir -p .claude/skills && cp -r ecommerce-store-skills/skills/order-export-cleanup .claude/skills/
```

Each release also has one zip per skill and an all-skills zip under
[Releases](https://github.com/saizul/ecommerce-store-skills/releases).

### Codex CLI

Codex reads skills from `~/.agents/skills` (all repositories) and `.agents/skills` in a
repository (from the current directory up to the repository root):

```bash
git clone https://github.com/saizul/ecommerce-store-skills.git
mkdir -p ~/.agents/skills && cp -r ecommerce-store-skills/skills/* ~/.agents/skills/
```

Codex also ships a `$skill-installer` skill that can install skills from a GitHub repository;
ask it to install from `saizul/ecommerce-store-skills`. Skill locations and the installer are
described in the [Codex skills documentation](https://developers.openai.com/codex/skills);
check it if your Codex version behaves differently. [AGENTS.md](AGENTS.md) explains how
Codex and other agents should use these skills.

### Any other agent

The skills follow the open [Agent Skills format](https://agentskills.io/specification):
a folder with `SKILL.md` (YAML frontmatter + instructions), `scripts/` and `references/`.
Point your agent at the folder, or run the scripts yourself; every script has `--help`.

## Usage examples

```text
> Here's products.tsv from our feed plugin. Merchant Center says "invalid GTIN" on half of it.
  (Runs validate_feed.py, finds UPCs that lost their leading zero in a spreadsheet and
   placeholder images on 51 products, and explains where to fix each in WooCommerce.)

> orders.csv is today's export. Clean it for Steadfast and tell me which COD orders to call.
  (order-export-cleanup normalises phones and districts, flags 3 duplicates, then
   returns-and-fraud-signals scores COD orders against last month's courier report.)

> Our checkout converts badly on mobile. I saved checkout.html.
  (Scans the page, walks the checklist with you, and returns P1/P2/P3 fixes with the
   WooCommerce or Shopify setting for each.)
```

Run the scripts directly too:

```bash
python3 skills/product-feed-validator/scripts/validate_feed.py feed.xml --fail-on warning
python3 skills/product-schema/scripts/product_schema.py validate product-page.html
python3 skills/order-export-cleanup/scripts/clean_orders.py orders.csv --out orders-clean.csv
python3 skills/inventory-reorder/scripts/reorder.py --sales sales.csv --stock stock.csv --out po.csv
python3 skills/store-speed-audit/scripts/image_weight.py ./wp-content/uploads/2026 --max-kb 250
python3 skills/returns-and-fraud-signals/scripts/cod_risk.py --orders orders-clean.csv --history courier.csv
```

## How skills work

At startup the agent loads only each skill's `name` and `description` (about 100 tokens
each). When your request matches a description, it reads that skill's `SKILL.md`: the
workflow, decision points and safety rules. Longer material lives in `references/` and is
read only when a step needs it. Scripts run as normal commands, so their output is exact
and repeatable.

```
skills/<skill-name>/
  SKILL.md          frontmatter (name, description) + workflow
  scripts/          standalone Python 3 helpers (stdlib only, --help, --json)
  references/       checklists, platform how-tos, formulas, templates
```

## FAQ

**Does it connect to my store?**
No. Skills work on exports and saved pages you provide (CSV, XML, HTML, image folders). That
keeps them platform-agnostic, safe to run on any machine and free of API keys.

**Will the agent change products or orders on its own?**
The skills instruct it not to. Scripts only write new files when you pass `--out`, and refuse
to overwrite their input. Imports, setting changes, theme edits, messages to customers and
order cancellations are always proposed for you to confirm. Your agent's own permission
settings still apply on top.

**What about customer data?**
Order exports contain personal data. Reports mask phones (`+880171****678`) and emails, the
scripts never send anything over the network, and `.gitignore` keeps stray CSV exports out
of commits. Delete working copies when you are done.

**I'm not in Bangladesh. Is this useful?**
Yes. Feed, schema, checkout, content, inventory, speed and returns analysis are market
independent. Phone normalisation takes `--country` (or a country column) for other markets;
the Bangladesh rules (+880, districts, COD/bKash) are extras.

**Is the COD risk score "AI fraud detection"?**
No, deliberately. It is a short list of documented rules with points you can read, explain to
staff and tune. High risk means "confirm first", never "cancel automatically".

## Roadmap

Ideas for new skills (great first contributions; see [CONTRIBUTING.md](CONTRIBUTING.md)):

- `meta-catalog-validator` - Facebook/Instagram catalog feed checks (similar to the GMC validator)
- `shipping-rate-review` - compare zone/weight rates with actual courier invoices
- `discount-margin-check` - flag coupons and sale prices that push margin below a floor
- `review-request-planner` - timing and templates for post-delivery review requests
- `abandoned-cart-sequences` - consent-aware email/SMS/WhatsApp reminder templates and timing
- `product-image-checklist` - background, angles, zoom and alt text rules per category
- `bangla-product-seo` - Bangla keyword variants and transliteration for product pages
- `pricing-elasticity-lite` - before/after price change analysis from order exports

## Contributing

Contributions are welcome: new checks, new skills, fixes and better docs. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the skill template, the quality bar and
how to run the validator and tests:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py && ruff check . && ruff format --check . && pytest
```

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report security issues
privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) (c) Saizul Amin
