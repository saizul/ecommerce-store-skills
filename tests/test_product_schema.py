import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "product-schema"
SCRIPT = "product_schema.py"
mod = load_script(SKILL, SCRIPT)
FX = FIXTURES / SKILL
TODAY = "2026-11-25"


def validate(path, *extra):
    r = run_script(SKILL, SCRIPT, "validate", str(path), "--json", "--today", TODAY, *extra)
    return r.returncode, json.loads(r.stdout)


def messages(report, severity=None):
    return [f["message"] for f in report["findings"] if severity in (None, f["severity"])]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1,250", "1250.00"),
        ("1,299.50", "1299.50"),
        ("1.299,50", "1299.50"),
        ("৳ 1,200", "1200.00"),
        ("$19.9", "19.90"),
        ("12,5", "12.50"),
        (25, "25.00"),
        ("free", None),
        (None, None),
    ],
)
def test_clean_price(raw, expected):
    assert mod.clean_price(raw) == expected


def test_generate_from_json():
    r = run_script(SKILL, SCRIPT, "generate", str(FX / "product.json"))
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["offers"]["price"] == "1250.00"
    assert data["offers"]["availability"] == "https://schema.org/InStock"
    assert data["offers"]["itemCondition"] == "https://schema.org/NewCondition"
    assert data["image"] == ["https://cdn.example.com/img/mug-1.jpg", "https://cdn.example.com/img/mug-2.jpg"]
    assert data["description"] == "Hand-glazed stoneware mug."
    assert data["aggregateRating"]["reviewCount"] == 38


def test_generated_output_validates(tmp_path):
    r = run_script(SKILL, SCRIPT, "generate", str(FX / "product.json"), "--script-tag")
    page = tmp_path / "page.html"
    page.write_text(f"<html><head>{r.stdout}</head></html>")
    rc, report = validate(page)
    assert rc == 0 and report["errors"] == 0 and report["warnings"] == 0


def test_generate_from_woocommerce_csv():
    r = run_script(SKILL, SCRIPT, "generate", str(FX / "products.csv"), "--currency", "usd")
    assert r.returncode == 0
    blocks = [json.loads(b) for b in r.stdout.replace("}\n{", "}\n\n{").split("\n\n")]
    assert [b["sku"] for b in blocks] == ["TSH-001", "TSH-002"]
    assert blocks[0]["gtin"] == "4006381333931" and blocks[0]["brand"]["name"] == "Acme"
    assert blocks[1]["offers"]["availability"].endswith("OutOfStock")
    assert blocks[0]["offers"]["priceCurrency"] == "USD"


def test_generate_rejects_bad_input(tmp_path):
    bad = tmp_path / "p.json"
    bad.write_text(json.dumps({"name": "X", "gtin": "4006381333932", "price": "1"}))
    r = run_script(SKILL, SCRIPT, "generate", str(bad), "--currency", "USD")
    assert r.returncode == 2 and "check digit" in r.stderr
    bad.write_text(json.dumps({"name": "X", "price": "10"}))
    r = run_script(SKILL, SCRIPT, "generate", str(bad))
    assert r.returncode == 2 and "currency" in r.stderr
    bad.write_text(json.dumps([{"price": "10"}]))
    assert run_script(SKILL, SCRIPT, "generate", str(bad)).returncode == 2
    r = run_script(SKILL, SCRIPT, "generate", "-", stdin=json.dumps({"name": "Only name"}))
    assert r.returncode == 0 and "offers" not in json.loads(r.stdout)


def test_no_rating_without_reviews():
    data = mod.build_product({"name": "X", "rating_value": "4.5", "review_count": "0"})
    assert "aggregateRating" not in data


def test_good_page_is_clean():
    rc, report = validate(FX / "good.html")
    assert rc == 0 and report["products"] == 1 and report["errors"] == 0 and report["warnings"] == 0
    assert not any(f["severity"] == "info" for f in report["findings"])


def test_bad_page_findings():
    rc, report = validate(FX / "bad.html")
    assert rc == 1 and report["products"] == 3 and report["blocks"] == 3
    text = "\n".join(messages(report))
    for needle in [
        "not valid JSON",
        "marked up 2 times",
        "missing image",
        "must be a number without currency symbols",
        "ISO 4217",
        "full URL https://schema.org/InStock",
        "in the past",
        "outside 1-5",
        "reviewCount or ratingCount",
        "gtin13 '4006381333932'",
        "missing price",
        "'https://schema.org/Available' is not",
        "itemCondition 'Mint'",
        "missing author",
        "reviewRating.ratingValue",
        "lowPrice '1,000'",
        "AggregateOffer needs priceCurrency",
    ]:
        assert needle in text, needle


def test_product_group_variants(tmp_path):
    doc = {
        "@context": "https://schema.org",
        "@type": "ProductGroup",
        "name": "Tee",
        "hasVariant": [
            {
                "@type": "Product",
                "name": "Tee S",
                "image": "https://a.example.com/s.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "10",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                },
            },
            {
                "@type": "Product",
                "name": "Tee M",
                "image": "https://a.example.com/m.jpg",
                "offers": {"@type": "Offer", "price": "10 USD", "priceCurrency": "USD"},
            },
        ],
    }
    f = tmp_path / "g.json"
    f.write_text(json.dumps(doc))
    rc, report = validate(f)
    assert report["products"] == 2 and rc == 1
    assert any("Tee M" in m and "price '10 USD'" in m for m in messages(report, "error"))


def test_no_product_and_text_output(tmp_path):
    f = tmp_path / "x.html"
    f.write_text('<script type="application/ld+json">{"@type":"Organization","name":"X"}</script>')
    rc, report = validate(f)
    assert rc == 1 and "no Product JSON-LD found" in messages(report)
    r = run_script(SKILL, SCRIPT, "validate", str(FX / "bad.html"), "--today", TODAY)
    assert r.returncode == 1 and "[ERROR]" in r.stdout and "--verbose" in r.stdout
    assert run_script(SKILL, SCRIPT, "validate", str(tmp_path / "missing.html")).returncode == 2


def test_gtin_ok():
    assert mod.gtin_ok("4006381333931") and mod.gtin_ok("96385074")
    assert not mod.gtin_ok("4006381333932") and not mod.gtin_ok("abc")
