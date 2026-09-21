---
layout: cheltenham-earnings
title: "Cheltenham Median Earnings History"
seo: "Cheltenham median full-time earnings since 2008: annual, weekly and hourly pay for residents and workers, compared with the South West and England."
permalink: /cheltenham-earnings-history
description: "Median full-time earnings in Cheltenham year by year since 2008, for people who live and people who work in the town, compared with Gloucestershire, the South West and England."
type: "about"
schema: cheltenham-earnings
---

{% include sponsor.html %}

{% assign earnings = site.data["cheltenham-earnings"] %}
{% assign annual = earnings.latest.rows | first %}

## Cheltenham Earnings History

The typical (median) full-time employee who lives in Cheltenham earned **{{ earnings.latest.resident_display }} a year in {{ earnings.latest.year }}**, before tax. That is {{ annual.vs_england | abs }}% {% if annual.vs_england >= 0 %}above{% else %}below{% endif %} the England median of {{ annual.england_display }} and {{ annual.vs_south_west | abs }}% {% if annual.vs_south_west >= 0 %}above{% else %}below{% endif %} the South West median of {{ annual.south_west_display }}. Full-time employees who work in Cheltenham, wherever they live, earned a median of **{{ earnings.latest.workplace_display }}**.

Since {{ earnings.growth.first_year }}, median pay for Cheltenham residents has risen by {{ earnings.growth.cheltenham }}%, compared with {{ earnings.growth.england }}% across England. The figures are cash amounts, not adjusted for inflation, so they show what people were paid rather than what it would buy. This page sits alongside [employment rates](/cheltenham-employment-history) and the [population and growth statistics](/about-cheltenham).
