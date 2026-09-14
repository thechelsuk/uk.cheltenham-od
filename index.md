---
layout: home
title: "Local Open Data for Cheltenham & Gloucestershire"
seo_title: "Cheltenham Fuel Prices, House Prices, Crime & News"
seo: "Free Cheltenham open data for Gloucestershire: compare local fuel prices, check crime stats, house prices, flood warnings, food banks, GPs, planning and news."
permalink: /
type: "cod"
description: "The open data hub for Cheltenham and Gloucestershire. Fuel prices, crime figures, flood alerts, food banks, GPs, planning, local news and weather — all free, in one place."
sponsor:
  url: "/sponsor"
  logo: "/assets/images/sponsors/logo.png"
  name: "Your Local Business Here  - 01242 000000"
  tagline: "Become a principal sponsor of Cheltenham Open Data &rarr;"
  type: "Prinicpal Site Sponsor"
---

## Latest from Cheltenham Open Data

{% assign latest = site.posts | concat: site.events | sort: "date" | reverse %}
{% for post in latest limit: 5 %}

- [{{ post.title }}]({{ post.url }}) - {{ post.date | date: "%-d %B %Y" }}{% if post.collection == "events" %} (Events roundup){% endif %}

{% endfor %}

- [See all announcements &rarr;](/news)
