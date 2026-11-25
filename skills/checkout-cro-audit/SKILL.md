---
name: checkout-cro-audit
description: Checklist-driven conversion audit of an online store's cart and checkout (WooCommerce, Shopify or custom) that ends in a prioritized fix list - scans a saved cart/checkout page for too many fields, forced account creation, wrong email/phone input types, missing autocomplete, placeholder-only labels, CAPTCHA, visible coupon and address-line-2 fields, chat/pop-up/session-recording scripts, missing refund policy or contact links, payment methods and viewport, then scores a 29-item checklist (shipping cost in cart, guest checkout, COD fee clarity, local payment methods like bKash/Nagad, delivery estimate, express pay, error recovery, speed). Use when the user asks why shoppers abandon the cart or checkout, wants a checkout UX/CRO review, sees low checkout conversion, plans to simplify the WooCommerce or Shopify checkout, or asks what to fix first on the checkout page.
license: MIT
compatibility: Python 3.8+ standard library. Works on saved HTML; no network access.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Checkout CRO audit

Find what makes shoppers give up between cart and "Place order", and return a short list of
fixes ordered by impact and effort. Evidence first: the page source, the store's own numbers,
and a walkthrough on a phone.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Lots of add-to-carts but few orders", "checkout conversion is low", "cart abandonment"
- Planning a checkout redesign, switching to WooCommerce Checkout Blocks or a one-page checkout
- A store owner asks "what should I fix first on my checkout?"
- Before running paid traffic to a new store

## When not to use

- Product page content and photos: use `product-content-writer`
- Site-wide speed: use `store-speed-audit` (this skill flags checkout scripts only)
- Payment gateway integration bugs or failing webhooks: debug the gateway logs
- Fraud or fake COD orders: use `returns-and-fraud-signals`

## Workflow

1. **Collect evidence.** Ask for:
   - the funnel numbers if available (sessions, add to cart, reached checkout, orders, per
     device). If checkout-to-order is above about 50% the main problem is earlier in the funnel;
     say so instead of over-optimising the form.
   - saved HTML of the cart and checkout pages with a product in the cart (browser: right click,
     Save page as, "Webpage, HTML only", or DevTools > Elements > Copy outerHTML of `<html>`).
     Shopify checkout pages can only be changed through checkout settings and apps, so focus the
     scan on the cart page there.
   - market and payment context (country, COD share, common wallets).
2. **Scan the pages (read-only).**
   ```bash
   python3 scripts/checkout_audit.py scan checkout.html --site-host shop.example.com
   python3 scripts/checkout_audit.py scan cart.html --site-host shop.example.com --json
   ```
   Exit 1 when findings at or above `--fail-on` (default medium) exist. `--max-fields`
   changes the field budget (default 12).
3. **Walk the checklist.** Print it, then answer each item from the scan, the page and a test
   order on a phone (use a test product or cancel the order afterwards):
   ```bash
   python3 scripts/checkout_audit.py checklist           # human-readable checklist
   python3 scripts/checkout_audit.py checklist --json > answers.json
   ```
   Fill `answers.json` with `yes`, `no`, `partial` or `na`. Details, evidence and platform
   settings for every item are in [references/checklist.md](references/checklist.md).
4. **Score and prioritise.**
   ```bash
   python3 scripts/checkout_audit.py score answers.json
   ```
   P1 items first (they block orders), then P2, then P3. Within a priority prefer low-effort
   fixes (a setting) over high-effort ones (theme changes). Platform-specific how-tos are in
   [references/platform-fixes.md](references/platform-fixes.md).
5. **Propose changes, do not apply them.** Settings, plugin/app changes and theme edits need
   the user's confirmation. Recommend a staging site or a duplicate Shopify theme, and one change
   at a time so the effect can be measured.
6. **Define the measurement.** For each fix, name the metric (checkout-to-order rate, by device)
   and a review date (2-4 weeks, or a proper A/B test if traffic allows).

## Output

```
Checkout audit: shop.example.com (score 58/100)

P1  1. Shipping cost only appears at the last step -> show delivery charge in cart
       (WooCommerce: Shipping > enable shipping calculator; effort: low)
P1  2. 16 fields -> remove company, address 2, second phone, confirm email (effort: low)
P1  3. COD advance charge explained only after "Place order" -> add notice in cart (low)
P2  4. reCAPTCHA v2 on checkout -> switch to invisible/score-based or rate limiting (medium)
P2  5. Tawk.to and a Privy pop-up load on checkout -> exclude /checkout and /cart (low)

Measure: checkout-to-order rate on mobile, before vs 3 weeks after.
```
