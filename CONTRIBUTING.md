# Contributing to ecommerce-store-skills

Thank you for helping! New checks, new skills, fixes, synthetic test fixtures that reproduce
real-world export quirks, and clearer docs are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Good first issues](#good-first-issues)
- [Development setup](#development-setup)
- [Repository layout](#repository-layout)
- [Write a new skill](#write-a-new-skill)
- [Quality bar](#quality-bar)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Fix a typo, clarify a workflow step, add a FAQ entry |
| 30 minutes | Add a column alias for an export format you use, with a test |
| 1-2 hours | Add a check to an existing script (see below) |
| Half a day | Write a new skill from the template |

Comment on an issue before you start so nobody else picks the same one.

## Good first issues

Each of these is self-contained and touches one script and its test file.

1. **product-feed-validator: apparel attributes.** With `--apparel`, require `color`, `size`,
   `gender` and `age_group`, and check `age_group`/`gender` values.
2. **product-feed-validator: image size from a local folder.** Accept `--images DIR` and use
   `store-speed-audit`'s header reader logic to flag images under 100x100 px.
3. **product-schema: microdata detection.** Report `info` when the page also contains
   `itemtype="https://schema.org/Product"` microdata (double markup).
4. **checkout-cro-audit: Shopify cart page.** Detect dynamic checkout buttons
   (`shopify-payment-button`) and the cart note field; map them to checklist items.
5. **product-content-writer: Shopify `SEO Title` / `SEO Description`.** Score meta title and
   description length when those CSV columns exist.
6. **order-export-cleanup: Dhaka area lookup.** Map common Dhaka areas (Mirpur, Uttara,
   Dhanmondi, Gulshan, Mohammadpur...) to district Dhaka so they stop showing `district_unknown`.
7. **order-export-cleanup: WooCommerce `BD-xx` state codes.** Map ISO 3166-2:BD codes to
   district names.
8. **inventory-reorder: per-SKU service level.** Read an optional `service_level` column in the
   stock file.
9. **store-speed-audit: `srcset` check.** Flag large images without `srcset`/`sizes`.
10. **returns-and-fraud-signals: Bangla reasons.** Add Bangla keywords to the reason categories
    (for example সাইজ, ভাঙা, ভুল পণ্য).
11. **returns-and-fraud-signals: rules file.** Let `cod_risk.py --rules rules.json` override
    rule points, with validation.
12. **New skill: `meta-catalog-validator`** (see the roadmap in the README).

## Development setup

```bash
git clone https://github.com/saizul/ecommerce-store-skills.git
cd ecommerce-store-skills
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python tools/validate_skills.py   # SKILL.md frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

To try your changes in Claude Code, either copy a skill to `~/.claude/skills/` or add your
checkout as a local marketplace:

```bash
claude plugin marketplace add ./ecommerce-store-skills
claude plugin install ecommerce-store-skills@ecommerce-store-skills
```

For Codex, copy the skill folder to `~/.agents/skills/`.

## Repository layout

```
.claude-plugin/
  marketplace.json      marketplace + plugin entry listing every skill
  plugin.json           plugin manifest (name, version, author)
skills/<name>/
  SKILL.md              frontmatter + workflow (the part agents read)
  scripts/*.py          standalone helpers, Python 3.8+ stdlib only
  references/*.md       detail loaded on demand
templates/skill/        copy this to start a new skill
tests/
  test_<skill>.py       one test module per skill
  fixtures/<skill>/     synthetic inputs for those tests
tools/validate_skills.py
```

## Write a new skill

1. Open a "New skill proposal" issue first so we can agree on scope.
2. Copy the template:
   ```bash
   cp -r templates/skill skills/my-new-skill
   mv skills/my-new-skill/scripts/your_script.py skills/my-new-skill/scripts/my_check.py
   ```
3. Edit `SKILL.md`:
   - `name` equals the folder name: lowercase letters, digits, single hyphens, max 64 chars.
   - `description` (max 1024 chars) says **what** it does with concrete keywords and **when**
     to use it, starting the second part with "Use when ...". This text decides whether
     the agent picks the skill, so list the phrases store owners actually type.
   - Required sections: `## When to use`, `## When not to use`, `## Workflow`, `## Output`.
   - Workflow steps are imperative and numbered, with exact commands, decision points and
     the point where the agent must ask before changing anything in the store.
   - Keep it under 400 lines; move tables, checklists and platform how-tos to `references/`.
4. Write the script: `argparse` with a useful `--help`, `--json` output, exit codes
   0 (ok) / 1 (findings) / 2 (error), read-only by default (write only with `--out`), no
   network access, mask customer identifiers in output.
5. Add `tests/test_my_new_skill.py` and fixtures in `tests/fixtures/my-new-skill/`. Cover
   a "bad" input, a "good" input that produces no findings, edge cases and the CLI exit codes.
6. Add the skill to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the README
   skills table, the table in `AGENTS.md` and `CHANGELOG.md` under "Unreleased".
7. Run the validator, ruff and pytest.

## Quality bar

- **Safety first.** A skill never tells the agent to change a live store, message customers or
  share customer data without the user's confirmation.
- **Deterministic where it matters.** If a step is "parse this export and find X", write a
  script and test it rather than relying on the model reading a 5,000-row CSV.
- **Synthetic fixtures only.** Never commit real exports. Use `example.com`, made-up names and
  numbers like `01712345678`; reproduce the quirk (Excel-mangled phones, Shopify line rows),
  not the customer.
- **Platform aware.** Name the exact WooCommerce and Shopify setting or column; say when
  something only applies to one platform.
- **Low false positives.** If a check is often wrong, make it `info` or drop it, and document
  known false positives in the skill's references.

## Pull request process

1. Fork, create a branch, make focused commits.
2. Make sure CI passes locally (validator, ruff, pytest).
3. Fill in the pull request template.
4. A maintainer reviews within a few days. Small, focused pull requests are merged fastest.

By contributing you agree that your contributions are licensed under the MIT License.
