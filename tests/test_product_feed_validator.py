import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "product-feed-validator"
SCRIPT = "validate_feed.py"
mod = load_script(SKILL, SCRIPT)
FX = FIXTURES / SKILL


def codes(path, *extra):
    r = run_script(SKILL, SCRIPT, str(path), "--json", *extra)
    data = json.loads(r.stdout)
    return r.returncode, data, {f["code"] for f in data["findings"]}


@pytest.mark.parametrize(
    "gtin,ok",
    [
        ("4006381333931", True),
        ("036000291452", True),
        ("96385074", True),
        ("00012345600012", True),
        ("4006381333932", False),
        ("12345", False),
        ("0000000000000", False),
        ("40063813339A1", False),
    ],
)
def test_gtin_check(gtin, ok):
    assert (mod.gtin_check(gtin) is None) is ok


def test_restricted_prefixes():
    assert mod.gtin_restricted("2001234567893")
    assert mod.gtin_restricted("212345678906")  # UPC number system 2 (random weight)
    assert not mod.gtin_restricted("9781234567897")  # ISBN
    assert not mod.gtin_restricted("4006381333931")


def test_parse_price():
    assert mod.parse_price("15.00 USD") == (15.0, "USD")
    assert mod.parse_price("1200 BDT") == (1200.0, "BDT")
    assert mod.parse_price("$15.00") is None
    assert mod.parse_price("15,00 EUR") is None
    assert mod.parse_price("15.00") is None


def test_good_tsv_is_clean():
    rc, data, found = codes(FX / "good.tsv")
    assert rc == 0 and found == set() and data["items"] == 2 and data["format"] == "csv"


def test_bad_csv_findings():
    rc, data, found = codes(FX / "bad.csv")
    assert rc == 1
    expected = {
        "gtin_invalid",
        "duplicate_id",
        "image_placeholder",
        "price_format",
        "condition_invalid",
        "image_svg",
        "availability_invalid",
        "price_zero",
        "missing_description",
        "missing_image_link",
        "link_invalid",
        "missing_availability_date",
        "title_caps",
        "title_promo",
        "description_is_title",
        "link_http",
        "availability_format",
        "identifier_conflict",
        "mixed_currencies",
        "missing_brand",
    }
    assert expected <= found, expected - found
    assert data["items_with_errors"] == 3


def test_xml_feed():
    rc, data, found = codes(FX / "feed.xml")
    assert data["format"] == "xml" and data["items"] == 2
    assert rc == 1 and "sale_price_not_lower" in found
    # repeated additional_image_link elements are joined, nested g:shipping is tolerated
    items = mod.read_xml((FX / "feed.xml").read_text())
    assert items[0]["additional_image_link"].count(",") == 1
    assert items[0]["shipping"] == "present"
    # item 2 sets identifier_exists=no so no identifier warnings
    assert not any(f["item"] == "WOO-102" and f["code"] == "missing_identifiers" for f in data["findings"])


def test_fail_on_warning(tmp_path):
    feed = tmp_path / "f.tsv"
    rows = (FX / "good.tsv").read_text().splitlines()
    rows[1] = rows[1].replace("Acme Organic Cotton T-Shirt, Men, Navy, Size M", "Acme Tee SALE")
    feed.write_text("\n".join(rows) + "\n")
    assert codes(feed)[0] == 0
    rc, _, found = codes(feed, "--fail-on", "warning")
    assert rc == 1 and {"title_promo", "title_short"} <= found


def test_limits(tmp_path):
    feed = tmp_path / "f.csv"
    feed.write_text(
        "id,title,description,link,image_link,availability,price,brand,mpn,condition\n"
        f"{'x' * 51},{'T' * 10}{'t' * 150},{'d' * 5001},https://a.example.com/p,https://a.example.com/i.jpg,"
        "in_stock,1.00 USD,B,M1,new\n"
    )
    _, _, found = codes(feed)
    assert {"id_too_long", "title_too_long", "description_too_long"} <= found


def test_entities_refused(tmp_path):
    feed = tmp_path / "evil.xml"
    feed.write_text('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "x">]><rss><item><id>&a;</id></item></rss>')
    r = run_script(SKILL, SCRIPT, str(feed))
    assert r.returncode == 2 and "entities" in r.stderr


def test_text_output_and_errors(tmp_path):
    r = run_script(SKILL, SCRIPT, str(FX / "bad.csv"), "--max-per-code", "1")
    assert r.returncode == 1 and "[ERROR] gtin_invalid" in r.stdout and "more" in r.stdout
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.csv")).returncode == 2
    empty = tmp_path / "empty.csv"
    empty.write_text("id,title\n")
    assert run_script(SKILL, SCRIPT, str(empty)).returncode == 2
    r = run_script(SKILL, SCRIPT, "-", stdin=(FX / "good.tsv").read_text())
    assert r.returncode == 0
