---
name: store-speed-audit
description: Speed audit for WooCommerce and Shopify stores focused on what slows real stores down - theme, plugin and app bloat and heavy product images. Scans a saved page for CSS/JS per WordPress plugin and per Shopify app extension, third-party hosts (pixels, chat, heatmaps), render-blocking scripts, duplicate jQuery, WooCommerce cart fragments, web fonts, inline JS, images without width/height, lazy-loaded hero images and DOM size; scans a product image folder for files over a KB budget, oversized dimensions, photos saved as PNG, poorly compressed JPEGs, heavy GIFs, BMP/TIFF, images too small for zoom and duplicates, with estimated savings; then walks a theme/app bloat checklist tied to Core Web Vitals (LCP, INP, CLS). Use when the user says the store or product pages are slow, PageSpeed or Core Web Vitals scores are poor, asks which plugins or apps slow the site, or wants to optimise product images.
license: MIT
compatibility: Python 3.8+ standard library. Works offline on saved HTML and local image folders.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Store speed audit

Find the few things that make a store slow (usually images, apps/plugins and third-party tags),
fix them in order of impact, and confirm with field data.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "My store is slow", "PageSpeed score is 30 on mobile", "LCP/INP/CLS failing in Search Console"
- After installing several plugins/apps or a new theme
- Before a sale or ad campaign
- Bulk product photo uploads that look heavy

## When not to use

- Server-level tuning (PHP workers, MySQL, object cache, nginx): that is hosting work; the
  checklist points to it but this skill does not tune servers
- Checkout friction that is not about speed: use `checkout-cro-audit`
- Rewriting a theme from scratch

## Workflow

1. **Measure first.** Ask for (or have the user run) PageSpeed Insights on the home page, a
   collection/category page and a product page, mobile. Record field data (CrUX: LCP, INP,
   CLS) separately from the lab score. Targets: LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1.
   Note the LCP element PageSpeed names (usually the hero or main product image).
2. **Scan saved pages (read-only).** Save each page's HTML (`curl -sL -A 'Mozilla/5.0' URL -o
   product.html` or browser Save page, HTML only) and run:
   ```bash
   python3 scripts/page_assets.py product.html --site-host shop.example.com
   python3 scripts/page_assets.py home.html --site-host shop.example.com --json > home-assets.json
   ```
   It lists files per WordPress plugin and per Shopify app extension so you can see which
   ones load on pages that do not need them, plus third-party hosts, render-blocking scripts,
   jQuery duplicates, cart fragments, fonts, inline JS, image attributes and DOM size.
3. **Scan product images (read-only)** from a local copy (WordPress: download
   `wp-content/uploads` or a sample year/month folder; Shopify: product images from the admin
   or a CSV of image URLs downloaded by the user):
   ```bash
   python3 scripts/image_weight.py ./uploads --max-kb 250 --max-px 2048
   python3 scripts/image_weight.py ./product-photos --json > images.json
   ```
   WordPress generated sizes (`-300x300.jpg`) are skipped unless `--include-thumbnails`.
   Exit 1 when findings at or above `--fail-on` (medium) exist. The script never modifies files.
4. **Walk the bloat checklist** in [references/bloat-checklist.md](references/bloat-checklist.md)
   (WooCommerce and Shopify sections) for what the scans cannot see: unused plugins/apps,
   leftover app code after uninstall, autoloaded options, sliders and page builders, tag manager
   containers.
5. **Prioritise by impact on the failing metric**: LCP (hero image weight, render-blocking
   CSS/JS, slow server), INP (third-party scripts, heavy JS from apps/page builders), CLS
   (images without dimensions, late banners, font swaps). Image fixes and removing unused
   apps/plugins usually come first. Fix recipes: [references/fixes.md](references/fixes.md).
6. **Propose, do not apply.** Deactivating plugins/apps, theme edits and image
   re-compression are changes to the live store: list them with expected impact and risk, get
   the user's confirmation, and recommend a staging site or duplicate theme plus a backup of
   original images. Never delete originals.
7. **Verify** by re-running PageSpeed (lab) right away and checking field data after 28 days.

## Output

```
Product page (mobile): LCP 4.8 s (hero image), INP 310 ms, CLS 0.18

1. Hero image 1.9 MB, 4000x4000 -> 1600px WebP ~180 KB; remove loading="lazy" from it (LCP)
2. 17 plugins load assets here; revslider, popup-maker, instagram-feed are not used on product
   pages -> load conditionally or remove (LCP/INP)
3. jQuery loaded twice (theme + revslider) (INP)
4. 8 third-party hosts: Hotjar + Clarity both installed, Tawk.to on every page (INP)
5. 20 product thumbnails without width/height (CLS)
Images folder: 1,240 files, 610 MB, est. saving 420 MB; 85 opaque PNG photos.
```
