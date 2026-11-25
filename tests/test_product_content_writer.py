import json

from conftest import FIXTURES, load_script, run_script

SKILL = "product-content-writer"
SCRIPT = "score_content.py"
mod = load_script(SKILL, SCRIPT)
FX = FIXTURES / SKILL


def csv_results(*extra):
    r = run_script(SKILL, SCRIPT, "--csv", str(FX / "products.csv"), "--json", *extra)
    data = json.loads(r.stdout)
    return r.returncode, data, {x["id"]: x for x in data["results"]}


def test_strip_html_counts_bullets():
    text, bullets = mod.strip_html(
        "<p>A&amp;B</p><ul><li>one</li><li class='x'>two</li></ul><script>x()</script>"
    )
    assert bullets == 2 and "A&B" in text and "- one" in text and "x()" not in text


def test_syllables_and_flesch():
    assert mod.syllables("cat") == 1 and mod.syllables("table") >= 1 and mod.syllables("organic") == 3
    easy = "The cat sat on the mat. It was a warm day. The dog ran to the park and back. " * 3
    fre, wps = mod.flesch(easy)
    assert fre is not None and fre > 80 and wps < 10
    assert mod.flesch("Too short.")[0] is None


def test_good_text_scores_high():
    r = run_script(
        SKILL,
        SCRIPT,
        "--text",
        str(FX / "good.html"),
        "--title",
        "Acme Organic Cotton T-Shirt for Men",
        "--keyword",
        "organic cotton t-shirt",
        "--json",
    )
    res = json.loads(r.stdout)["results"][0]
    assert r.returncode == 0 and res["score"] >= 90 and res["grade"] == "A"
    assert res["bullets"] == 5 and res["specs_found"] >= 3 and 0.5 <= res["keyword_density"] <= 3


def test_catalogue_scores_and_order():
    rc, data, by_id = csv_results()
    assert rc == 1 and data["products"] == 5
    assert data["results"][0]["id"] == "WAL-1"  # worst first
    assert by_id["TEE-1"]["score"] >= 90
    wal = by_id["WAL-1"]
    assert wal["score"] < 20 and wal["penalty"] >= 10
    joined = " ".join(wal["fixes"])
    assert (
        "Thin description" in joined
        and "ALL-CAPS" in joined
        and "filler" in joined
        and "exclamation" in joined
    )


def test_duplicate_descriptions():
    _, _, by_id = csv_results()
    assert by_id["MUG-2"]["duplicate_of"] == "MUG-1"
    assert "duplicate_of" not in by_id["MUG-1"]
    assert by_id["MUG-2"]["score"] == by_id["MUG-1"]["score"] - 10


def test_bangla_product():
    _, _, by_id = csv_results()
    saree = by_id["SAREE-1"]
    assert saree["readability_skipped"] is True and saree["flesch"] is None
    assert saree["words"] > 30  # vowel signs do not split words
    assert not any("first 100 words" in f for f in saree["fixes"])  # suffix শাড়িটি matches keyword
    assert saree["keyword_density"] > 0


def test_keyword_stuffing():
    body = ("Leather wallet. " * 30) + "It is a leather wallet made of 100% leather and 2 mm thick."
    res = mod.score_product("Acme Leather Wallet Brown", body, "leather wallet")
    assert res["keyword_density"] > 3 and any("stuffed" in f for f in res["fixes"])


def test_no_keyword_scales_to_80():
    res = mod.score_product("Acme Stoneware Coffee Mug 350 ml", (FX / "good.html").read_text())
    assert "keyword" not in res["parts"] and res["score"] >= 90


def test_min_score_and_text_output():
    rc, _, _ = csv_results("--min-score", "0")
    assert rc == 0
    r = run_script(SKILL, SCRIPT, "--csv", str(FX / "products.csv"))
    assert "average score" in r.stdout and "WAL-1" in r.stdout


def test_errors(tmp_path):
    bad = tmp_path / "x.csv"
    bad.write_text("foo,bar\n1,2\n")
    r = run_script(SKILL, SCRIPT, "--csv", str(bad))
    assert r.returncode == 2 and "needs columns" in r.stderr
    assert run_script(SKILL, SCRIPT, "--text", str(tmp_path / "missing.txt")).returncode == 2
    r = run_script(SKILL, SCRIPT, "--text", "-", "--title", "Short", stdin="Tiny text.")
    assert r.returncode == 1
