## What does this pull request do?

<!-- One or two sentences. Link the issue: "Closes #123". -->

## Type

- [ ] New skill
- [ ] New check or option in an existing script
- [ ] Workflow / reference improvement
- [ ] Bug fix
- [ ] Repository tooling (validator, CI)

## Checklist

- [ ] `python tools/validate_skills.py` passes
- [ ] `ruff check . && ruff format --check .` passes
- [ ] `pytest` passes; new script behaviour has tests with fixtures in `tests/fixtures/<skill>/`
- [ ] Scripts use only the Python standard library (or POSIX shell), support `--help`, have a
      `--json` option where output is structured, and exit non-zero on findings
- [ ] Read-only by default (files written only with `--out`, never over the input); any change to
      a live store is shown to the user and needs confirmation in the SKILL.md workflow
- [ ] Customer identifiers are masked in script output
- [ ] Fixtures are synthetic: no real customer exports, names, phone numbers, emails or API keys
      (use example.com and made-up data)
- [ ] New skills: listed in `.claude-plugin/marketplace.json`, the README skills table and CHANGELOG.md
