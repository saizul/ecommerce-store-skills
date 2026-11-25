# Theme, plugin and app bloat checklist

Tick each item, note evidence (scan output, PageSpeed, admin screen) and the expected metric.

## Both platforms

- [ ] Hero/product image under ~200 KB, served at display size, WebP/AVIF, not lazy-loaded,
      `fetchpriority="high"` (LCP)
- [ ] Every `<img>` has width and height (or aspect-ratio CSS) (CLS)
- [ ] One analytics setup: no duplicate GA4 tags, one heatmap tool at most, pixels via one tag
      manager (INP)
- [ ] Chat widget loads on interaction or after idle, not on every page load (INP)
- [ ] Pop-up and review widgets load only on pages that show them
- [ ] At most 2 font families, `font-display: swap`, self-hosted or preconnected (LCP/CLS)
- [ ] No sliders/carousels above the fold on mobile (LCP)
- [ ] Videos are click-to-play facades, not autoplaying embeds
- [ ] No announcement bars or banners injected late above content (CLS)

## WooCommerce / WordPress

- [ ] Plugin count reviewed: each active plugin has an owner and a reason; remove the unused
- [ ] Plugins load assets only where needed (`page_assets.py` shows per-plugin files; use the
      plugin's own setting, or conditional dequeue with `is_product()`, `is_cart()`,
      `is_checkout()`; asset manager plugins can do this without code)
- [ ] Page builder (Elementor, WPBakery) not used for product templates if the theme's product
      template is lighter
- [ ] Only one slider plugin, and none on product pages
- [ ] jQuery loaded once (`multiple_jquery`); no plugin bundling its own copy
- [ ] Cart fragments (`wc-cart-fragments`) only where a live mini-cart needs it
- [ ] Full-page cache for anonymous visitors (host cache, LiteSpeed Cache, WP Rocket or similar)
      with cart/checkout/my-account excluded
- [ ] Persistent object cache (Redis/Memcached) when the host supports it
- [ ] PHP 8.2+; enough PHP workers for traffic peaks
- [ ] Autoloaded options under ~1 MB (`wp option list --autoload=on --format=total_bytes`)
- [ ] Action Scheduler: no huge backlog of pending/failed actions (WooCommerce > Status > Scheduled Actions)
- [ ] Expired transients and old sessions cleaned (`wp transient delete --expired`)
- [ ] Post revisions limited (`WP_POST_REVISIONS`), spam comments and trashed products emptied
      (after a backup)
- [ ] Image sizes: themes and plugins do not register many unused sizes (each upload creates
      every size)
- [ ] Heartbeat API slowed on the front end; WooCommerce admin not used as a front-end page

## Shopify

- [ ] App list reviewed: each app is used; uninstall the rest
- [ ] Leftover code from uninstalled apps removed (search `theme.liquid`, `snippets/` and
      `layout/` for the app name; old apps injected snippets before app embeds existed)
- [ ] App embeds (Online Store > Themes > Customize > App embeds) disabled for unused apps
- [ ] `page_assets.py` app list (`cdn.shopify.com/extensions/...`, `/apps/...`) matches the apps
      you expect on that template
- [ ] Theme is an Online Store 2.0 theme kept up to date; no heavily modified old theme
- [ ] Sections: product page does not render every section (recommendations, reviews, Instagram
      feed, videos) above the fold
- [ ] Images use `image_url` with `width` and responsive `srcset` (theme `image_tag` filter)
- [ ] No large Liquid loops over all products/collections on every page
- [ ] Shopify's Theme Inspector for Chrome used to find slow Liquid on server-rendered pages
- [ ] Shopify admin's web performance report (Core Web Vitals from real visits) checked after changes

## Third-party scripts worth questioning

| Script | Typical cost | Alternative |
| --- | --- | --- |
| Session recording (Hotjar, Clarity) | INP, main-thread time | sample a % of sessions, run for a limited period |
| Chat widgets | 200-600 KB JS | load on click, or a WhatsApp link |
| Multiple ad pixels | INP | one tag manager, server-side conversions API |
| Review widgets | JS + layout shift | render stars server-side, load the widget below the fold |
| Instagram feed | many images | static images linked to the profile |
