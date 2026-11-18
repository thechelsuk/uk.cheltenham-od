---
layout: about-info/business-rates-empty
title: "Cheltenham Empty Business Properties"
seo_title: "Empty Business Properties in Cheltenham"
seo: "Every empty shop, office and business property in Cheltenham's business rates lists, with its rateable value, exemption and how often it's been empty."
permalink: /cheltenham-business-rates/empty-properties
description: "Every empty business property in Cheltenham Borough Council's business rates lists, with its rateable value, any exemption from empty rates and how many of the council's lists have shown it empty."
type: "about"
schema: business-rates-empty
filters:
  - table: 2
    column: "Type"
  - table: 2
    column: "Lists Empty"
---

{% include sponsor.html %}

{% assign rates = site.data["business-rates"] %}
{% assign s = rates.summary %}

## Empty Business Properties in Cheltenham

**{{ s.empty_display }} business properties in Cheltenham were empty** in the council's {{ rates.release.name }} business rates list, with a combined rateable value of {{ s.empty_rv_display }}. {{ s.empty_every_release_display }} of them were empty in all {{ s.release_count }} of the council's lists since {{ rates.releases.first.name }}, so they have stood empty for most of 2026 or longer.

Many empty properties pay no rates: listed buildings are exempt for as long as they stay empty, and every other empty property pays nothing for its first three months, or six for some industrial ones. The table shows the exemption for each one. For the occupied properties and the town as a whole, see [Cheltenham business rates](/cheltenham-business-rates).
