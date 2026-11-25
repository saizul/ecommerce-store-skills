# AGENTS.md

Guidance for Codex CLI and other coding agents that use or work on this repository.

## Using the skills

The skills live in `skills/<name>/SKILL.md` and follow the Agent Skills format. Codex
discovers them when they are copied to `~/.agents/skills/` or `.agents/skills/` (see
README "Install"). If you are reading this file inside the repository instead:

1. Pick the skill whose `description` matches the user's request:

   | Request is about | Skill |
   | --- | --- |
   | Google Merchant Center feed, GTIN errors, disapproved products | `product-feed-validator` |
   | product structured data, JSON-LD, rich results, price/stars in Google | `product-schema` |
   | cart or checkout conversion, abandonment, checkout UX | `checkout-cro-audit` |
   | product titles, descriptions, bullets, thin or duplicate copy | `product-content-writer` |
   | cleaning order exports, phone numbers, courier uploads, duplicate orders | `order-export-cleanup` |
   | what to reorder, safety stock, days of stock, overstock | `inventory-reorder` |
   | slow store, PageSpeed, plugin/app bloat, heavy images | `store-speed-audit` |
   | fake COD orders, refusals/RTO, return rates | `returns-and-fraud-signals` |

2. Read that `SKILL.md` completely and follow its Workflow section in order.
3. Paths such as `scripts/x.py` and `references/y.md` are relative to the skill folder.
   `${CLAUDE_SKILL_DIR}` in the text means that folder; Codex does not expand it.
4. Read files in `references/` only when a workflow step points to them.

## Safety rules (apply to every skill)

- Run only the read-only scripts and commands a workflow lists without asking. Scripts write
  files only with `--out`; never point `--out` at an input file.
- Do not change the live store (product edits, CSV imports, plugin/app/theme changes, settings,
  order status) without showing the change and getting the user's explicit confirmation.
  Recommend a backup export, a staging site or a duplicate theme first.
- Never send messages to customers, cancel orders or contact couriers on the user's behalf;
  draft messages for the user to send.
- Customer data stays local: do not paste full order rows, phone numbers or emails into chat or
  external tools. Keep script output masked when summarising.
- Never invent product facts, GTINs, reviews, ratings or certifications.
- Risk scores support a human decision; never present them as proof of fraud.

## Working on this repository

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py   # frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

- Scripts: Python 3.8+ standard library only, `#!/usr/bin/env python3`, `argparse` with
  `--help`, `--json` where output is structured, exit 0/1/2 (ok / findings / error).
- Every script needs tests in `tests/test_<skill_with_underscores>.py` with fixtures in
  `tests/fixtures/<skill>/`. Fixtures are synthetic: `example.com` domains, made-up names and
  phone numbers; never commit real customer exports.
- Keep each `SKILL.md` under 400 lines; move detail to `references/`.
- A new skill must be added to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the
  README table, the table above and `CHANGELOG.md`. The validator enforces the manifest.
