# Product copy framework

## 1. Title

Formula: **Brand + product type + key attribute(s) + variant**

| Weak | Better |
| --- | --- |
| `WALLET` | `Acme Slim Leather Wallet for Men - RFID Blocking, Brown` |
| `Mug` | `Acme Stoneware Coffee Mug 350 ml - Matte Black` |
| `Best Saree Sale!!!` | `Dhakai Jamdani Saree - Handwoven Cotton Silk, Red and Gold` |

Rules:

- Put what people search for first; brand first only when the brand is what people search for.
- 25-90 characters on the product page; Google Shopping titles may be up to 150 characters and
  benefit from extra attributes (material, size, pack count).
- No promotions ("sale", "free shipping"), no ALL CAPS, no emoji.
- Variant products: same base title, variant attributes at the end.

## 2. Opening paragraph (2-3 sentences)

Who it is for + the main outcome + one proof. Use the focus keyword once, naturally.

> This organic cotton t-shirt is the one you reach for every morning: soft from the first wear
> and still in shape after 50 washes.

## 3. Bullets (3-7)

Benefit first, then the spec that proves it. One line each. Start with the most important.

- Stays cool on hot days - breathable 180 gsm organic cotton
- No twisting after washing - double-stitched side seams
- True to size - regular fit, model is 180 cm and wears M

## 4. Specs block

A short table or list with units: dimensions, weight, capacity, materials (with %), power,
compatibility, what is in the box, warranty. Use the units customers use in that market
(cm/kg in Bangladesh and most of the world; add inches where buyers expect them).

## 5. Fit, use and care

Sizing advice, who it is not for, assembly time, care instructions, storage, shelf life.

## 6. Objections

Delivery time and cost, returns/exchange window, warranty, authenticity (for branded goods),
payment options (COD). Keep it to 2-4 lines or link the policy.

## 7. FAQ (optional)

Two to four questions taken from real customer messages or reviews. Never invent reviews or
testimonials.

## Writing rules

- Specific beats superlative: "keeps tea hot for 6 hours" instead of "amazing quality".
- Short sentences (most under 20 words), short paragraphs (2-4 sentences), active voice.
- Write for the reader's language level; Flesch reading ease 60+ for general consumer goods.
- Keyword: in the title, the first 100 words, and 1-3 more times across the page. Use synonyms.
- Every product gets original copy. Supplier descriptions shared by many stores add nothing;
  rewrite them or at least add your own opening, bullets and fit notes.
- Do not claim certifications, medical effects, origin or test results unless the user provides
  proof.

## Bangla and bilingual stores

- Write Bangla copy natively instead of machine-translating English; keep product names, sizes
  and units consistent across languages.
- Use one script per field (don't mix Bangla and English words in one title unless customers
  search that way, e.g. brand names).
- The scorer skips Flesch readability for Bangla text and allows suffixes (`শাড়িটি`) when it
  matches a Bangla keyword.

## Score breakdown (score_content.py)

| Part | Points | Full marks when |
| --- | --- | --- |
| Length | 20 | `--min-words` (120) to `--max-words` (700) words |
| Title | 15 | 25-90 characters |
| Keyword | 20 | in title (8), in first 100 words (6), 0.5-3 occurrences per 100 words (6) |
| Readability | 20 | Flesch 60+, average sentence 22 words or fewer |
| Structure | 15 | 3-10 bullets (10), no paragraph over 80 words (5) |
| Specifics | 10 | 2+ numbers with units |
| Penalties | up to -15 | filler phrases, ALL CAPS, "!!"; -10 for duplicate descriptions |

Without a keyword the score is scaled from 80 points. Use it to compare products and track
progress; it does not replace reading the copy.
