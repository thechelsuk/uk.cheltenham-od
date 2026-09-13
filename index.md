---
layout: home
title: "Local Open Data for Cheltenham & Gloucestershire"
seo_title: "Cheltenham Fuel Prices, House Prices, Crime & News"
seo: "Free Cheltenham open data for Gloucestershire: compare local fuel prices, check crime stats, house prices, flood warnings, food banks, GPs, planning and news."
permalink: /
type: "cod"
description: "The open data hub for Cheltenham and Gloucestershire. Fuel prices, crime figures, flood alerts, food banks, GPs, planning, local news and weather — all free, in one place."
---

## Latest from Cheltenham Open Data

{% for post in site.posts limit: 5 %}
- [{{ post.title }}]({{ post.url }}) &mdash; {{ post.date | date: "%-d %B %Y" }}
{% endfor %}

- [See all announcements &rarr;](/news)
