---
layout: about-info/council-spending-suppliers
title: "Cheltenham Council's Biggest Suppliers"
seo_title: "Cheltenham Council's Top 100 Suppliers"
seo: "The 100 suppliers Cheltenham Borough Council paid most over the last five financial years, with the amount paid to each in every year."
permalink: /cheltenham-council-spending/suppliers
description: "The 100 suppliers Cheltenham Borough Council paid most over the last five financial years, year by year."
type: "about"
schema: council-spending
---

{% assign idx = site.data["council-spending"].index %}
{% assign top = idx.suppliers | first %}

## Who Cheltenham Borough Council Pays Most

Over the five financial years from {{ idx.page_years.last }}, the council paid **{{ top.name }} {{ top.total_display }}**, more than any other supplier. The table ranks the 100 biggest suppliers by what they were paid in that time, with what each was paid in every year.

The figures count payments of £500 or more and card purchases, as published in the council's monthly [spending files](/cheltenham-council-spending).
