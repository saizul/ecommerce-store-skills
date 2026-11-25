import json
import re

from conftest import FIXTURES, SKILLS, load_script, run_script

SKILL = "checkout-cro-audit"
SCRIPT = "checkout_audit.py"
mod = load_script(SKILL, SCRIPT)
FX = FIXTURES / SKILL


def scan(path, *extra):
    r = run_script(SKILL, SCRIPT, "scan", str(path), "--json", *extra)
    return r.returncode, json.loads(r.stdout)


def checks(report, severity=None):
    return {f["check"] for f in report["findings"] if severity in (None, f["severity"])}


def test_checklist_ids_documented():
    doc = (SKILLS / SKILL / "references" / "checklist.md").read_text()
    documented = set(re.findall(r"^\| `([a-z0-9-]+)` \|", doc, re.M))
    ids = [c[0] for c in mod.CHECKLIST]
    assert len(ids) == len(set(ids)) == 29
    assert documented == set(ids)
    assert all(c[2] in mod.PRIORITY_WEIGHT for c in mod.CHECKLIST)


def test_good_checkout():
    rc, report = scan(FX / "good-checkout.html", "--site-host", "shop.example.com")
    assert rc == 0
    assert report["fields"] == 8  # includes the optional account password
    assert report["third_party_hosts"] == ["js.stripe.com"]
    assert report["payment_methods"] == ["COD", "Stripe", "bKash"]
    assert {f["severity"] for f in report["findings"]} == {"info"}


def test_bad_checkout():
    rc, report = scan(FX / "bad-checkout.html")
    assert rc == 1
    assert {"field-count", "guest-checkout", "viewport"} <= checks(report, "high")
    assert {"input-types", "autofill", "labels", "captcha", "no-popups", "return-policy-link"} <= checks(
        report, "medium"
    )
    assert {"address-line2-collapsed", "cart-coupon-collapsed"} <= checks(report, "low")
    types = next(f for f in report["findings"] if f["check"] == "input-types")["items"]
    assert "phone (type=number, want tel)" in types
    popups = next(f for f in report["findings"] if f["check"] == "no-popups")["items"]
    assert any("tawk" in p for p in popups) and any("privy" in p for p in popups)
    # coupon field does not count against the field budget
    fields = next(f for f in report["findings"] if f["check"] == "field-count")["items"]
    assert "coupon_code" not in fields


def test_fail_on_threshold():
    assert (
        run_script(SKILL, SCRIPT, "scan", str(FX / "bad-checkout.html"), "--fail-on", "high").returncode == 1
    )
    good = str(FX / "good-checkout.html")
    assert run_script(SKILL, SCRIPT, "scan", good, "--fail-on", "info").returncode == 1
    assert run_script(SKILL, SCRIPT, "scan", good, "--max-fields", "5", "--json").returncode == 1


def test_site_host_subdomains():
    html = '<meta name="viewport" content="x"><script src="https://cdn.shop.example.com/a.js"></script>'
    assert mod.scan_html(html, "shop.example.com")["third_party_hosts"] == []
    assert mod.scan_html(html)["third_party_hosts"] == ["cdn.shop.example.com"]


def test_score():
    r = run_script(SKILL, SCRIPT, "score", str(FX / "answers.json"), "--json")
    report = json.loads(r.stdout)
    assert r.returncode == 1  # open P1 items
    ids = [f["id"] for f in report["fixes"]]
    assert ids[:3] == ["cart-shipping-cost", "field-count", "cod-fee-clear"]
    assert ids[-1] == "tap-targets"
    assert report["unknown_ids"] == ["made-up-id"] and report["invalid_values"] == ["viewport"]
    assert "viewport" in report["unanswered"] and "express-pay" not in report["unanswered"]
    # P1: 3 yes + 1 partial of 6 answered (10.5/18); P2: 1 partial of 2 (1/4); P3: 0/1
    assert report["score"] == round(100 * (10.5 + 1) / (18 + 4 + 1))


def test_score_all_yes_and_text(tmp_path):
    f = tmp_path / "a.json"
    f.write_text(json.dumps({c[0]: "yes" for c in mod.CHECKLIST}))
    r = run_script(SKILL, SCRIPT, "score", str(f))
    assert r.returncode == 0 and "100/100" in r.stdout
    f.write_text("[1, 2]")
    assert run_script(SKILL, SCRIPT, "score", str(f)).returncode == 2
    f.write_text("{bad")
    assert run_script(SKILL, SCRIPT, "score", str(f)).returncode == 2


def test_checklist_command():
    r = run_script(SKILL, SCRIPT, "checklist")
    assert r.returncode == 0 and "## Payment & trust" in r.stdout and "`guest-checkout` (P1)" in r.stdout
    template = json.loads(run_script(SKILL, SCRIPT, "checklist", "--json").stdout)
    assert len(template) == 29 and set(template.values()) == {""}


def test_text_scan_output():
    r = run_script(SKILL, SCRIPT, "scan", str(FX / "bad-checkout.html"))
    assert "[HIGH] (guest-checkout)" in r.stdout
    assert run_script(SKILL, SCRIPT, "scan", "/nonexistent/x.html").returncode == 2
