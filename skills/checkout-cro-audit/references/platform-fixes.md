# Platform how-tos for common checkout fixes

Always change one thing at a time on a staging site or duplicate theme, and note the date so
the effect can be measured.

## WooCommerce

| Fix | Where |
| --- | --- |
| Guest checkout | WooCommerce > Settings > Accounts & Privacy > "Allow customers to place orders without an account" |
| Fewer fields (classic checkout) | Appearance > Customize > WooCommerce > Checkout sets company, address line 2 and phone to hidden/optional/required; for other fields use the `woocommerce_checkout_fields` filter in a small plugin or a checkout field editor plugin |
| Fewer fields (Checkout block) | Edit the Checkout page in the block editor; toggle company, address line 2 and phone in the block settings |
| Shipping cost in cart | WooCommerce > Settings > Shipping > Shipping options: enable the shipping calculator on the cart page; set zones so a default rate shows |
| COD fee / advance payment notice | Add a notice block on cart and checkout; many BD stores use "delivery charge in advance via bKash" - state the amount |
| Phone normalisation | Validate with a filter that strips spaces/dashes and accepts `+880` / `880` / `0` prefixes instead of a strict pattern |
| Remove chat/pop-ups on checkout | Each plugin's display rules; or dequeue scripts with `is_checkout()` / `is_cart()` conditions |
| CAPTCHA | Prefer the gateway's own fraud tools, rate limiting, or an invisible/score-based challenge |

## Shopify

| Fix | Where |
| --- | --- |
| Guest checkout | Settings > Customer accounts: do not require accounts |
| Fewer fields | Settings > Checkout > Customer information: hide company, make address line 2 optional/hidden, phone optional or required (pick one) |
| Shipping in cart | Show a shipping estimate in the cart via theme settings or an estimate app; set free-shipping thresholds visibly |
| Express pay | Settings > Payments: Shop Pay, Apple Pay, Google Pay, PayPal; theme cart setting for dynamic checkout buttons |
| COD | Settings > Payments > Manual payment methods > Cash on Delivery; add instructions text |
| Pop-ups and chat | App settings: exclude cart; apps cannot inject into checkout on non-Plus plans anyway |
| Checkout customisation | Checkout editor (Settings > Checkout > Customize) and checkout UI extensions |

## Bangladesh specifics

- COD is often the majority of orders. Show the COD rule (inside Dhaka / outside Dhaka charges,
  any advance) before checkout and repeat it next to the payment option.
- Accept phone numbers as typed (`01712-345678`, `+8801712345678`, Bangla digits) and normalise
  them; reject only numbers that are not 11-digit `01[3-9]` mobiles after normalisation.
- Area/thana and district fields matter more than postcode for couriers; consider making
  postcode optional and district a dropdown.
- bKash/Nagad payments through a gateway (or merchant checkout) reduce fake COD orders; offer a
  small discount for prepaid orders rather than a fee for COD if margins allow.
