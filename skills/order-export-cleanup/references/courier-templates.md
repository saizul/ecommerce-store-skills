# Mapping a cleaned export to courier bulk uploads

Courier bulk-upload templates change; always download the current template from the courier's
merchant panel and map columns to it. Typical fields and where they come from in the cleaned
file:

| Courier field (typical) | Cleaned export column |
| --- | --- |
| Invoice / merchant order id | order number (`Order Number` / `Name`) |
| Recipient name | billing or shipping name |
| Recipient phone | `phone_e164` without `+88` if the template wants `01XXXXXXXXX` |
| Recipient address | address 1 + address 2 + city |
| District / city / zone | `district` (then pick the courier's zone/area by hand or with their lookup) |
| COD amount | `total_clean` when `is_cod=yes`, otherwise `0` |
| Note | order note / delivery instructions |
| Item weight / quantity | from line items (Shopify `Lineitem quantity`) |

Converting E.164 back to the local 11-digit form: `"0" + phone_e164[4:]` (for `+880` numbers).

## Checklist before uploading

1. Filter out rows whose `issues` contain `phone_invalid`, `phone_excel_corrupted`,
   `possible_duplicate` or `duplicate_order_id` until they are resolved.
2. Check COD amounts against the store (partial advance payments reduce the COD amount).
3. Upload a small batch first and check the courier's preview for zone mismatches.
4. Keep the cleaned file with the consignment ids the courier returns, so returns can be
   matched later in `returns-and-fraud-signals`.
