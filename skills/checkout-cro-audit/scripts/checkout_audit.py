#!/usr/bin/env python3
"""Checklist-driven cart and checkout conversion audit. Read-only.

  checklist  print the audit checklist (markdown, or a JSON answers template with --json)
  scan       inspect a saved cart/checkout HTML page: field count, forced accounts,
             input types, autocomplete, labels, CAPTCHA, coupon field, pop-up and chat
             scripts, policy and contact links, payment methods, viewport
  score      turn filled-in checklist answers (JSON) into a prioritized fix list

Exit codes: 0 = nothing at or above --fail-on, 1 = findings / open P1 items, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

# id, area, priority, check, why/fix
CHECKLIST = [
    (
        "cart-shipping-cost",
        "Cart",
        "P1",
        "Shipping cost or a reliable estimate is shown in the cart",
        "Show the delivery charge (inside/outside city) in the cart; "
        "surprise costs are the top abandonment reason",
    ),
    (
        "cart-total-clear",
        "Cart",
        "P1",
        "Cart shows the full total including tax, COD and other fees",
        "Show every fee before checkout; add a line per fee",
    ),
    (
        "cart-coupon-collapsed",
        "Cart",
        "P2",
        "Coupon field is collapsed behind a text link",
        "Collapse it ('Have a coupon?') so shoppers do not leave to hunt for codes",
    ),
    (
        "cart-mobile-cta",
        "Cart",
        "P2",
        "Checkout button is visible without scrolling on mobile",
        "Add a sticky or top checkout button on small screens",
    ),
    (
        "cart-edit",
        "Cart",
        "P3",
        "Quantity can be changed and items removed easily",
        "Use +/- steppers and an obvious remove link",
    ),
    (
        "guest-checkout",
        "Checkout",
        "P1",
        "Guest checkout is available (no forced account creation)",
        "Allow guest checkout; offer account creation after the order",
    ),
    (
        "field-count",
        "Checkout",
        "P1",
        "The form shows 12 or fewer fields by default",
        "Remove or hide optional fields (company, address line 2, second phone); "
        "merge first/last name if possible",
    ),
    (
        "address-line2-collapsed",
        "Checkout",
        "P2",
        "Address line 2 and company are hidden behind a link or removed",
        "Collapse optional address fields",
    ),
    (
        "autofill",
        "Checkout",
        "P2",
        "Fields have correct autocomplete attributes so browser autofill works",
        "Set autocomplete=name/email/tel/street-address/address-level2/postal-code/country",
    ),
    (
        "input-types",
        "Checkout",
        "P2",
        "Email and phone fields use type=email and type=tel",
        "Correct input types open the right mobile keyboard",
    ),
    (
        "labels",
        "Checkout",
        "P2",
        "Every field has a visible label (not placeholder-only)",
        "Add labels; placeholders disappear while typing and hurt accessibility",
    ),
    (
        "inline-validation",
        "Checkout",
        "P2",
        "Errors are shown inline next to the field with a clear message",
        "Validate on blur and keep entered data",
    ),
    (
        "phone-format",
        "Checkout",
        "P2",
        "Phone field accepts local formats (e.g. 01XXXXXXXXX or +8801XXXXXXXXX)",
        "Normalize on the server instead of rejecting spaces, dashes or country codes",
    ),
    (
        "delivery-date",
        "Checkout",
        "P2",
        "Estimated delivery time is shown before payment",
        "Show 'Delivery in 1-2 days inside Dhaka, 3-5 days outside' or similar",
    ),
    (
        "captcha",
        "Checkout",
        "P2",
        "No CAPTCHA challenge for normal shoppers on checkout",
        "Use invisible/score-based bot protection or rate limiting instead",
    ),
    (
        "progress",
        "Checkout",
        "P3",
        "Single page, or multi-step with a clear progress indicator",
        "Show steps and keep the order summary visible",
    ),
    (
        "payment-methods",
        "Payment & trust",
        "P1",
        "Locally preferred payment methods are offered",
        "Offer what customers use: COD, bKash/Nagad, cards, wallets, PayPal depending on market",
    ),
    (
        "cod-fee-clear",
        "Payment & trust",
        "P1",
        "COD fees or advance delivery charges are explained before the last step",
        "State the rule and amount in the cart and next to the payment option",
    ),
    (
        "express-pay",
        "Payment & trust",
        "P2",
        "Express wallets (Apple Pay, Google Pay, Shop Pay, PayPal) where available",
        "Enable express buttons on cart and checkout",
    ),
    (
        "return-policy-link",
        "Payment & trust",
        "P2",
        "Returns/refund policy and contact (phone/WhatsApp) linked from checkout",
        "Link policies in the checkout footer and next to the order button",
    ),
    (
        "payment-error-recovery",
        "Payment & trust",
        "P2",
        "A failed payment keeps the order data and offers another method",
        "Return to checkout with the cart intact and suggest COD or another gateway",
    ),
    (
        "trust-near-payment",
        "Payment & trust",
        "P3",
        "Security and trust cues near the payment fields",
        "Short line on secure payment and real reviews count, not a wall of badges",
    ),
    (
        "checkout-speed",
        "Performance",
        "P2",
        "Checkout LCP under 2.5 s on a mid-range phone",
        "Remove non-essential scripts from cart/checkout; see store-speed-audit",
    ),
    (
        "third-party-scripts",
        "Performance",
        "P2",
        "No chat widgets, heatmaps or pop-up tools on checkout",
        "Disable them on cart/checkout pages; they slow input and can capture form data",
    ),
    (
        "no-popups",
        "Performance",
        "P2",
        "No newsletter, spin-wheel or exit-intent pop-ups on cart/checkout",
        "Exclude cart and checkout URLs in the pop-up tool",
    ),
    (
        "tap-targets",
        "Performance",
        "P3",
        "Inputs at least 44 px tall with 16 px+ font (avoids iOS zoom)",
        "Adjust theme CSS for inputs and buttons",
    ),
    (
        "viewport",
        "Performance",
        "P1",
        "Page has a responsive viewport meta tag",
        'Add <meta name="viewport" content="width=device-width, initial-scale=1">',
    ),
    (
        "confirmation",
        "Post-purchase",
        "P3",
        "Confirmation page, email and SMS show order number and next steps",
        "Include delivery estimate and support contact",
    ),
    (
        "abandoned-cart",
        "Post-purchase",
        "P2",
        "Abandoned cart recovery (email/SMS/WhatsApp) with consent",
        "Send 1-3 reminders within 48 hours to shoppers who opted in",
    ),
]
PRIORITY_WEIGHT = {"P1": 3, "P2": 2, "P3": 1}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}
ANSWERS = {"yes", "no", "partial", "na"}

AUTOCOMPLETE_HINTS = [
    (re.compile(r"e-?mail"), "email"),
    (re.compile(r"phone|mobile|\btel\b|_tel|tel_"), "tel"),
    (re.compile(r"first_?name|fname|given"), "given-name"),
    (re.compile(r"last_?name|lname|surname|family"), "family-name"),
    (re.compile(r"address_?1|address_?line_?1|street|address$"), "address-line1"),
    (re.compile(r"city|town"), "address-level2"),
    (re.compile(r"post_?code|postal|zip"), "postal-code"),
    (re.compile(r"country"), "country"),
]
POPUP_CHAT_HOSTS = {
    "tawk.to": "chat widget",
    "embed.tawk.to": "chat widget",
    "widget.intercom.io": "chat widget",
    "client.crisp.chat": "chat widget",
    "code.tidio.co": "chat widget",
    "static.zdassets.com": "chat widget",
    "connect.facebook.net": "Meta pixel / Messenger",
    "static.hotjar.com": "session recording",
    "script.hotjar.com": "session recording",
    "www.clarity.ms": "session recording",
    "widget.privy.com": "pop-up tool",
    "a.omappapi.com": "pop-up tool",
    "static.klaviyo.com": "pop-up / email tool",
    "cdn.onesignal.com": "push prompt",
    "sumo.com": "pop-up tool",
}
CAPTCHA_RE = re.compile(
    r"g-recaptcha|recaptcha/api|h-captcha|hcaptcha\.com|cf-turnstile|challenges\.cloudflare", re.I
)
PAYMENT_WORDS = {
    "cash on delivery": "COD",
    "bkash": "bKash",
    "nagad": "Nagad",
    "rocket": "Rocket",
    "sslcommerz": "SSLCOMMERZ",
    "aamarpay": "aamarPay",
    "stripe": "Stripe",
    "paypal": "PayPal",
    "apple pay": "Apple Pay",
    "google pay": "Google Pay",
    "shop pay": "Shop Pay",
    "razorpay": "Razorpay",
    "klarna": "Klarna",
}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inputs: list[dict] = []
        self.label_for: set[str] = set()
        self.label_depth = 0
        self.scripts: list[str] = []
        self.inline_scripts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.viewport = False
        self.text: list[str] = []
        self._in_script = False
        self._in_a: str | None = None
        self._a_text: list[str] = []
        self.classes: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if a.get("class"):
            self.classes.append(a["class"])
        if tag == "label":
            self.label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            a["_tag"] = tag
            a["_in_label"] = self.label_depth > 0
            self.inputs.append(a)
        elif tag == "script":
            self._in_script = True
            if a.get("src"):
                self.scripts.append(a["src"])
        elif tag == "meta" and a.get("name", "").lower() == "viewport":
            self.viewport = True
        elif tag == "a":
            self._in_a = a.get("href", "")
            self._a_text = []
        elif tag == "iframe" and a.get("src"):
            self.scripts.append(a["src"])

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1
        elif tag == "script":
            self._in_script = False
        elif tag == "a" and self._in_a is not None:
            self.links.append((self._in_a, " ".join(self._a_text).strip()))
            self._in_a = None

    def handle_data(self, data):
        if self._in_script:
            self.inline_scripts.append(data)
            return
        self.text.append(data)
        if self._in_a is not None:
            self._a_text.append(data.strip())


def field_key(f: dict) -> str:
    return f"{f.get('name', '')} {f.get('id', '')}".lower()


def scan_html(html: str, site_host: str = "", max_fields: int = 12) -> dict:
    parser = PageParser()
    parser.feed(html)
    findings: list[dict] = []

    def add(sev, check, title, fix, items=None):
        findings.append({"severity": sev, "check": check, "title": title, "fix": fix, "items": items or []})

    skip_types = {"hidden", "submit", "button", "image", "reset"}
    fields = [f for f in parser.inputs if f.get("type", "text").lower() not in skip_types]
    text_fields = [f for f in fields if f.get("type", "text").lower() not in ("checkbox", "radio")]
    named = [
        f for f in text_fields if not re.search(r"coupon|search|\bs\b|newsletter|quantity|qty", field_key(f))
    ]
    if len(named) > max_fields:
        add(
            "high",
            "field-count",
            f"{len(named)} form fields shown (target {max_fields} or fewer)",
            "Remove or collapse optional fields",
            [f.get("name") or f.get("id") or f["_tag"] for f in named],
        )

    passwords = [f for f in fields if f.get("type", "").lower() == "password"]
    optional_account = any(
        re.search(r"createaccount|create_account|create-account", field_key(f)) for f in fields
    )
    if passwords and not optional_account:
        add(
            "high",
            "guest-checkout",
            "password field without an optional 'create account' checkbox: account creation may be forced",
            "Enable guest checkout (WooCommerce: Settings > Accounts & Privacy)",
        )
    elif passwords:
        add("info", "guest-checkout", "account creation is optional (create account checkbox found)", "")

    wrong_type, missing_ac, no_label = [], [], []
    for f in text_fields:
        key = field_key(f)
        ftype = f.get("type", "text").lower()
        label = f.get("name") or f.get("id") or f["_tag"]
        if re.search(r"e-?mail", key) and f["_tag"] == "input" and ftype != "email":
            wrong_type.append(f"{label} (type={ftype}, want email)")
        if re.search(r"phone|mobile|\btel\b", key) and f["_tag"] == "input" and ftype != "tel":
            wrong_type.append(f"{label} (type={ftype}, want tel)")
        expected = next((ac for rx, ac in AUTOCOMPLETE_HINTS if rx.search(key)), None)
        ac = f.get("autocomplete", "").lower()
        if expected and (not ac or ac in ("off", "nope", "false")):
            missing_ac.append(f"{label} (want autocomplete={expected})")
        labelled = (
            f["_in_label"]
            or (f.get("id") and f["id"] in parser.label_for)
            or f.get("aria-label")
            or f.get("aria-labelledby")
        )
        if not labelled:
            no_label.append(label + (" (placeholder only)" if f.get("placeholder") else ""))
    if wrong_type:
        add(
            "medium",
            "input-types",
            "email/phone fields with the wrong input type",
            "Use type=email and type=tel",
            wrong_type,
        )
    if missing_ac:
        add(
            "medium",
            "autofill",
            "fields without autocomplete (autofill will not work well)",
            "Add autocomplete tokens",
            missing_ac,
        )
    if no_label:
        add("medium", "labels", "fields without a label", "Add <label for=...> or aria-label", no_label)

    optional = [
        f.get("name") or f.get("id")
        for f in text_fields
        if re.search(r"address_?2|address_?line_?2|apartment|company", field_key(f))
    ]
    if optional:
        add(
            "low",
            "address-line2-collapsed",
            "optional address/company fields are visible",
            "Collapse behind a link",
            optional,
        )
    if any(re.search(r"coupon|discount|promo", field_key(f)) for f in text_fields):
        add(
            "low",
            "cart-coupon-collapsed",
            "coupon field is present",
            "Make sure it is collapsed behind a link",
        )

    all_scripts = (
        " ".join(parser.scripts) + " " + " ".join(parser.classes) + " " + " ".join(parser.inline_scripts)
    )
    if CAPTCHA_RE.search(all_scripts):
        add(
            "medium",
            "captcha",
            "CAPTCHA detected on the page",
            "Use invisible protection or rate limiting on checkout",
        )

    hosts = sorted({urlparse(s).netloc.lower() for s in parser.scripts if urlparse(s).netloc})
    own = site_host.lower().lstrip(".")
    third = [h for h in hosts if not own or not (h == own or h.endswith("." + own))]
    distracting = sorted({f"{h} ({POPUP_CHAT_HOSTS[h]})" for h in third if h in POPUP_CHAT_HOSTS})
    if distracting:
        check = (
            "no-popups" if any("pop-up" in d or "push" in d for d in distracting) else "third-party-scripts"
        )
        add(
            "medium",
            check,
            "chat, recording or pop-up scripts load on this page",
            "Exclude cart/checkout in each tool",
            distracting,
        )
    if len(third) > 10:
        add(
            "low",
            "third-party-scripts",
            f"{len(third)} third-party script hosts",
            "Audit and remove what checkout does not need",
            third,
        )

    if not parser.viewport:
        add(
            "high",
            "viewport",
            "no responsive viewport meta tag",
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
        )

    links_text = " ".join(f"{h} {t}" for h, t in parser.links).lower()
    if not re.search(r"refund|return", links_text):
        add(
            "medium",
            "return-policy-link",
            "no link to a returns/refund policy",
            "Link the policy near the order button",
        )
    if not re.search(r"tel:|wa\.me|whatsapp|m\.me|contact", links_text):
        add(
            "low",
            "return-policy-link",
            "no phone, WhatsApp or contact link",
            "Show a support number or WhatsApp link",
        )

    body = " ".join(parser.text).lower()
    methods = sorted({label for word, label in PAYMENT_WORDS.items() if word in body or word in links_text})
    if re.search(r"\bcod\b", body) and "COD" not in methods:
        methods.append("COD")
    if methods:
        add("info", "payment-methods", "payment methods mentioned: " + ", ".join(sorted(methods)), "")
    else:
        add(
            "low",
            "payment-methods",
            "no payment methods detected in the page text",
            "Check the payment step manually",
        )

    findings.sort(key=lambda f: -SEVERITY_ORDER[f["severity"]])
    return {
        "fields": len(named),
        "third_party_hosts": third,
        "payment_methods": sorted(methods),
        "findings": findings,
    }


def score_answers(answers: dict) -> dict:
    ids = {c[0] for c in CHECKLIST}
    unknown = sorted(set(answers) - ids)
    bad_values = sorted(k for k, v in answers.items() if k in ids and str(v).lower() not in ANSWERS)
    total = got = 0
    fixes, unanswered = [], []
    for cid, area, prio, check, fix in CHECKLIST:
        value = str(answers.get(cid, "")).lower()
        if value not in ANSWERS:
            unanswered.append(cid)
            continue
        if value == "na":
            continue
        weight = PRIORITY_WEIGHT[prio]
        total += weight
        got += weight if value == "yes" else weight / 2 if value == "partial" else 0
        if value in ("no", "partial"):
            fixes.append(
                {"id": cid, "area": area, "priority": prio, "answer": value, "check": check, "fix": fix}
            )
    fixes.sort(key=lambda f: (f["priority"], f["answer"] != "no"))
    return {
        "score": round(100 * got / total) if total else None,
        "fixes": fixes,
        "unanswered": unanswered,
        "unknown_ids": unknown,
        "invalid_values": bad_values,
    }


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def cmd_checklist(args) -> int:
    if args.json:
        print(json.dumps({c[0]: "" for c in CHECKLIST}, indent=2))
        return 0
    area = None
    for cid, a, prio, check, _ in CHECKLIST:
        if a != area:
            print(f"\n## {a}\n")
            area = a
        print(f"- [ ] `{cid}` ({prio}) {check}")
    return 0


def cmd_scan(args) -> int:
    try:
        report = scan_html(read_text(args.html), args.site_host, args.max_fields)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['fields']} input fields, {len(report['third_party_hosts'])} third-party hosts")
        for f in report["findings"]:
            print(f"[{f['severity'].upper()}] ({f['check']}) {f['title']}")
            if f["fix"]:
                print(f"    fix: {f['fix']}")
            for item in f["items"][:12]:
                print(f"    - {item}")
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f["severity"]] >= threshold for f in report["findings"]) else 0


def cmd_score(args) -> int:
    try:
        answers = json.loads(read_text(args.answers))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(answers, dict):
        print("error: answers must be a JSON object of id -> yes/no/partial/na", file=sys.stderr)
        return 2
    report = score_answers(answers)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Checkout score: {report['score']}/100 ({len(report['fixes'])} items to fix)")
        for f in report["fixes"]:
            print(f"  {f['priority']} [{f['answer']}] {f['area']}: {f['check']}\n      fix: {f['fix']}")
        if report["unanswered"]:
            print(f"Unanswered: {', '.join(report['unanswered'])}")
        for key in ("unknown_ids", "invalid_values"):
            if report[key]:
                print(f"Ignored ({key.replace('_', ' ')}): {', '.join(report[key])}")
    return 1 if any(f["priority"] == "P1" for f in report["fixes"]) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("checklist", help="print the checklist")
    c.add_argument("--json", action="store_true", help="print an empty answers template")
    c.set_defaults(func=cmd_checklist)
    s = sub.add_parser("scan", help="scan a saved cart or checkout HTML page")
    s.add_argument("html", help="saved page HTML, or - for stdin")
    s.add_argument("--site-host", default="", help="store domain; scripts from it are not third-party")
    s.add_argument("--max-fields", type=int, default=12)
    s.add_argument("--fail-on", choices=list(SEVERITY_ORDER), default="medium")
    s.add_argument("--json", action="store_true", help="print JSON")
    s.set_defaults(func=cmd_scan)
    sc = sub.add_parser("score", help="score checklist answers (JSON id -> yes/no/partial/na)")
    sc.add_argument("answers", help="answers JSON file, or - for stdin")
    sc.add_argument("--json", action="store_true", help="print JSON")
    sc.set_defaults(func=cmd_score)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
