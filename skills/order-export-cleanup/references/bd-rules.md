# Bangladesh phone, district and postcode rules

## Mobile numbers

A Bangladeshi mobile number is `01` + operator digit `3-9` + 8 digits (11 digits locally).
E.164 form: `+880` + the 10 digits after the leading `0`.

| Input | Normalised | Note |
| --- | --- | --- |
| `01712-345678`, `01712 345678` | `+8801712345678` | spaces and dashes removed |
| `+880 1712 345678`, `8801712345678`, `008801712345678` | `+8801712345678` | country code forms |
| `+88001712345678` | `+8801712345678` | extra trunk zero after 880 (common typo) |
| `1712345678` | `+8801712345678` | leading zero lost (Excel or number column) |
| `০১৭১২৩৪৫৬৭৮` | `+8801712345678` | Bangla digits |
| `1.71234E+09` | invalid (`phone_excel_corrupted`) | digits are gone; get the number from the admin |
| `01911-223344, 01611-223344` | first number, `multiple_phones` | second number stays in the original column |
| `01212345678`, `12345` | invalid (`phone_invalid`) | not a mobile prefix / wrong length |

Operator prefixes (number portability means this is the original operator, not necessarily
the current one):

| Prefix | Operator |
| --- | --- |
| 013, 017 | Grameenphone |
| 014, 019 | Banglalink |
| 015 | Teletalk |
| 016 | Robi (formerly Airtel) |
| 018 | Robi |

Landline numbers (e.g. `02-` Dhaka) are reported as invalid because couriers and SMS need a
mobile number. Foreign numbers written with `+` are kept and tagged `phone_foreign`.

## Districts

Bangladesh has 64 districts. The script uses the current official English spellings and maps
old or common spellings:

| Seen in orders | District |
| --- | --- |
| Chittagong, CTG, Chattagram | Chattogram |
| Comilla, Kumilla | Cumilla |
| Barisal | Barishal |
| Jessore | Jashore |
| Bogra | Bogura |
| Coxs Bazar, Coxsbazar | Cox's Bazar |
| Chapai Nawabganj, Nawabganj | Chapainawabganj |
| Maulvibazar, Moulvi Bazar | Moulvibazar |
| Jhalakati, Jhalokati | Jhalokathi |
| Netrakona | Netrokona |
| Laxmipur | Lakshmipur |
| ঢাকা, চট্টগ্রাম, সিলেট ... | Dhaka, Chattogram, Sylhet ... |

The district is searched in the state, city, address line 2 and address line 1 columns, in
that order. Many shoppers type a thana or area (Mirpur, Dhanmondi, Agrabad) in the city field;
those are not districts, so the row gets `district_unknown` unless the district also appears
somewhere in the address. Area-to-district mapping is a good contribution (see CONTRIBUTING).

WooCommerce stores Bangladeshi "states" as codes like `BD-13`; if the export shows codes, map
the state column to the district names with a lookup before running, or rely on the city.

## Postcodes

Four digits (`1205` Dhanmondi, `4100` Chattogram). Anything else is `postcode_invalid`.
Postcodes are optional for most couriers; district and area matter more.

## Duplicate rules

- Exact duplicate rows (every column equal) are dropped: usually a double export or merge.
- Same order id twice (not merged): `duplicate_order_id`, the first row is kept as is.
- Same normalised phone + same total within `--dup-hours`: `possible_duplicate`, both rows kept.
  Customers do sometimes place two identical orders on purpose (gifts); always confirm.
