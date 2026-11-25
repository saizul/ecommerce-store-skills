# Checkout checklist

Each item has an id (used in `answers.json`), a priority and how to check it. P1 items block or
lose orders directly; P2 items add friction; P3 items are polish.

Priorities reflect widely reported checkout usability research (for example Baymard
Institute's abandonment surveys, where extra costs, forced accounts and long forms are
consistently top reasons). Treat them as defaults, not laws: the store's own data wins.

## Cart

| Id | P | Check | How to verify |
| --- | --- | --- | --- |
| `cart-shipping-cost` | P1 | Shipping cost or a reliable estimate is shown in the cart | Add a product, open the cart on a phone; is the delivery charge visible before checkout? |
| `cart-total-clear` | P1 | Full total including tax, COD and other fees | Compare the cart total with the final total of a test order |
| `cart-coupon-collapsed` | P2 | Coupon field collapsed behind a link | Scan reports `cart-coupon-collapsed`; check whether the field is open by default |
| `cart-mobile-cta` | P2 | Checkout button visible without scrolling on mobile | 375 px wide viewport, cart with 2 items |
| `cart-edit` | P3 | Quantity change and remove are easy | Try it on a phone |

## Checkout form

| Id | P | Check | How to verify |
| --- | --- | --- | --- |
| `guest-checkout` | P1 | No forced account creation | Scan: password field without a create-account checkbox; try checking out logged out |
| `field-count` | P1 | 12 or fewer fields by default | Scan counts visible text inputs, selects and textareas |
| `address-line2-collapsed` | P2 | Address line 2 / company hidden or removed | Scan lists optional address fields |
| `autofill` | P2 | Correct `autocomplete` tokens | Scan lists fields without them; try browser autofill |
| `input-types` | P2 | `type=email` and `type=tel` | Scan; phone fields with `type=number` drop leading zeros and show spinners |
| `labels` | P2 | Visible labels, not placeholder-only | Scan lists unlabeled fields |
| `inline-validation` | P2 | Inline errors, data kept | Submit with an invalid phone and an empty address |
| `phone-format` | P2 | Local phone formats accepted | Enter `01712-345678`, `+880 1712 345678`, `8801712345678`; all should pass and be normalised |
| `delivery-date` | P2 | Delivery estimate before payment | Read the checkout as a shopper |
| `captcha` | P2 | No CAPTCHA challenge for normal shoppers | Scan detects reCAPTCHA, hCaptcha, Turnstile |
| `progress` | P3 | Single page or clear steps | Read the checkout |

## Payment and trust

| Id | P | Check | How to verify |
| --- | --- | --- | --- |
| `payment-methods` | P1 | Locally preferred methods offered | Scan lists methods mentioned; compare with what customers ask for (COD, bKash, Nagad, cards, PayPal) |
| `cod-fee-clear` | P1 | COD fees / advance delivery charge explained before the last step | Where is the rule first shown? It should be in the cart and next to the COD option |
| `express-pay` | P2 | Express wallets where available | Apple Pay / Google Pay / Shop Pay / PayPal buttons on cart and checkout (`na` if not available in the market) |
| `return-policy-link` | P2 | Policy and contact links on checkout | Scan checks refund/return and tel/WhatsApp/contact links |
| `payment-error-recovery` | P2 | Failed payment keeps the order and offers alternatives | Use the gateway's test/sandbox mode with a declined test card |
| `trust-near-payment` | P3 | Calm trust cues near payment | Read the page |

## Performance and mobile

| Id | P | Check | How to verify |
| --- | --- | --- | --- |
| `checkout-speed` | P2 | LCP under 2.5 s on mobile | PageSpeed Insights on the checkout URL (with a session cookie it may redirect; test the cart then) |
| `third-party-scripts` | P2 | No chat, heatmap or session recording on checkout | Scan lists known vendors and the third-party host count |
| `no-popups` | P2 | No newsletter / spin-wheel / exit-intent pop-ups | Scan detects common pop-up tools; check visually |
| `tap-targets` | P3 | Inputs 44 px+ tall, 16 px+ font | DevTools device mode |
| `viewport` | P1 | Responsive viewport meta tag | Scan |

## Post-purchase

| Id | P | Check | How to verify |
| --- | --- | --- | --- |
| `confirmation` | P3 | Confirmation page, email and SMS with order number | Place a test order |
| `abandoned-cart` | P2 | Recovery messages with consent | Check the store's email/SMS tool for an abandoned checkout flow |

## Reading the funnel

| Step rate | Typical range | If lower, look at |
| --- | --- | --- |
| Add to cart / product views | 4-10% | product page (price, photos, delivery info) |
| Reached checkout / carts | 40-60% | cart: costs, coupon field, CTA |
| Orders / reached checkout | 45-70% | the form, payment methods, fees, errors |

Ranges vary a lot by niche, device and traffic source. Compare the store with itself over time
and mobile with desktop rather than with industry averages.
