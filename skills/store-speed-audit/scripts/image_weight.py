#!/usr/bin/env python3
"""Audit the weight of product images in a folder (WordPress uploads, Shopify export, photo dump).

Reads image headers with the standard library only (JPEG, PNG, GIF, WebP, BMP, AVIF/HEIC
dimensions) and reports files over a size budget, oversized dimensions, photos saved as PNG,
poorly compressed JPEGs, heavy GIFs, non-web formats, images too small for zoom or Merchant
Center, and byte-identical duplicates, with an estimate of the savings. Read-only: never
modifies or converts files.

Exit codes: 0 = no findings at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".avif", ".heic", ".svg"}
WP_THUMB_RE = re.compile(r"-\d{2,4}x\d{2,4}\.(?:jpe?g|png|webp|gif|avif)$", re.I)
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}


def image_info(data: bytes) -> dict:
    """Return {'format', 'width', 'height', 'alpha', 'progressive'} from file bytes."""
    info = {"format": "unknown", "width": None, "height": None, "alpha": None, "progressive": None}
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 26:
        w, h = struct.unpack(">II", data[16:24])
        info.update(format="png", width=w, height=h, alpha=data[25] in (4, 6) or b"tRNS" in data[:4096])
    elif data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        w, h = struct.unpack("<HH", data[6:10])
        info.update(format="gif", width=w, height=h)
    elif data[:2] == b"\xff\xd8":
        info["format"] = "jpeg"
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                i += 1 if marker == 0xFF else 2
                continue
            length = struct.unpack(">H", data[i + 2 : i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                info.update(width=w, height=h, progressive=marker in (0xC2, 0xC6, 0xCA, 0xCE))
                break
            i += 2 + length
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        info["format"] = "webp"
        chunk = data[12:16]
        if chunk == b"VP8 " and len(data) >= 30:
            w, h = struct.unpack("<HH", data[26:30])
            info.update(width=w & 0x3FFF, height=h & 0x3FFF, alpha=False)
        elif chunk == b"VP8L" and len(data) >= 25:
            b = data[21:25]
            info.update(
                width=1 + (((b[1] & 0x3F) << 8) | b[0]),
                height=1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6)),
                alpha=bool(b[3] & 0x10),
            )
        elif chunk == b"VP8X" and len(data) >= 30:
            info.update(
                width=1 + int.from_bytes(data[24:27], "little"),
                height=1 + int.from_bytes(data[27:30], "little"),
                alpha=bool(data[20] & 0x10),
            )
    elif data[:2] == b"BM" and len(data) >= 26:
        w, h = struct.unpack("<ii", data[18:26])
        info.update(format="bmp", width=w, height=abs(h))
    elif data[:4] in (b"II*\x00", b"MM\x00*"):
        info["format"] = "tiff"
    elif data[4:8] == b"ftyp":
        brand = data[8:12]
        info["format"] = "avif" if brand in (b"avif", b"avis") else "heic"
        pos = data.find(b"ispe", 0, 1 << 16)
        if pos != -1 and pos + 16 <= len(data):
            w, h = struct.unpack(">II", data[pos + 8 : pos + 16])
            info.update(width=w, height=h)
    elif data.lstrip()[:5] in (b"<?xml", b"<svg ") or b"<svg" in data[:1024]:
        info["format"] = "svg"
    return info


def scan(root: str, opts) -> dict:
    files, skipped_thumbs = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() not in EXTS:
                continue
            if not opts.include_thumbnails and WP_THUMB_RE.search(name):
                skipped_thumbs += 1
                continue
            files.append(os.path.join(dirpath, name))

    findings: list[dict] = []
    images: list[dict] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    budget = opts.max_kb * 1024

    def add(sev, code, rel, msg):
        findings.append({"severity": sev, "code": code, "file": rel, "message": msg})

    for path in files:
        rel = os.path.relpath(path, root)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            add("low", "unreadable", rel, str(exc))
            continue
        size = len(data)
        info = image_info(data)
        hashes[hashlib.sha1(data).hexdigest()].append(rel)
        w, h = info["width"], info["height"]
        est = size
        fmt = info["format"]
        if fmt in ("bmp", "tiff"):
            add("high", "not_web_format", rel, f"{fmt.upper()} is not a web format; export as JPEG or WebP")
            est = min(est, budget)
        if fmt == "svg":
            if size > 100 * 1024:
                add(
                    "low",
                    "heavy_svg",
                    rel,
                    f"SVG is {size // 1024} KB; optimise it (SVGO) or use a raster image",
                )
        elif size > budget:
            sev = "high" if size > 2 * budget else "medium"
            add(sev, "over_budget", rel, f"{size // 1024} KB (budget {opts.max_kb} KB)")
            est = min(est, budget)
        if w and h:
            longest, shortest = max(w, h), min(w, h)
            if longest > opts.max_px:
                add("medium", "oversized", rel, f"{w}x{h}px; resize to {opts.max_px}px on the longest side")
                est = min(est, int(size * (opts.max_px / longest) ** 2))
            if shortest < 100:
                add(
                    "high",
                    "too_small",
                    rel,
                    f"{w}x{h}px; Merchant Center needs at least 100x100 (250x250 apparel)",
                )
            elif shortest < opts.min_px and fmt != "gif":
                add("low", "small_for_zoom", rel, f"{w}x{h}px; {opts.min_px}px+ looks sharper with zoom")
            px = w * h
            if fmt == "png" and info["alpha"] is False and size > 100 * 1024:
                add(
                    "medium",
                    "png_photo",
                    rel,
                    f"opaque PNG of {size // 1024} KB; a JPEG/WebP is usually 70-90% smaller",
                )
                est = min(est, int(size * 0.25))
            if fmt == "jpeg" and size > 100 * 1024 and px and size / px > opts.max_bpp:
                add(
                    "low", "poor_compression", rel, f"{size / px:.2f} bytes/pixel; re-encode at quality 75-85"
                )
                est = min(est, int(px * opts.max_bpp * 0.6))
        elif fmt not in ("svg", "tiff"):
            add("info", "no_dimensions", rel, f"could not read dimensions ({fmt})")
        if fmt == "gif" and size > 500 * 1024:
            add("medium", "heavy_gif", rel, f"GIF of {size // 1024} KB; use MP4/WebM video or a static WebP")
        images.append(
            {
                "file": rel,
                "format": fmt,
                "bytes": size,
                "width": w,
                "height": h,
                "estimated_bytes": min(size, est),
            }
        )

    for digest, paths in hashes.items():
        if len(paths) > 1:
            findings.append(
                {
                    "severity": "info",
                    "code": "duplicate",
                    "file": paths[0],
                    "message": f"identical to {', '.join(paths[1:])}",
                    "sha1": digest[:12],
                }
            )

    total = sum(i["bytes"] for i in images)
    saving = sum(i["bytes"] - i["estimated_bytes"] for i in images)
    by_format = Counter()
    bytes_by_format = Counter()
    for i in images:
        by_format[i["format"]] += 1
        bytes_by_format[i["format"]] += i["bytes"]
    legacy = bytes_by_format["jpeg"] + bytes_by_format["png"]
    if images and legacy / max(1, total) > 0.8 and total > 5 * 1024 * 1024:
        findings.append(
            {
                "severity": "info",
                "code": "modern_formats",
                "file": "",
                "message": "most bytes are JPEG/PNG; serve WebP/AVIF (Shopify CDN does this automatically; "
                "WordPress needs a converter or image CDN)",
            }
        )
    findings.sort(key=lambda f: (-SEVERITY_ORDER[f["severity"]], f["file"]))
    heaviest = sorted(images, key=lambda i: -i["bytes"])[: opts.top]
    return {
        "root": root,
        "images": len(images),
        "skipped_thumbnails": skipped_thumbs,
        "total_bytes": total,
        "average_kb": round(total / len(images) / 1024, 1) if images else 0,
        "by_format": dict(by_format),
        "estimated_saving_bytes": saving,
        "counts": dict(Counter(f["severity"] for f in findings)),
        "heaviest": heaviest,
        "findings": findings,
    }


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", help="folder with images (scanned recursively)")
    p.add_argument("--max-kb", type=int, default=250, help="size budget per image in KB (default 250)")
    p.add_argument("--max-px", type=int, default=2048, help="longest side budget in px (default 2048)")
    p.add_argument("--min-px", type=int, default=800, help="warn when the shortest side is below this")
    p.add_argument(
        "--max-bpp", type=float, default=0.5, help="JPEG bytes per pixel considered poorly compressed"
    )
    p.add_argument("--include-thumbnails", action="store_true", help="include WordPress -300x300 style sizes")
    p.add_argument("--top", type=int, default=10, help="list the N heaviest files")
    p.add_argument("--fail-on", choices=list(SEVERITY_ORDER), default="medium")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    if not os.path.isdir(args.folder):
        print(f"error: {args.folder} is not a directory", file=sys.stderr)
        return 2
    report = scan(args.folder, args)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"{report['images']} images, {mb(report['total_bytes'])} total, avg {report['average_kb']} KB "
            f"({report['skipped_thumbnails']} WordPress thumbnails skipped)"
        )
        print("formats: " + ", ".join(f"{k} {v}" for k, v in sorted(report["by_format"].items())))
        print(f"estimated saving: {mb(report['estimated_saving_bytes'])}")
        print("\nheaviest:")
        for i in report["heaviest"]:
            dims = f"{i['width']}x{i['height']}" if i["width"] else "?"
            print(f"  {i['bytes'] // 1024:>6} KB  {dims:>11}  {i['file']}")
        grouped = defaultdict(list)
        for f in report["findings"]:
            grouped[(f["severity"], f["code"])].append(f)
        for (sev, code), group in sorted(grouped.items(), key=lambda kv: -SEVERITY_ORDER[kv[0][0]]):
            print(f"\n[{sev.upper()}] {code} x{len(group)}")
            for f in group[:8]:
                print(f"  - {f['file']}: {f['message']}")
            if len(group) > 8:
                print(f"  ... {len(group) - 8} more")
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f["severity"]] >= threshold for f in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
