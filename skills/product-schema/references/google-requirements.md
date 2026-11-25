# Product structured data: what Google needs

Google has two product rich result types. Check the current documentation
(developers.google.com/search/docs/appearance/structured-data/product) when in doubt;
requirements change.

| Type | Required | Notes |
| --- | --- | --- |
| Product snippet (stars, price in organic results) | `name`, plus one of `review`, `aggregateRating`, `offers` | For review/editorial pages and product pages |
| Merchant listing (shopping surfaces) | `name`, `image`, `offers` with `price` and `priceCurrency` | Only pages where the user can buy the product |

## Field rules the validator enforces

- `price`: a number as text or number, `.` as decimal separator, no currency symbols, no
  thousands separators: `"1250.00"`, not `"৳1,250"` or `"$1,250.00"`.
- `priceCurrency`: ISO 4217 three-letter code (`USD`, `EUR`, `GBP`, `BDT`, `INR`).
- `availability`: a schema.org ItemAvailability URL, e.g. `https://schema.org/InStock`,
  `OutOfStock`, `PreOrder`, `BackOrder`, `LimitedAvailability`, `Discontinued`, `SoldOut`,
  `InStoreOnly`, `OnlineOnly`, `PreSale`.
- `itemCondition`: `https://schema.org/NewCondition`, `UsedCondition`,
  `RefurbishedCondition`, `DamagedCondition`.
- `priceValidUntil`: ISO date; a past date makes Google ignore the price.
- `aggregateRating.ratingValue` inside `worstRating`..`bestRating` (defaults 1..5), plus
  `reviewCount` or `ratingCount` greater than 0.
- `review`: needs `author` and `reviewRating.ratingValue`.
- `gtin`, `gtin8`, `gtin12`, `gtin13`, `gtin14`: valid GS1 check digit.

## Template: simple product

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Acme Stoneware Coffee Mug 350 ml",
  "image": ["https://shop.example.com/img/mug-1x1.jpg", "https://shop.example.com/img/mug-4x3.jpg"],
  "description": "Hand-glazed stoneware mug, 350 ml, dishwasher safe.",
  "sku": "MUG-002",
  "gtin12": "036000291452",
  "brand": {"@type": "Brand", "name": "Acme"},
  "offers": {
    "@type": "Offer",
    "url": "https://shop.example.com/products/stoneware-mug",
    "price": "1250.00",
    "priceCurrency": "BDT",
    "availability": "https://schema.org/InStock",
    "itemCondition": "https://schema.org/NewCondition",
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": {"@type": "MonetaryAmount", "value": "60", "currency": "BDT"},
      "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "BD"},
      "deliveryTime": {
        "@type": "ShippingDeliveryTime",
        "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "DAY"},
        "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 3, "unitCode": "DAY"}
      }
    },
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "applicableCountry": "BD",
      "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
      "merchantReturnDays": 7,
      "returnMethod": "https://schema.org/ReturnByMail",
      "returnFees": "https://schema.org/FreeReturn"
    }
  },
  "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.6", "reviewCount": 38}
}
```

## Variable products

Two options:

1. One `Product` with an `AggregateOffer` (`lowPrice`, `highPrice`, `priceCurrency`,
   `offerCount`). Simple, works for product snippets; merchant listings prefer per-variant data.
2. `ProductGroup` with `hasVariant` (one `Product` per variant, each with its own `offers`,
   `sku`, `gtin`, `color`/`size`) and `variesBy`. Best for apparel and Merchant Center
   matching. The validator checks each nested variant `Product` it finds.

## Common mistakes

- Price printed with the store's display format (`"1.250,00"`, `"৳ 1,250"`).
- Sale price shown on the page but schema still carries the regular price (cached template).
- Ratings markup on products with zero reviews (`reviewCount: 0`): remove `aggregateRating`.
- Hard-coded `priceValidUntil` from a theme demo that is now in the past.
- Out-of-stock products still marked `InStock` because the theme reads the parent product.
- Microdata (`itemprop`) from the theme plus JSON-LD from a plugin, describing the same product
  differently. The validator only reads JSON-LD; search for `itemtype="https://schema.org/Product"`
  in the HTML to find microdata.
