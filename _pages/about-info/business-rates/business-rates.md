---
layout: about-info/business-rates
title: "Cheltenham Business Rates: Occupied and Empty Properties"
seo_title: "Cheltenham Business Rates & Empty Properties"
seo: "Cheltenham's business properties from the council's business rates lists: how many are empty, rateable values by band and type, and a map by postcode."
permalink: /cheltenham-business-rates
description: "How many of Cheltenham's business properties are occupied or empty, their rateable values by band and type, and the reliefs they get, from Cheltenham Borough Council's business rates lists."
type: "about"
schema: business-rates
---

{% include sponsor.html %}

{% assign rates = site.data["business-rates"] %}
{% assign s = rates.summary %}

## Cheltenham's Business Properties

Cheltenham Borough Council's {{ rates.release.name }} business rates lists hold **{{ s.properties_display }} business properties**, from shops and offices to warehouses, pubs and advertising sites. **{{ s.empty_display }} of them were empty**, {{ s.empty_pct_display }} of the total, and {{ s.empty_every_release_display }} of those had been empty in every list since {{ rates.releases.first.name }}.

Offices and shops make up more than half of the town's business properties, and many are small: {{ rates.bands.first.total_display }} have a rateable value of £12,000 or less, the limit for full small business rate relief. Every empty property is listed, with its exemption and start date, on [Cheltenham's empty business properties](/cheltenham-business-rates/empty-properties). For jobs and business counts across the town, see [the Cheltenham economy](/cheltenham-economy).
