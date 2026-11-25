#!/usr/bin/env python3
"""Find theme, plugin and app bloat in a saved store page (WooCommerce, Shopify or other).

Parses saved HTML and reports: scripts and stylesheets per WordPress plugin and per Shopify
app/extension, third-party hosts, render-blocking scripts in <head>, several jQuery copies,
WooCommerce cart fragments, web fonts, inline script/style weight, images without width and
height (layout shift), lazy-loaded first images (slow LCP), missing fetchpriority on the
hero image, and DOM size. Read-only; nothing is fetched.

Exit codes: 0 = no findings at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlparse

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}
KNOWN_HOSTS = {
    "www.googletagmanager.com": "Google Tag Manager / gtag",
    "www.google-analytics.com": "Google Analytics",
    "connect.facebook.net": "Meta pixel",
    "analytics.tiktok.com": "TikTok pixel",
    "static.hotjar.com": "Hotjar",
    "www.clarity.ms": "Microsoft Clarity",
    "embed.tawk.to": "Tawk.to chat",
    "widget.intercom.io": "Intercom",
    "code.tidio.co": "Tidio chat",
    "static.klaviyo.com": "Klaviyo",
    "widget.privy.com": "Privy",
    "cdn.judge.me": "Judge.me reviews",
    "loox.io": "Loox reviews",
    "static.zdassets.com": "Zendesk",
    "fonts.googleapis.com": "Google Fonts",
    "fonts.gstatic.com": "Google Fonts",
    "use.typekit.net": "Adobe Fonts",
    "cdn.jsdelivr.net": "public CDN",
    "cdnjs.cloudflare.com": "public CDN",
    "maps.googleapis.com": "Google Maps",
    "www.youtube.com": "YouTube embed",
    "player.vimeo.com": "Vimeo embed",
}
WP_PLUGIN_RE = re.compile(r"/wp-content/plugins/([^/?#]+)/")
WP_THEME_RE = re.compile(r"/wp-content/themes/([^/?#]+)/")
SHOPIFY_EXT_RE = re.compile(r"cdn\.shopify\.com/extensions/([^/?#]+)/")
SHOPIFY_PROXY_RE = re.compile(r"/apps/([^/?#]+)")


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_head = True
        self.scripts: list[dict] = []
        self.styles: list[str] = []
        self.images: list[dict] = []
        self.fonts: list[str] = []
        self.preloads: list[dict] = []
        self.inline_js = 0
        self.inline_css = 0
        self.tags = 0
        self._stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        self.tags += 1
        if tag == "body":
            self.in_head = False
        if tag == "script":
            self._stack.append("script")
            src = a.get("src", "")
            t = a.get("type", "").lower()
            if src:
                self.scripts.append(
                    {
                        "src": src,
                        "head": self.in_head,
                        "async": "async" in a or "defer" in a or t == "module",
                        "id": a.get("id", ""),
                    }
                )
        elif tag == "style":
            self._stack.append("style")
        elif tag == "link":
            rel = a.get("rel", "").lower()
            href = a.get("href", "")
            if "stylesheet" in rel and href:
                self.styles.append(href)
                if "fonts.googleapis.com" in href or "typekit" in href:
                    self.fonts.append(href)
            if "preload" in rel:
                self.preloads.append(a)
                if a.get("as") == "font":
                    self.fonts.append(href)
        elif tag == "img":
            self.images.append(
                {
                    "src": a.get("src") or a.get("data-src", ""),
                    "width": a.get("width"),
                    "height": a.get("height"),
                    "loading": a.get("loading", "").lower(),
                    "fetchpriority": a.get("fetchpriority", "").lower(),
                }
            )

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if self._stack and tag == self._stack[-1]:
            self._stack.pop()

    def handle_data(self, data):
        if self._stack and self._stack[-1] == "script":
            self.inline_js += len(data.encode())
        elif self._stack and self._stack[-1] == "style":
            self.inline_css += len(data.encode())


def analyse(html: str, site_host: str = "", max_dom: int = 1500) -> dict:
    c = Collector()
    c.feed(html)
    findings: list[dict] = []

    def add(sev, code, message, items=None):
        findings.append({"severity": sev, "code": code, "message": message, "items": items or []})

    urls = [s["src"] for s in c.scripts] + c.styles
    plugins = Counter(m.group(1) for u in urls for m in [WP_PLUGIN_RE.search(u)] if m)
    themes = sorted({m.group(1) for u in urls for m in [WP_THEME_RE.search(u)] if m})
    shop_ext = Counter(m.group(1) for u in urls for m in [SHOPIFY_EXT_RE.search(u)] if m)
    shop_proxy = Counter(m.group(1) for u in urls for m in [SHOPIFY_PROXY_RE.search(u)] if m)
    own = site_host.lower().lstrip(".")
    hosts = Counter()
    for u in urls:
        host = urlparse(u if not u.startswith("//") else "https:" + u).netloc.lower()
        if (
            host
            and not (own and (host == own or host.endswith("." + own)))
            and not host.endswith("cdn.shopify.com")
        ):
            hosts[host] += 1

    if plugins:
        heavy = [f"{p} ({n} files)" for p, n in plugins.most_common() if n >= 3]
        add(
            "medium" if len(plugins) > 15 else "low" if len(plugins) > 8 else "info",
            "wp_plugin_assets",
            f"{len(plugins)} WordPress plugins load CSS/JS on this page",
            [f"{p} ({n})" for p, n in plugins.most_common()],
        )
        if heavy:
            add("low", "wp_heavy_plugins", "plugins loading 3+ files here; load them only where used", heavy)
    if shop_ext or shop_proxy:
        apps = [f"{k} ({v})" for k, v in (shop_ext + shop_proxy).most_common()]
        add(
            "low" if len(apps) > 5 else "info",
            "shopify_app_assets",
            f"{len(apps)} Shopify app extensions/proxies",
            apps,
        )
    if hosts:
        labelled = [f"{h} ({KNOWN_HOSTS[h]})" if h in KNOWN_HOSTS else h for h, _ in hosts.most_common()]
        sev = "medium" if len(hosts) > 12 else "low" if len(hosts) > 6 else "info"
        add(sev, "third_party_hosts", f"{len(hosts)} third-party hosts", labelled)

    blocking = [s["src"] for s in c.scripts if s["head"] and not s["async"]]
    if len(blocking) > 2:
        add(
            "medium", "render_blocking_js", f"{len(blocking)} scripts in <head> without async/defer", blocking
        )
    elif blocking:
        add("low", "render_blocking_js", f"{len(blocking)} script(s) in <head> without async/defer", blocking)

    jq = [
        s["src"]
        for s in c.scripts
        if re.search(r"jquery(?:[.-]\d[\d.]*)?(?:\.min)?\.js", s["src"], re.I)
        and "migrate" not in s["src"].lower()
        and "ui" not in s["src"].lower().rsplit("/", 1)[-1]
    ]
    if len(jq) > 1:
        add("medium", "multiple_jquery", f"jQuery is loaded {len(jq)} times", jq)
    if any("cart-fragments" in s["src"] or s["id"].startswith("wc-cart-fragments") for s in c.scripts):
        add(
            "low",
            "wc_cart_fragments",
            "WooCommerce cart fragments script loads (an uncached AJAX call on every page)",
            ["load it only where a mini-cart needs live updates"],
        )
    if len(set(c.fonts)) > 3:
        add("low", "many_fonts", f"{len(set(c.fonts))} web font files/stylesheets", sorted(set(c.fonts)))
    if c.inline_js > 100 * 1024:
        add("medium", "inline_js", f"{c.inline_js // 1024} KB of inline JavaScript (not cacheable)")
    if c.inline_css > 75 * 1024:
        add("low", "inline_css", f"{c.inline_css // 1024} KB of inline CSS")
    if len(c.scripts) > 40:
        add("medium", "script_count", f"{len(c.scripts)} external scripts")
    if len(c.styles) > 25:
        add("low", "stylesheet_count", f"{len(c.styles)} stylesheets")

    real_imgs = [i for i in c.images if i["src"] and not i["src"].startswith("data:")]
    no_dims = [i["src"] for i in real_imgs if not (i["width"] and i["height"])]
    if no_dims:
        add(
            "medium" if len(no_dims) > 5 else "low",
            "img_no_dimensions",
            f"{len(no_dims)} images without width/height (layout shift)",
            no_dims,
        )
    first = real_imgs[:2]
    if first and first[0]["loading"] == "lazy":
        add(
            "medium",
            "lazy_lcp",
            "the first image is lazy-loaded; the hero/product image should load eagerly",
            [first[0]["src"]],
        )
    if (
        first
        and not any(i["fetchpriority"] == "high" for i in first)
        and not any(p.get("as") == "image" for p in c.preloads)
    ):
        add(
            "info", "no_fetchpriority", 'hero image has no fetchpriority="high" or preload', [first[0]["src"]]
        )
    eager_rest = [i["src"] for i in real_imgs[4:] if i["loading"] != "lazy"]
    if len(eager_rest) > 10:
        add(
            "low",
            "no_lazy_loading",
            f"{len(eager_rest)} below-the-fold images are not lazy-loaded",
            eager_rest,
        )
    if c.tags > max_dom:
        add(
            "medium" if c.tags > 2 * max_dom else "low",
            "dom_size",
            f"about {c.tags} elements (aim for under {max_dom})",
        )

    findings.sort(key=lambda f: -SEVERITY_ORDER[f["severity"]])
    return {
        "scripts": len(c.scripts),
        "stylesheets": len(c.styles),
        "images": len(real_imgs),
        "elements": c.tags,
        "inline_js_kb": round(c.inline_js / 1024, 1),
        "wp_plugins": dict(plugins.most_common()),
        "wp_themes": themes,
        "shopify_apps": dict((shop_ext + shop_proxy).most_common()),
        "third_party_hosts": dict(hosts.most_common()),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("html", help="saved page HTML (View source / curl output), or - for stdin")
    p.add_argument("--site-host", default="", help="store domain; its own assets are not third-party")
    p.add_argument("--max-dom", type=int, default=1500)
    p.add_argument("--fail-on", choices=list(SEVERITY_ORDER), default="medium")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        if args.html == "-":
            text = sys.stdin.read()
        else:
            with open(args.html, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = analyse(text, args.site_host, args.max_dom)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['scripts']} scripts, {report['stylesheets']} stylesheets, {report['images']} images, "
            f"~{report['elements']} elements, {report['inline_js_kb']} KB inline JS"
        )
        if report["wp_themes"]:
            print("theme: " + ", ".join(report["wp_themes"]))
        for f in report["findings"]:
            print(f"[{f['severity'].upper()}] {f['code']}: {f['message']}")
            for item in f["items"][:12]:
                print(f"    - {item}")
            if len(f["items"]) > 12:
                print(f"    ... {len(f['items']) - 12} more")
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f["severity"]] >= threshold for f in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
