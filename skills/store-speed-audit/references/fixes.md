# Fix recipes

Apply on staging or a duplicate theme first, keep original images, and change one thing at a
time so the effect is visible.

## Images

| Finding (image_weight.py) | Fix |
| --- | --- |
| `over_budget`, `oversized` | Resize to the largest display size (product zoom usually 1600-2048 px) and re-encode. Typical product photo: 100-250 KB as JPEG q75-85, less as WebP/AVIF |
| `png_photo` | Convert opaque PNG photos to JPEG or WebP; keep PNG only for transparency or line art |
| `poor_compression` | Re-encode at quality 75-85 (mozjpeg, Squoosh, ImageMagick `-quality 82 -strip`) |
| `heavy_gif` | Convert to MP4/WebM (`<video autoplay muted loop playsinline>`) or a static image |
| `not_web_format` | Export BMP/TIFF as JPEG/WebP before uploading |
| `too_small`, `small_for_zoom` | Re-upload from the original photo; Merchant Center needs at least 100x100 px (250x250 for apparel) |
| `duplicate` | Same file uploaded several times; reuse one media item |

Batch commands (run on a copy, never on the only originals):

```bash
# ImageMagick 7: write resized, re-encoded copies (max 2048 px) to ./optimized
mkdir -p optimized
magick mogrify -resize '2048x2048>' -strip -quality 82 -path ./optimized ./copy/*.jpg
# libwebp
for f in ./copy/*.jpg; do cwebp -q 80 "$f" -o "./optimized/$(basename "${f%.*}").webp"; done
```

WordPress: an image optimisation plugin or an image CDN can convert and serve WebP/AVIF and
resize on the fly; regenerate thumbnails after changing sizes. Shopify: its CDN already serves
WebP/AVIF and resizes by `width`; the fix is mostly uploading reasonably sized originals and
using responsive `image_tag` output in the theme.

## Plugin / app assets

- WooCommerce: dequeue a plugin's assets where not needed:
  ```php
  add_action( 'wp_enqueue_scripts', function () {
      if ( ! is_page( 'contact' ) ) {
          wp_dequeue_script( 'contact-form-7' );
          wp_dequeue_style( 'contact-form-7' );
      }
  }, 100 );
  ```
  Handles are visible in the page source as `id="<handle>-js"` / `id="<handle>-css"`.
- Cart fragments: if the theme's mini-cart does not need live updates on every page, dequeue
  `wc-cart-fragments` outside cart/checkout or use the theme option that disables it.
- Shopify: disable the app embed, then remove leftover snippets (`{% render 'app-name' %}`)
  from the duplicate theme, preview, publish.

## Render-blocking and third-party JS

- Add `defer` to non-critical scripts (WordPress 6.3+ supports a loading strategy in
  `wp_enqueue_script`), or use the caching plugin's "delay JS until interaction" with an
  exclusion list for checkout and payment scripts.
- Move pixels into one tag manager container; remove duplicates.
- Load chat on click (a static button that injects the widget).

## Layout shift

- Add `width`/`height` to `<img>` (WordPress does this for images inserted through the editor;
  theme templates and page builders sometimes do not).
- Reserve space for banners, review stars and sticky bars with CSS `min-height`.
- Preload the main font file or use `font-display: optional` for body text.
