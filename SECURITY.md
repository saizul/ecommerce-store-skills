# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

These skills are run by AI agents on real store data (orders with customer details, product
catalogues), so unsafe behaviour and unsafe guidance are treated like code vulnerabilities:

- A script that writes anywhere other than its `--out` file, overwrites an input file, or
  makes a network request
- A script or report that prints unmasked customer phone numbers or emails where masking is
  documented, or leaks other personal data
- A `SKILL.md` workflow that tells the agent to change a live store (imports, settings, theme
  edits, order cancellation), message customers, or share customer data without asking the
  user first
- Crafted input files (CSV, XML, HTML, images) that make a script execute code, read other
  files, or hang (for example XML entity expansion)
- Guidance that would mislead customers or break platform policies (fake reviews or ratings,
  invented GTINs)

A check that misses a problem (false negative) or flags a good input (false positive) is a
normal bug: please open an issue.

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/ecommerce-store-skills/security/advisories/new)
with the affected skill, version, impact and steps to reproduce. Never include real customer
data; build a minimal synthetic example instead.

You will get an answer within 5 working days. Fixes are released as soon as possible and
credited in the changelog unless you prefer otherwise.
