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

### How Is the National Average Worked Out?

- It's the mean of the latest reported price at every reporting forecourt across the UK for that fuel type, using the same GOV.UK fuel price scheme data. It isn't weighted by sales volume, so it reflects the spread of forecourt prices rather than what drivers typically pay in total.
