---
layout: about-info/council-spending
title: "Cheltenham Council Spending"
seo_title: "Cheltenham Council Spending: Every Payment over £500"
seo: "What Cheltenham Borough Council pays its suppliers: monthly totals since 2016, the biggest suppliers and service areas, and every payment over £500."
permalink: /cheltenham-council-spending
description: "Every payment of £500 or more that Cheltenham Borough Council makes to its suppliers, with monthly and yearly totals, the biggest suppliers and the service areas the money goes to."
type: "about"
schema: council-spending
filters:
  - table: 4
    column: "Service"
---

{% assign idx = site.data["council-spending"].index %}
{% assign top = idx.last_12.top_suppliers | first %}
{% assign top_service = idx.last_12.top_services | first %}

## Cheltenham Borough Council's Payments to Suppliers

Cheltenham Borough Council paid its suppliers **{{ idx.last_12.payments_display }}** in the 12 months to {{ idx.latest_month | append: "-01" | date: "%B %Y" }}, across {{ idx.last_12.count_display }} payments of £500 or more and card purchases. The biggest single supplier was {{ top.name }}, paid {{ top.payments_display }}, and the service area with the most spending was {{ top_service.name }}, at {{ top_service.payments_display }}.

The council publishes every payment month by month. This page adds them up by month and by financial year back to {{ idx.years.last.year }}, with a page for each of the last five years, the [top 100 suppliers](/cheltenham-council-spending/suppliers) and the council's [net spending by service](/cheltenham-council-spending/accounts). Pick a service area in the table at the bottom to see what the council paid for in the latest month. For land and buildings the council owns, see [council land and assets](/cheltenham-council-land-and-assets).
