---
layout: about-info/council-spending-year
title: "Cheltenham Council Spending 2026-27"
seo_title: "Cheltenham Council Spending 2026-27 by Month & Service"
seo: "Cheltenham Borough Council's payments to suppliers in 2026-27: month by month, every service area and the top 25 suppliers, from April 2026 to March 2027."
permalink: /cheltenham-council-spending/2026-27
description: "Cheltenham Borough Council's payments to suppliers in the 2026-27 financial year, by month, service area and supplier."
type: "about"
schema: council-spending
spending_year: "2026-27"
---

{% assign idx = site.data["council-spending"].index %}
{% assign y = idx.years | where: "year", page.spending_year | first %}
{% assign top = y.top_suppliers | first %}
{% assign top_service = y.services | first %}

## Cheltenham Council Spending in {{ y.year }}

{% if y.complete %}In the {{ y.year }} financial year, from April 2026 to March 2027, Cheltenham Borough Council paid its suppliers **{{ y.payments_display }}** in {{ y.count_display }} payments.{% else %}So far in the {{ y.year }} financial year, from April 2026 to {{ y.last_month | append: "-01" | date: "%B %Y" }}, Cheltenham Borough Council has paid its suppliers **{{ y.payments_display }}** in {{ y.count_display }} payments.{% endif %} The biggest supplier was {{ top.name }}, at {{ top.payments_display }}, and the service area with the most spending was {{ top_service.name }}, at {{ top_service.payments_display }}.

The tables break the year down by month, by every service area the council names in its files, and by its 25 biggest suppliers. Other years and the full list of suppliers are on the [council spending](/cheltenham-council-spending) page.
