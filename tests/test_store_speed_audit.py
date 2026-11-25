"""Images are generated at test time: real PNGs via zlib, header-accurate JPEG/WebP/GIF/BMP/AVIF stubs."""

import json
import struct
import zlib

from conftest import FIXTURES, load_script, run_script

SKILL = "store-speed-audit"
IMG = "image_weight.py"
PAGE = "page_assets.py"
img = load_script(SKILL, IMG)
page = load_script(SKILL, PAGE)
FX = FIXTURES / SKILL


def png(w, h, alpha=False, pad=0):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6 if alpha else 2, 0, 0, 0)
    raw = zlib.compress(b"\x00" * (w * (4 if alpha else 3) + 1) * min(h, 4))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", raw)
        + chunk(b"tEXt", b"c\x00" + b"x" * pad)
        + chunk(b"IEND", b"")
    )


def jpeg(w, h, size, progressive=False):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = (
        b"\xff"
        + (b"\xc2" if progressive else b"\xc0")
        + struct.pack(">HBHHB", 17, 8, h, w, 3)
        + b"\x01\x22\x00" * 3
    )
    head = b"\xff\xd8" + app0 + sof
    return head + b"\x00" * max(0, size - len(head) - 2) + b"\xff\xd9"


def webp_vp8x(w, h, size=200):
    body = (
        b"WEBP"
        + b"VP8X"
        + struct.pack("<I", 10)
        + b"\x10\x00\x00\x00"
        + (w - 1).to_bytes(3, "little")
        + (h - 1).to_bytes(3, "little")
    )
    data = b"RIFF" + struct.pack("<I", len(body)) + body
    return data + b"\x00" * max(0, size - len(data))


