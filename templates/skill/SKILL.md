---
name: your-skill-name
description: One or two sentences on WHAT the skill does (name the concrete checks, tools and outputs) followed by WHEN to use it. Use when the user asks to ... or mentions ..., ... (list the phrases and file names that should trigger it). Max 1024 characters.
license: MIT
compatibility: Python 3.8+. Mention input formats (CSV export, saved HTML) or platform assumptions here, or delete this line.
metadata:
  author: Your Name
  version: "0.1.0"
---

# Your skill title

One or two sentences on the goal and the main safety rule (for example: read-only first,
every change to the live store confirmed by the user, customer data masked).

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Concrete user requests that should trigger this skill
- Files or error messages that indicate it

## When not to use

- Neighbouring problems and which skill or tool fits them better

## Workflow

1. **Gather context.** Which export or saved page to ask for, platform (WooCommerce, Shopify), market.
2. **Run the helper (read-only).**
   ```bash
   python3 scripts/your_script.py INPUT
   python3 scripts/your_script.py INPUT --json
   ```
3. **Interpret.** Decision points; link details in [references/details.md](references/details.md).
4. **Propose changes** to the store and wait for confirmation before applying any of them.
5. **Verify** with an exact command (re-run the script on a new export).

## Output

A short example of the report the agent should return.
