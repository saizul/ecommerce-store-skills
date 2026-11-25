#!/usr/bin/env python3
"""Score product titles and descriptions (0-100) with concrete fixes. Read-only.

Measures description length, title length, focus keyword use (title, first 100 words,
density), readability (Flesch reading ease, sentence length; skipped for Bangla and other
non-Latin text), structure (bullets, long paragraphs), specifics (numbers with units),
filler phrases, shouting, and duplicate descriptions across a catalogue.

Input: a single description (--text FILE with --title/--keyword) or a WooCommerce/Shopify
product CSV export (one product per row; HTML is stripped).

Exit codes: 0 = every product scores at least --min-score, 1 = some below, 2 = error.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys

FLUFF = [
    "high quality",
    "best quality",
    "premium quality",
    "top quality",
    "world class",
    "world-class",
    "best in class",
    "amazing",
    "awesome",
    "perfect for everyone",
    "look no further",
    "second to none",
    "state of the art",
    "state-of-the-art",
    "100% satisfaction",
    "must have",
    "must-have",
    "unbeatable",
    "best price",
    "cheapest",
]
UNIT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:mm|cm|m|km|in|inch|inches|ft|g|gm|kg|lb|lbs|oz|ml|l|ltr|litre|liter|gsm|mah|w|kw|v|"
    r"hz|gb|tb|mb|mp|%|pcs|pieces|pack|years?|months?|days?|hours?|hrs?|°c|c)\b",
    re.I,
)
COLUMNS = {
    "id": ["sku", "id", "handle", "variant sku"],
    "title": ["name", "title", "product name"],
    "description": ["description", "body (html)", "body_html", "body"],
    "short": ["short description", "short_description", "excerpt"],
    "keyword": [
        "keyword",
        "focus keyword",
        "focus_keyword",
        "focus keyphrase",
        "meta: rank_math_focus_keyword",
    ],
}
NON_LATIN_RE = re.compile(r"[ঀ-৿ऀ-ॿ؀-ۿ]")  # Bengali, Devanagari, Arabic


def strip_html(text: str) -> tuple[str, int]:
    """Return plain text (block tags become newlines) and the number of <li> items."""
    text = text or ""
    bullets = len(re.findall(r"<li[\s>]", text, re.I))
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<\s*(br|/p|/li|/h\d|/div|/tr)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip(), bullets


def words_of(text: str) -> list[str]:
    # \w misses Indic vowel signs (combining marks), so include those script blocks explicitly
    return re.findall(r"[\w\u0900-\u097F\u0980-\u09FF'’-]+", text, re.U)


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def sentences_of(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+|\n+", text)
    return [p for p in parts if len(words_of(p)) >= 3 and not p.strip().startswith(("-", "*", "•"))]


def flesch(text: str) -> tuple[float | None, float]:
    sents = sentences_of(text)
    words = [w for s in sents for w in words_of(s)]
    if len(sents) < 2 or len(words) < 30:
        return None, (len(words) / len(sents) if sents else 0.0)
    syl = sum(syllables(w) for w in words)
    wps = len(words) / len(sents)
    return round(206.835 - 1.015 * wps - 84.6 * (syl / len(words)), 1), round(wps, 1)


def score_product(title: str, description: str, keyword: str = "", opts=None) -> dict:
    min_words = getattr(opts, "min_words", 120)
    max_words = getattr(opts, "max_words", 700)
    plain, li_count = strip_html(description)
    words = words_of(plain)
    n = len(words)
    fixes: list[str] = []
    parts: dict[str, float] = {}

    # length (20)
    if n >= min_words:
        parts["length"] = 20 if n <= max_words else 15
        if n > max_words:
            fixes.append(
                f"Description is {n} words; trim to under {max_words} or move specs into bullets/tabs"
            )
    elif n >= min_words / 2:
        parts["length"] = 10
        fixes.append(f"Description is {n} words; aim for {min_words}+ (benefits, use cases, specs, care)")
    else:
        parts["length"] = 0
        fixes.append(f"Thin description ({n} words); write at least {min_words} words of original copy")

    # title (15)
    t = (title or "").strip()
    tl = len(t)
    if 25 <= tl <= 90:
        parts["title"] = 15
    elif 15 <= tl <= 150:
        parts["title"] = 8
        fixes.append(
            f"Title is {tl} characters; 25-90 works best (brand + product type + key attribute + variant)"
        )
    else:
        parts["title"] = 0
        fixes.append(f"Title is {tl} characters; rewrite as brand + product type + key attribute + variant")

    # keyword (20)
    kw = (keyword or "").strip().lower()
    density = None
    if kw:
        text_l = " ".join(words).lower()
        # Bangla/Hindi attach suffixes (শাড়িটি, শাড়ির), so only Latin keywords need a word end
        kw_re = re.compile(r"(?<!\w)" + re.escape(kw) + ("" if NON_LATIN_RE.search(kw) else r"(?!\w)"))
        hits = len(kw_re.findall(text_l))
        density = round(100 * hits / n, 2) if n else 0.0  # occurrences per 100 words
        k = 0
        if kw in t.lower():
            k += 8
        else:
            fixes.append(f"Put the keyword '{keyword}' in the title, near the start")
        first = " ".join(words[:100]).lower()
        if kw_re.search(first):
            k += 6
        else:
            fixes.append(f"Use '{keyword}' in the first 100 words")
        if 0.5 <= density <= 3:
            k += 6
        elif density > 3:
            fixes.append(f"Keyword density {density}% looks stuffed; use synonyms and natural phrasing")
        elif hits:
            k += 3
        parts["keyword"] = k

    # readability (20)
    non_latin = len(NON_LATIN_RE.findall(plain)) > 0.3 * max(1, len(re.findall(r"\w", plain)))
    fre, wps = (None, 0.0) if non_latin else flesch(plain)
    if non_latin:
        parts["readability"] = 14
    elif fre is None:
        parts["readability"] = 10
    else:
        parts["readability"] = 20 if fre >= 60 else 15 if fre >= 50 else 8 if fre >= 30 else 0
        if fre < 50:
            fixes.append(f"Hard to read (Flesch {fre}); use shorter sentences and everyday words")
        if wps > 22:
            parts["readability"] = max(0, parts["readability"] - 4)
            fixes.append(f"Average sentence is {wps} words; keep most under 20")

    # structure (15)
    bullet_lines = len(re.findall(r"^\s*(?:[-*•✓✔]|\d+[.)])\s+\S", plain, re.M))
    bullets = max(li_count, bullet_lines)
    s = 0
    if 3 <= bullets <= 10:
        s += 10
    elif bullets:
        s += 5
        fixes.append(f"{bullets} bullet(s); use 3-7 scannable bullets for key benefits/specs")
    else:
        fixes.append("Add 3-7 bullets for the key benefits and specs")
    paragraphs = [p for p in re.split(r"\n\s*\n", plain) if p.strip()]
    longest = max((len(words_of(p)) for p in paragraphs), default=0)
    if longest <= 80:
        s += 5
    else:
        fixes.append(f"Longest paragraph is {longest} words; split into 2-4 sentence paragraphs")
    parts["structure"] = s

    # specifics (10)
    specs = len(UNIT_RE.findall(plain))
    parts["specifics"] = 10 if specs >= 2 else 5 if specs == 1 else 0
    if specs < 2:
        fixes.append("Add concrete specs with units (size, weight, capacity, material %, warranty)")

    # penalties
    penalty = 0
    low = plain.lower() + " " + t.lower()
    fluff = sorted({f for f in FLUFF if f in low})
    if fluff:
        penalty += min(10, 2 * len(fluff))
        fixes.append("Replace filler ('" + "', '".join(fluff) + "') with a specific claim or proof")
    caps = [w for w in words_of(plain + " " + t) if len(w) >= 4 and w.isupper() and w.isalpha()]
    if len(caps) > 2:
        penalty += 3
        fixes.append(f"{len(caps)} ALL-CAPS words; use normal case")
    if "!!" in plain or "!!" in t:
        penalty += 2
        fixes.append("Drop repeated exclamation marks")

    max_points = 100 if kw else 80
    raw = sum(parts.values())
    score = max(0, round(100 * raw / max_points) - penalty)
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"
    return {
        "title": t,
        "score": score,
        "grade": grade,
        "words": n,
        "title_chars": tl,
        "bullets": bullets,
        "flesch": fre,
        "avg_sentence_words": wps,
        "keyword_density": density,
        "specs_found": specs,
        "readability_skipped": non_latin,
        "parts": parts,
        "penalty": penalty,
        "fixes": fixes,
        "_hash": hashlib.sha1(re.sub(r"\W+", "", plain.lower()).encode()).hexdigest() if n >= 20 else None,
    }


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        lookup = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
        missing = [k for k in ("title", "description") if not any(a in lookup for a in COLUMNS[k])]
        if missing:
            raise ValueError(f"CSV needs columns for {missing}; found {list(lookup)}")
        rows = []
        for i, row in enumerate(reader, start=2):
            item = {"line": i}
            for key, aliases in COLUMNS.items():
                item[key] = next(
                    (row[lookup[a]] or "" for a in aliases if a in lookup and row[lookup[a]]), ""
                )
            if not item["title"] and not item["description"]:
                continue  # Shopify exports extra rows per image/variant
            item["description"] = "\n\n".join(x for x in (item["short"], item["description"]) if x)
            rows.append(item)
        return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="product CSV export (WooCommerce or Shopify)")
    src.add_argument("--text", help="file with one description (plain text or HTML), or - for stdin")
    p.add_argument("--title", default="", help="product title (with --text)")
    p.add_argument("--keyword", default="", help="focus keyword (with --text, or default for CSV rows)")
    p.add_argument("--min-words", type=int, default=120)
    p.add_argument("--max-words", type=int, default=700)
    p.add_argument("--min-score", type=int, default=60, help="exit 1 if any product scores lower")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        if args.csv:
            rows = read_csv(args.csv)
        else:
            if args.text == "-":
                text = sys.stdin.read()
            else:
                with open(args.text, encoding="utf-8") as fh:
                    text = fh.read()
            rows = [{"line": 1, "id": "", "title": args.title, "description": text, "keyword": args.keyword}]
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("error: no products found", file=sys.stderr)
        return 2

    results = []
    for row in rows:
        r = score_product(row["title"], row["description"], row.get("keyword") or args.keyword, args)
        r["id"] = row.get("id") or f"line {row['line']}"
        results.append(r)
    seen: dict[str, str] = {}
    for r in results:
        h = r.pop("_hash")
        if h and h in seen:
            r["duplicate_of"] = seen[h]
            r["score"] = max(0, r["score"] - 10)
            r["fixes"].insert(
                0, f"Same description as {seen[h]}; write unique copy (manufacturer text is duplicated)"
            )
        elif h:
            seen[h] = r["id"]
    results.sort(key=lambda r: r["score"])
    avg = round(sum(r["score"] for r in results) / len(results), 1)
    below = [r for r in results if r["score"] < args.min_score]
    if args.json:
        print(
            json.dumps(
                {"products": len(results), "average": avg, "below_min": len(below), "results": results},
                indent=2,
            )
        )
    else:
        print(f"{len(results)} product(s), average score {avg}, {len(below)} below {args.min_score}")
        for r in results:
            flesch_txt = "n/a" if r["flesch"] is None else r["flesch"]
            print(
                f"\n{r['score']:>3} {r['grade']}  {r['id']}  {r['title'][:60]}\n"
                f"     words {r['words']}, title {r['title_chars']} chars, bullets {r['bullets']}, "
                f"flesch {flesch_txt}, specs {r['specs_found']}"
            )
            for fix in r["fixes"][:6]:
                print(f"     - {fix}")
    return 1 if below else 0


if __name__ == "__main__":
    sys.exit(main())
