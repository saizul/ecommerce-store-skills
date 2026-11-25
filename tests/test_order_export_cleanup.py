import csv
import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "order-export-cleanup"
SCRIPT = "clean_orders.py"
mod = load_script(SKILL, SCRIPT)
FX = FIXTURES / SKILL
WOO = FX / "woocommerce-orders.csv"
SHOPIFY = FX / "shopify-orders.csv"


@pytest.mark.parametrize(
    "raw,e164,operator",
    [
        ("01712-345678", "+8801712345678", "Grameenphone"),
        ("+880 1812 345678", "+8801812345678", "Robi"),
        ("8801912345678", "+8801912345678", "Banglalink"),
        ("008801512345678", "+8801512345678", "Teletalk"),
        ("+88001612345678", "+8801612345678", "Robi (Airtel)"),
        ("1312345678", "+8801312345678", "Grameenphone"),
        ("০১৪১২৩৪৫৬৭৮", "+8801412345678", "Banglalink"),
        ("(017) 1234-5678", "+8801712345678", "Grameenphone"),
    ],
)
def test_bd_phones_valid(raw, e164, operator):
    res = mod.normalize_phone(raw, "BD")
    assert res["valid"] and res["e164"] == e164 and res["operator"] == operator


@pytest.mark.parametrize(
    "raw,issue",
    [
        ("12345", "phone_invalid"),
        ("01212345678", "phone_invalid"),
        ("02-9112233", "phone_invalid"),
        ("1.71234E+09", "phone_excel_corrupted"),
        ("", "phone_missing"),
    ],
)
def test_bd_phones_invalid(raw, issue):
    res = mod.normalize_phone(raw, "BD")
    assert not res["valid"] and issue in res["issues"]


def test_other_countries_and_multiple():
    assert mod.normalize_phone("+91 98765 43210", "IN")["e164"] == "+919876543210"
    assert mod.normalize_phone("098765 43210", "IN")["e164"] == "+919876543210"
    assert mod.normalize_phone("+44 20 7946 0958", "BD")["issues"] == ["phone_foreign"]
    res = mod.normalize_phone("01911-223344, 01611-223344", "BD")
    assert res["e164"] == "+8801911223344" and "multiple_phones" in res["issues"]


def test_districts_and_tidy():
    assert mod.find_district("chittagong") == "Chattogram"
    assert mod.find_district("", "Comilla") == "Cumilla"
    assert mod.find_district("", "Mirpur", "", "House 3, Mirpur 10, Dhaka") == "Dhaka"
    assert mod.find_district("Cox's Bazar") == "Cox's Bazar"
    assert mod.find_district("ঢাকা") == "Dhaka"
    assert mod.find_district("Agrabad") == ""
    assert mod.tidy("House 12,  Road 5 ,, Dhanmondi,") == "House 12, Road 5, Dhanmondi"
    assert mod.tidy_name("rahim UDDIN") == "rahim UDDIN" and mod.tidy_name("RAHIM UDDIN") == "Rahim Uddin"
    assert mod.mask_phone("+8801712345678") == "+880171****678"


@pytest.mark.parametrize(
    "raw,value",
    [
        ("1,250.00", 1250.0),
        ("1,250", 1250.0),
        ("৳ ৯৯০", 990.0),
        ("12,50", 12.5),
        ("1.250,75", 1250.75),
        ("", None),
    ],
)
def test_parse_total(raw, value):
    assert mod.parse_total(raw) == value


def test_woocommerce_report():
    r = run_script(SKILL, SCRIPT, str(WOO), "--json")
    s = json.loads(r.stdout)
    assert r.returncode == 1
    assert s["rows_in"] == 9 and s["orders_out"] == 8 and s["exact_duplicates_dropped"] == 1
    assert s["cod_orders"] == 5 and s["valid_phones"] == 6
    flagged = {f["order_id"]: f for f in s["flagged"]}
    assert set(flagged) == {"1003", "1004", "1006"}
    assert flagged["1004"]["duplicate_of"] == "1001" and flagged["1004"]["phone"] == "+880171****678"
    assert s["issues"]["postcode_invalid"] == 1 and s["issues"]["multiple_phones"] == 1
    assert "01712" not in r.stdout  # report never prints full numbers


def test_woocommerce_cleaned_file(tmp_path):
    out = tmp_path / "clean.csv"
    r = run_script(SKILL, SCRIPT, str(WOO), "--out", str(out))
    assert r.returncode == 1 and "written" in r.stdout
    rows = {row["Order Number"]: row for row in csv.DictReader(out.open())}
    assert rows["1001"]["phone_e164"] == "+8801712345678" and rows["1001"]["is_cod"] == "yes"
    assert rows["1001"]["Billing First Name"] == "Rahim" and rows["1001"]["Billing Last Name"] == "Uddin"
    assert rows["1001"]["Billing Address 1"] == "House 12, Road 5, Dhanmondi"
    assert rows["1001"]["total_clean"] == "1250.00"
    assert rows["1002"]["district"] == "Chattogram" and rows["1002"]["is_cod"] == "no"
    assert rows["1005"]["phone_e164"] == "+8801912345678" and rows["1005"]["district"] == "Sylhet"
    assert rows["1006"]["district"] == "Cumilla" and "phone_excel_corrupted" in rows["1006"]["issues"]
    assert rows["1007"]["district"] == "Rajshahi"
    assert rows["1008"]["phone_e164"] == "+919876543210" and rows["1008"]["district"] == ""
    assert "district_unknown" not in rows["1008"]["issues"]  # only checked for BD rows


def test_dup_window(tmp_path):
    r = run_script(SKILL, SCRIPT, str(WOO), "--json", "--dup-hours", "1")
    s = json.loads(r.stdout)
    assert "possible_duplicate" not in s["issues"]  # 1001 and 1004 are 1h45m apart


def test_shopify_line_items_merged(tmp_path):
    out = tmp_path / "s.csv"
    r = run_script(SKILL, SCRIPT, str(SHOPIFY), "--out", str(out), "--json")
    s = json.loads(r.stdout)
    assert r.returncode == 0 and s["line_rows_merged"] == 1 and s["orders_out"] == 2
    rows = list(csv.DictReader(out.open()))
    assert rows[0]["Name"] == "#1101" and rows[0]["Total"] == "1500.00" and rows[0]["is_cod"] == "yes"
    assert rows[0]["phone_operator"] == "Teletalk" and rows[0]["district"] == "Dhaka"
    assert rows[1]["district"] == "Khulna"


def test_map_override_and_errors(tmp_path):
    f = tmp_path / "o.csv"
    f.write_text("Invoice,Mobile No,Amount\nA1,01712345678,100\n")
    r = run_script(SKILL, SCRIPT, str(f), "--json")
    assert r.returncode == 2 and "order id" in r.stderr
    r = run_script(SKILL, SCRIPT, str(f), "--json", "--map", "order_id=Invoice", "--map", "phone=Mobile No")
    s = json.loads(r.stdout)
    assert r.returncode == 0 and s["valid_phones"] == 1
    assert run_script(SKILL, SCRIPT, str(f), "--map", "order_id=Nope").returncode == 2
    assert run_script(SKILL, SCRIPT, str(f), "--map", "bad").returncode == 2
    assert run_script(SKILL, SCRIPT, str(f), "--out", str(f)).returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.csv")).returncode == 2
