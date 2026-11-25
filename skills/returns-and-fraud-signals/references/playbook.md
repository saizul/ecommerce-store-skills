# Returns playbook: from finding to fix

## Reading return_rate.py output

- `unit_return_rate`: returned units / sold units in the files. Note the period; returns lag
  sales by days to weeks, so recent weeks look better than they are.
- `wilson_lower`: the lower end of the 95% confidence interval of a SKU's return rate. A SKU is
  flagged only when this is above the store average, so 1 return out of 2 sales does not make
  a product "bad".
- Reason categories come from keyword matching on free text. `other` and `unspecified` mean
  the returns form needs a required reason dropdown.

## Fixes by reason

| Reason | Fix | Check |
| --- | --- | --- |
| size/fit | measured size chart in cm per product (not a generic chart), "runs small/large" notes, model height and size, fit photos | size/fit share for that SKU next month |
| not as described | more photos (scale, detail, on-body), true-colour photos in daylight, specs with units, video | reason share |
| damaged | better packaging (double box, bubble wrap, "fragile" tape), courier claim process, photo before dispatch | damage rate per courier |
| wrong item | pick-pack checks, SKU labels on shelves, barcode scan at packing | wrong-item count per week |
| quality | supplier review, honest material description, stop selling repeat offenders | rating and return rate |
| late delivery | realistic delivery estimates, courier choice per zone, dispatch same/next day | late share by courier |
| changed mind | clear policy, delivery charge non-refundable for change-of-mind (state it before checkout) | share over time |
| refused/unreachable | COD confirmation (cod_risk.py), advance delivery charge, tracking SMS, deliver within promised time | RTO rate |

## Couriers and areas

- Compare couriers on the same areas and order types; a courier that serves remote districts
  will look worse.
- A district with a high refusal rate may need a different courier or a prepayment rule above a
  value, not a ban.

## Serial returners

- Check the history before acting: a loyal customer with many orders and some returns is
  different from a phone that refused 3 of 4 parcels.
- Reasonable steps: prepaid-only for that phone, advance delivery charge, or a call before
  shipping. Record the decision.

## Metrics to track monthly

- RTO (returned-to-origin) rate for COD orders
- Unit and order return rate, top 10 SKUs by returned units and by rate
- Return reasons share
- Cost of returns: delivery both ways + damaged stock + staff time
