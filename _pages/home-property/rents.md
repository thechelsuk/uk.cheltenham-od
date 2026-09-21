---
layout: rents
title: "Cheltenham Average Rent & Private Rental Prices"
seo: "Average rent in Cheltenham by month since 2015, by bedrooms and property type, compared with the South West and England, from ONS rent data."
permalink: /cheltenham-rent-prices
description: "What tenants in Cheltenham pay in rent: the average monthly private rent, how it has changed since 2015, and how it splits by bedrooms and property type."
type: "property"
schema: rents
---

{% assign rents = site.data.rents %}
{% assign latest = rents.latest %}
{% assign england_gap = latest.price | minus: latest.england.price %}
{% assign south_west_gap = latest.price | minus: latest.south_west.price %}

## Average Rent in Cheltenham

The average private rent in Cheltenham was **{{ latest.price_display }} a month in {{ latest.month_name }} {{ latest.year }}**, {% if latest.annual_change >= 0 %}up{% else %}down{% endif %} {{ latest.annual_change | abs }}% on a year earlier. That is £{{ england_gap | abs }} a month {% if england_gap < 0 %}below{% else %}above{% endif %} the England average of {{ latest.england.price_display }}, and £{{ south_west_gap | abs }} {% if south_west_gap < 0 %}below{% else %}above{% endif %} the South West average of {{ latest.south_west.price_display }}.

The figures come from the Office for National Statistics' Price Index of Private Rents, which measures the rents tenants are actually paying across all private tenancies, both new lets and existing ones, rather than the asking rents on listing sites. Because it includes long-running tenancies where the rent changes once a year at most, it moves more slowly than the rents advertised for new lets today.

Below you can see how rents have changed month by month since 2015, how they differ by the number of bedrooms and by property type, and how Cheltenham compares with the rest of the South West and England. Moving here to study? Our [student guide](/student-guide-to-cheltenham) covers finding somewhere to live, and our [house prices](/cheltenham-house-prices) page shows what homes are selling for.
