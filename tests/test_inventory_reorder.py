import csv
import json
import math

import pytest

from conftest import FIXTURES, load_script, run_script

SKILL = "inventory-reorder"
SCRIPT = "reorder.py"
mod = load_script(SKILL, SCRIPT)
FX = FIXTURES / SKILL
ARGS = ["--sales", str(FX / "sales.csv"), "--stock", str(FX / "stock.csv")]


def report(*extra):
    r = run_script(SKILL, SCRIPT, *ARGS, "--json", *extra)
    data = json.loads(r.stdout)
    return r.returncode, data, {x["sku"]: x for x in data["results"]}


def test_statuses():
    rc, data, by = report()
    assert rc == 1 and data["as_of"] == "2026-11-20"
    assert {k: v["status"] for k, v in by.items()} == {
        "MUG-1": "stockout",
        "TEE-M": "reorder",
        "NEWBAG": "new",
        "CAP": "ok",
        "BOARD": "overstock",
        "SPOON": "dead",
    }
    assert [r["sku"] for r in data["results"]][:2] == ["MUG-1", "TEE-M"]
    assert data["sold_but_not_in_stock_file"] == ["GHOST"]
    assert data["skipped_sales_rows"] == 1


def test_formulas_for_tee():
    _, data, by = report()
    tee = by["TEE-M"]
    pattern = [4, 6, 5, 3, 7, 5, 5]
    series = [pattern[i % 7] for i in range(90)]
    series[88] -= 2  # refund on 2026-11-19
    avg = sum(series) / 90
    sd = math.sqrt(sum((x - avg) ** 2 for x in series) / 90)
    assert tee["avg_daily"] == round(avg, 3) and tee["sd_daily"] == round(sd, 3)
    safety = 1.645 * sd * math.sqrt(14)
    assert tee["safety_stock"] == round(safety, 1)
    assert tee["reorder_point"] == round(avg * 14 + safety, 1)
    need = avg * (14 + 30) + safety - 40
    assert tee["order_qty"] == math.ceil(need / 10) * 10 and tee["order_qty"] % 10 == 0
    assert tee["order_value"] == round(tee["order_qty"] * 6.5, 2)
    assert tee["est_stockout_date"] == "2026-11-28"


def test_moq_and_new_history():
    _, _, by = report()
    assert by["NEWBAG"]["history_days"] == 10 and by["NEWBAG"]["avg_daily"] == 3.0
    assert by["SPOON"]["days_of_stock"] is None and by["SPOON"]["order_qty"] == 0
    assert by["BOARD"]["excess_units"] == pytest.approx(400 - 1.0 * 180, abs=1)
    rows = [{"date": "2026-11-01", "sku": "A", "qty": "1"}]
    stock = [{"sku": "A", "on_hand": "0", "moq": "25", "case_pack": "6"}]

    class Opts:
        as_of = "2026-11-10"
        window = 10
        lead_time = 5
        cover_days = 5
        service_level = 0.95
        overstock_days = 180
        min_history = 1

    res = mod.compute(rows, stock, Opts)["results"][0]
    assert res["status"] == "stockout" and res["order_qty"] == 30  # MOQ 25 rounded up to case pack 6


def test_service_level_changes_safety():
    _, _, low = report("--service-level", "0.9")
    _, _, high = report("--service-level", "0.99")
    assert high["TEE-M"]["safety_stock"] > low["TEE-M"]["safety_stock"]
    assert mod.z_for(0.96) == 1.645


def test_as_of_and_window():
    _, data, by = report("--as-of", "2026-11-15", "--window", "30")
    assert data["as_of"] == "2026-11-15" and by["NEWBAG"]["history_days"] == 5


def test_purchase_order_csv(tmp_path):
    out = tmp_path / "po.csv"
    r = run_script(SKILL, SCRIPT, *ARGS, "--out", str(out))
    assert r.returncode == 1 and "Purchase order written" in r.stdout and "GHOST" in r.stdout
    rows = list(csv.DictReader(out.open()))
    assert [row["sku"] for row in rows] == ["MUG-1", "TEE-M"]


def test_nothing_to_order(tmp_path):
    stock = tmp_path / "stock.csv"
    stock.write_text("sku,on_hand\nCAP,60\n")
    r = run_script(SKILL, SCRIPT, "--sales", str(FX / "sales.csv"), "--stock", str(stock))
    assert r.returncode == 0


def test_errors(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")
    r = run_script(SKILL, SCRIPT, "--sales", str(bad), "--stock", str(FX / "stock.csv"))
    assert r.returncode == 2 and "cannot find column" in r.stderr
    assert run_script(SKILL, SCRIPT, *ARGS, "--service-level", "1.5").returncode == 2
    empty = tmp_path / "s.csv"
    empty.write_text("date,sku,qty\nnope,A,1\n")
    r = run_script(SKILL, SCRIPT, "--sales", str(empty), "--stock", str(FX / "stock.csv"))
    assert r.returncode == 2 and "no usable sales rows" in r.stderr


def test_parse_day_and_num():
    assert str(mod.parse_day("2026-11-23 14:03:22 +0600")) == "2026-11-23"
    assert str(mod.parse_day("2026-11-23T14:03:22Z")) == "2026-11-23"
    assert str(mod.parse_day("23/11/2026")) == "2026-11-23"
    assert mod.parse_day("soon") is None
    assert mod.num("1,250") == 1250 and mod.num("") == 0 and mod.num("x", 7) == 7


def test_budget_funds_stockouts_first_and_cuts_to_case_pack():
    _, full, _ = report()
    assert "budget" not in full
    _, data, by = report("--budget", "1000")
    assert by["MUG-1"]["order_qty"] == 108 and "suggested_qty" not in by["MUG-1"]
    tee = by["TEE-M"]
    assert tee["suggested_qty"] == 190 and tee["order_qty"] == 100  # (1000 - 324) / 6.5 -> 104 -> pack 10
    assert tee["order_value"] == 650 and tee["budget_note"] == "cut to fit budget"
    b = data["budget"]
    assert b == {
        "limit": 1000,
        "spent": 974,
        "remaining": 26,
        "lines_cut": 1,
        "lines_deferred": 0,
        "unfunded_value": 585,
    }
    assert data["order_value"] == 974


def test_budget_defers_lines_below_moq(tmp_path):
    _, data, by = report("--budget", "500")
    # 500 - 324 = 176 -> 27 units -> 20 after case pack, below the MOQ of 50.
    assert by["TEE-M"]["order_qty"] == 0 and by["TEE-M"]["budget_note"] == "deferred: over budget"
    assert data["budget"]["lines_deferred"] == 1 and data["order_lines"] == 1
    out = tmp_path / "po.csv"
    r = run_script(SKILL, SCRIPT, *ARGS, "--budget", "500", "--out", str(out))
    assert "Budget 500.00: spent 324.00" in r.stdout
    assert [row["sku"] for row in csv.DictReader(out.open())] == ["MUG-1"]


def test_budget_ignores_lines_without_cost():
    results = [
        {"sku": "A", "order_qty": 10, "order_value": None},
        {"sku": "B", "order_qty": 4, "order_value": 40},
    ]
    info = mod.apply_budget(results, {"A": (1, 0, 0), "B": (2, 0, 10)}, 25)
    assert results[0]["order_qty"] == 10 and "no unit cost" in results[0]["budget_note"]
    assert results[1]["order_qty"] == 2 and results[1]["suggested_qty"] == 4
    assert info["spent"] == 20 and info["unfunded_value"] == 20
    assert run_script(SKILL, SCRIPT, *ARGS, "--budget", "-1").returncode == 2