def write(folder, name, data):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_header_parsing():
    assert img.image_info(png(640, 480)) == {
        "format": "png",
        "width": 640,
        "height": 480,
        "alpha": False,
        "progressive": None,
    }
    assert img.image_info(png(10, 20, alpha=True))["alpha"] is True
    info = img.image_info(jpeg(3000, 2000, 5000, progressive=True))
    assert (info["format"], info["width"], info["height"], info["progressive"]) == ("jpeg", 3000, 2000, True)
    assert img.image_info(webp_vp8x(1200, 900))["width"] == 1200
    assert img.image_info(b"GIF89a" + struct.pack("<HH", 320, 200) + b"\x00" * 10)["width"] == 320
    assert img.image_info(b"BM" + b"\x00" * 16 + struct.pack("<ii", 50, -40) + b"\x00" * 8)["height"] == 40
    avif = (
        b"\x00\x00\x00\x1cftypavif"
        + b"\x00" * 20
        + b"\x00\x00\x00\x14ispe\x00\x00\x00\x00"
        + struct.pack(">II", 800, 600)
    )
    assert img.image_info(avif)["width"] == 800
    assert img.image_info(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")["format"] == "svg"
    vp8l = b"RIFF\x00\x00\x00\x00WEBPVP8L\x00\x00\x00\x00\x2f" + bytes([0x3F, 0xC0, 0x3F, 0x00])
    vi = img.image_info(vp8l)
    assert vi["width"] == 64 and vi["height"] == 256


def build_folder(tmp_path):
    d = tmp_path / "uploads"
    write(d, "2026/11/hero.jpg", jpeg(4000, 4000, 1_900_000))
    write(d, "2026/11/hero-300x300.jpg", jpeg(300, 300, 20_000))
    write(d, "2026/11/ok.jpg", jpeg(1600, 1600, 180_000))
    write(d, "2026/11/flat-photo.png", png(1200, 1200, pad=300_000))
    write(d, "2026/11/logo.png", png(400, 400, alpha=True, pad=10_000))
    write(d, "2026/11/tiny.webp", webp_vp8x(90, 90))
    write(d, "2026/11/scan.bmp", b"BM" + b"\x00" * 16 + struct.pack("<ii", 1000, 1000) + b"\x00" * 1000)
    write(d, "2026/11/dupe-a.jpg", jpeg(1000, 1000, 150_000))
    write(d, "2026/11/dupe-b.jpg", jpeg(1000, 1000, 150_000))
    write(d, "2026/11/notes.txt", b"not an image")
    return d


def run_images(folder, *extra):
    r = run_script(SKILL, IMG, str(folder), "--json", *extra)
    data = json.loads(r.stdout)
    return r.returncode, data, {(f["code"], f["file"].split("/")[-1]) for f in data["findings"]}


def test_image_folder(tmp_path):
    rc, data, found = run_images(build_folder(tmp_path))
    assert rc == 1 and data["images"] == 8 and data["skipped_thumbnails"] == 1
    for item in [
        ("over_budget", "hero.jpg"),
        ("oversized", "hero.jpg"),
        ("png_photo", "flat-photo.png"),
        ("too_small", "tiny.webp"),
        ("not_web_format", "scan.bmp"),
        ("small_for_zoom", "logo.png"),
        ("duplicate", "dupe-a.jpg"),
    ]:
        assert item in found, item
    assert ("png_photo", "logo.png") not in found  # transparent PNGs are fine
    assert not any(code in ("over_budget", "oversized") for code, f in found if f == "ok.jpg")
    hero = next(f for f in data["findings"] if f["code"] == "over_budget")
    assert hero["severity"] == "high"
    assert data["heaviest"][0]["file"].endswith("hero.jpg")
    assert data["estimated_saving_bytes"] > 1_600_000


def test_poor_compression_and_thumbnails(tmp_path):
    d = tmp_path / "i"
    write(d, "fat.jpg", jpeg(500, 500, 200_000))  # 0.8 bytes/pixel
    write(d, "fat-150x150.jpg", jpeg(150, 150, 5_000))
    rc, data, found = run_images(d, "--fail-on", "high")
    assert ("poor_compression", "fat.jpg") in found and rc == 0
    _, data, _ = run_images(d, "--include-thumbnails")
    assert data["images"] == 2


def test_image_text_output_and_errors(tmp_path):
    r = run_script(SKILL, IMG, str(build_folder(tmp_path)))
    assert "heaviest:" in r.stdout and "[HIGH]" in r.stdout
    assert run_script(SKILL, IMG, str(tmp_path / "nope")).returncode == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_script(SKILL, IMG, str(empty)).returncode == 0


def page_report(name, *extra):
    r = run_script(SKILL, PAGE, str(FX / name), "--site-host", "shop.example.com", "--json", *extra)
    data = json.loads(r.stdout)
    return r.returncode, data, {f["code"]: f for f in data["findings"]}


def test_bloated_woocommerce_page():
    rc, data, by = page_report("woocommerce-bloated.html")
    assert rc == 1
    assert len(data["wp_plugins"]) == 17 and data["wp_themes"] == ["flatsome"]
    assert by["wp_plugin_assets"]["severity"] == "medium"
    assert {"render_blocking_js", "multiple_jquery", "inline_js", "lazy_lcp"} <= set(by)
    assert {
        "wc_cart_fragments",
        "many_fonts",
        "img_no_dimensions",
        "third_party_hosts",
        "wp_heavy_plugins",
    } <= set(by)
    assert "static.hotjar.com" in data["third_party_hosts"]
    assert "shop.example.com" not in data["third_party_hosts"]
    assert any("Hotjar" in i for i in by["third_party_hosts"]["items"])


def test_lean_shopify_page():
    rc, data, by = page_report("shopify-lean.html")
    assert rc == 0 and data["shopify_apps"] == {"judgeme-reviews-123": 1}
    assert set(by) == {"shopify_app_assets"}


def test_dom_and_lazy_rules():
    html = "<html><head></head><body>" + "<div></div>" * 3100 + "</body></html>"
    rep = page.analyse(html, max_dom=1500)
    assert any(f["code"] == "dom_size" and f["severity"] == "medium" for f in rep["findings"])
    imgs = "".join(f'<img src="/i{i}.jpg" width="1" height="1">' for i in range(20))
    rep = page.analyse(f"<html><body>{imgs}</body></html>")
    codes = {f["code"] for f in rep["findings"]}
    assert "no_lazy_loading" in codes and "no_fetchpriority" in codes


def test_page_text_output_and_errors(tmp_path):
    r = run_script(SKILL, PAGE, str(FX / "woocommerce-bloated.html"))
    assert "[MEDIUM] multiple_jquery" in r.stdout and "theme: flatsome" in r.stdout
    assert run_script(SKILL, PAGE, str(tmp_path / "missing.html")).returncode == 2
    r = run_script(SKILL, PAGE, "-", stdin="<html><body></body></html>")
    assert r.returncode == 0
