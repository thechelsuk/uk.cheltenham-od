---
layout: fuel
title: Cheapest Fuel Prices in Cheltenham & Gloucestershire.
seo: "Latest and Cheapest Fuel Prices in Cheltenham. Cheapest fuel in Glos, Cheapest fuel in Gloucestershire, petrol, diesel prices, what's the diesel price in Cheltenham?"
permalink: /cheltenham-fuel-prices
schema: fuel-prices
type: fuel
description: Compare today's cheapest petrol and diesel prices across 100+ forecourts in Cheltenham, Gloucester and wider Gloucestershire — updated daily from official GOV.UK data.
---

{% assign fuel = site.data["fuel-prices"] %}

Data sourced from the [GOV.UK fuel price scheme](https://www.gov.uk/check-fuel-prices) under the [Open Government Licence v3](http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), and refreshed daily. They can change at any time, so treat them as a guide and check the forecourt's own display before filling up.

## Fuel Price FAQs

### How Often Are Prices Updated?

- Daily. Figures come straight from the GOV.UK fuel price scheme, which forecourts are required to keep current.

### Where Does This Data Come From?

- The UK government's official fuel price disclosure scheme. We show every reporting forecourt within {{ fuel.radius_miles }} miles of Cheltenham town centre, from supermarket pumps to independent garages. That's {{ fuel.stations | size}} forecourts.

### Why isn’t My Local Station Listed?

- Only stations that have reported a price in the last {{ fuel.lookback_days }} days are shown. If yours is missing it probably hasn't filed a change recently — check directly before assuming it's the cheapest. We've also only included forecourts located within 20 miles of the centre of Cheltenham.

### How Do I Read the Table?

- Click any column header to sort — by price, distance, or when a price was last reported. The lowest price in each fuel column is highlighted, and forecourts with no update in {{ fuel.stale_days }} days are greyed out.

### How Is "Typical" Calculated?

- It's the median price for that fuel type across all listed local forecourts — the middle value when every price is lined up in order — not the average. Median is less skewed by the odd unusually cheap or expensive forecourt, so it's a fairer read of what you'd typically pay locally.

### How Are the "Savings" Worked Out?

- The percentage compares the cheapest local price against the local typical (median) price. The £ figure scales that per-litre saving up to a 55-litre tank — about the size of an average UK car's — as a simple, comparable reference point. Most people don't fill from empty, so treat it as an upper bound: if you're topping up 30 litres instead of 55, the saving is roughly 30/55 of what's shown.
