import csv
import json

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "returns-and-fraud-signals"
RISK = "cod_risk.py"
RET = "return_rate.py"
risk = load_script(SKILL, RISK)
ret = load_script(SKILL, RET)
FX = FIXTURES / SKILL
ORDERS = str(FX / "orders-to-score.csv")
HISTORY = str(FX / "history.csv")


def scored(*extra):
    r = run_script(SKILL, RISK, "--orders", ORDERS, "--history", HISTORY, "--json", *extra)
    data = json.loads(r.stdout)
    return r.returncode, data, {x["order_id"]: x for x in data["results"]}


def rules(result):
    return {x["rule"] for x in result["reasons"]}


@pytest.mark.parametrize(
    "raw,key",
    [
        ("01712345678", "+8801712345678"),
        ("+880 1712-345678", "+8801712345678"),
        ("8801712345678", "+8801712345678"),
        ("+88001712345678", "+8801712345678"),
        ("১৭১২৩৪৫৬৭৮", "+8801712345678"),
        ("12345", ""),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_phone_key(raw, key):
    assert risk.phone_key(raw) == key


def test_scores_and_levels():
    rc, data, by = scored()
    assert rc == 1 and data["scored"] == 6 and data["history_phones"] == 3
    assert by["7002"]["level"] == "high" and {
        "fake_name",
        "short_address",
        "disposable_email",
        "bulk_quantity",
        "first_order_high_value",
    } <= rules(by["7002"])
    assert by["7006"]["level"] == "high" and {"prior_failed_delivery", "low_success_rate"} <= rules(
        by["7006"]
    )
    assert next(x for x in by["7006"]["reasons"] if x["rule"] == "prior_failed_delivery")["points"] == 50
    assert by["7005"]["level"] == "medium" and "invalid_phone" in rules(by["7005"])
    assert by["7001"]["score"] == 0 and "trusted_customer" in rules(by["7001"])
    assert "repeat_in_batch" in rules(by["7003"]) and "repeat_in_batch" in rules(by["7004"])
    assert "first_order_high_value" not in rules(by["7003"])  # has (cancelled) history
    assert "7007" not in by  # prepaid skipped by default
    assert by["7006"]["phone"] == "+880161****678"


def test_all_includes_prepaid_and_far_above_median():
    _, data, by = scored("--all")
    assert data["scored"] == 7 and by["7007"]["is_cod"] is False
    assert "far_above_median" in rules(by["7007"])
    assert "first_order_high_value" not in rules(by["7007"])  # COD-only rule


def test_without_history_and_text(tmp_path):
    r = run_script(SKILL, RISK, "--orders", ORDERS)
    assert r.returncode == 1 and "no history file" in r.stdout and "01712345678" not in r.stdout
    out = tmp_path / "scored.csv"
    r = run_script(SKILL, RISK, "--orders", ORDERS, "--history", HISTORY, "--out", str(out))
    rows = {row["Order Number"]: row for row in csv.DictReader(out.open())}
    assert rows["7002"]["risk_level"] == "high" and "disposable" in rows["7002"]["risk_reasons"]
    assert set(rows) == {"7001", "7002", "7003", "7004", "7005", "7006"}


def test_risk_errors(tmp_path):
    assert run_script(SKILL, RISK, "--orders", ORDERS, "--out", ORDERS).returncode == 2
    bad = tmp_path / "h.csv"
    bad.write_text("a,b\n1,2\n")
    r = run_script(SKILL, RISK, "--orders", ORDERS, "--history", str(bad))
    assert r.returncode == 2 and "phone and status" in r.stderr
    r = run_script(SKILL, RISK, "--orders", str(bad))
    assert r.returncode == 2 and "order id" in r.stderr


def test_categorize_and_wilson():
    assert ret.categorize("Size too small") == "size/fit"
    assert ret.categorize("Customer refused at door") == "refused/unreachable"
    assert ret.categorize("arrived broken") == "damaged"
    assert ret.categorize("colour looks different from picture") == "not as described"
    assert ret.categorize("") == "unspecified" and ret.categorize("meh") == "other"
    assert ret.wilson_lower(0, 10) == 0.0
    assert 0.2 < ret.wilson_lower(30, 100) < 0.3
    assert ret.wilson_lower(1, 2) < 0.1
    assert ret.mask("someone@example.com") == "so***@example.com" and ret.mask("1712345678") == "***678"


def test_return_rates():
    r = run_script(
        SKILL, RET, "--orders", str(FX / "order-lines.csv"), "--returns", str(FX / "returns.csv"), "--json"
    )
    data = json.loads(r.stdout)
    assert r.returncode == 1
    assert data["orders"] == 120 and data["units_sold"] == 242 and data["units_returned"] == 36
    assert data["flagged_skus"] == ["TEE-M"]
    skus = {s["sku"]: s for s in data["skus"]}
    assert skus["TEE-M"]["top_reason"] == "size/fit" and skus["TEE-M"]["returned"] == 33
    assert not skus["BAG-1"]["flagged"]  # 50% but only 2 sold
    assert skus["OLD-SKU"]["sold"] == 0 and skus["OLD-SKU"]["note"]
    assert data["serial_returners"] == [
        {"customer": "***111", "orders": 4, "returned_orders": 3, "share": 0.75}
    ]
    assert {d["district"] for d in data["by_district"]} == {"Dhaka", "Chattogram", "Sylhet"}
    assert {c["courier"] for c in data["by_courier"]} == {"Pathao", "Steadfast", "RedX"}
    assert data["reasons"]["size/fit"] == 30


def test_status_column_mode():
    r = run_script(SKILL, RET, "--orders", str(FX / "order-lines-status.csv"), "--json")
    data = json.loads(r.stdout)
    assert r.returncode == 0 and data["units_returned"] == 2 and data["order_return_rate"] == 0.5
    assert data["reasons"] == {"size/fit": 1, "refused/unreachable": 1}
    r = run_script(SKILL, RET, "--orders", str(FX / "order-lines-status.csv"), "--min-units", "1", "--json")
    assert json.loads(r.stdout)["flagged_skus"] == []  # 50% vs 50% average is not above average


def test_return_errors_and_text(tmp_path):
    r = run_script(SKILL, RET, "--orders", str(FX / "order-lines.csv"))
    assert r.returncode == 2 and "status column" in r.stderr
    r = run_script(SKILL, RET, "--orders", str(FX / "order-lines.csv"), "--returns", str(FX / "returns.csv"))
    assert "FLAG TEE-M" in r.stdout and "Serial returners" in r.stdout and "01899" not in r.stdout
    bad = tmp_path / "x.csv"
    bad.write_text("a\n1\n")
    assert run_script(SKILL, RET, "--orders", str(bad), "--returns", str(FX / "returns.csv")).returncode == 2
