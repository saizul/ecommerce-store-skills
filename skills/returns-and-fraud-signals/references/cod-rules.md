# COD risk rules (cod_risk.py)

| Rule | Points | Fires when |
| --- | --- | --- |
| `invalid_phone` | +40 | phone missing or not a valid mobile (BD: `01[3-9]` + 8 digits after normalising) |
| `prior_failed_delivery` | +25 each, max +50 | history has returned / refused / RTO / undelivered / failed for this phone |
| `low_success_rate` | +20 | 2+ finished deliveries in history and fewer than half delivered |
| `first_order_high_value` | +15 | no history for this phone, COD, total >= `--high-value` |
| `far_above_median` | +10 | total >= 3x the batch median and >= `--high-value` |
| `repeat_in_batch` | +15 | 2+ orders from the same phone within 24 hours in this file |
| `fake_name` | +20 | name like test, asdf, xxx, demo, n/a, repeated characters, 3+ digits, or 1-2 characters |
| `short_address` | +15 | address line shorter than `--min-address` (15) characters |
| `disposable_email` | +10 | mailinator, yopmail, 10minutemail and similar |
| `bulk_quantity` | +10 | quantity column >= `--bulk-qty` (5) |
| `trusted_customer` | -20 | 3+ delivered orders and 90%+ success |

Levels: **high** >= 60, **medium** 30-59, **low** < 30.

History statuses: text containing deliver/complete/paid/success counts as delivered; text
containing return/refus/RTO/undeliver/fail/reject/"not received"/"cancelled by customer"
counts as failed; anything else (pending, cancelled before shipping) is ignored.

## Tuning

- Set `--high-value` to roughly 2-3x the store's average order value.
- If many confirmed-good orders score medium, raise thresholds or lower the points of the rule
  that fires most often (edit `RULES` in the script; keep a note in the changelog of the store's
  copy).
- New stores without history rely on the order-level rules only; start collecting courier
  status exports from day one.
- `repeat_in_batch` often catches double submissions, not fraud: check
  `order-export-cleanup`'s `possible_duplicate` first.

## Actions that work for COD stores

| Level | Action |
| --- | --- |
| high | Call. Ask for the delivery charge (or a part payment) in advance by bKash/Nagad. If unreachable after 2 calls, hold. |
| medium | SMS or WhatsApp: order summary + "reply YES to confirm". Ship after confirmation. |
| low | Ship. Optionally send the courier tracking link by SMS. |

Other levers: a small discount for prepaid orders, showing the delivery charge clearly before
checkout, requiring advance delivery charge above a value threshold, and limiting COD for
customers with 2+ refusals. Explain the rule on the checkout page; surprises cause refusals.

## Limits

- Rules see only what is in the files. A careful fraudster with a real number and a good
  address scores low.
- Shared phones (family, office) mix histories.
- Operator portability means the phone prefix says nothing about risk; it is not used.
