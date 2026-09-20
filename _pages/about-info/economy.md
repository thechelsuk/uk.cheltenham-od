---
layout: cheltenham-economy
title: "Cheltenham Economy: Jobs, Businesses and Claimants"
seo: "Cheltenham's economy in numbers: jobs by industry, how many businesses there are and how many people claim unemployment benefits, compared with England, from the ONS."
permalink: /cheltenham-economy
description: "How many people work in Cheltenham and in which industries, how many businesses the town has, and how many residents are claiming unemployment-related benefits, compared with England."
type: "about"
schema: cheltenham-economy
---

{% include sponsor.html %}

{% assign economy = site.data["cheltenham-economy"] %}
{% assign biggest = economy.jobs.industries | first %}
{% assign tech = economy.jobs.industries | where: "code", "J" | first %}

## Cheltenham's Economy

Cheltenham had **{{ economy.jobs.total_display }} employee jobs in {{ economy.jobs.year }}** and **{{ economy.businesses.total_display }} VAT and PAYE registered businesses in {{ economy.businesses.year }}**. The biggest employer by industry is {{ biggest.name | downcase }}, with {{ biggest.share_display }} of jobs.{% if tech %} Information and communication, which includes the town's technology and cyber security firms, accounts for {{ tech.share_display }} of jobs against {{ tech.england_share_display }} across England, {{ tech.quotient_display }} times the national share.{% endif %}

In {{ economy.claimants.period_name }}, {{ economy.claimants.count_display }} Cheltenham residents were claiming unemployment-related benefits, {{ economy.claimants.rate_display }} of residents aged 16 to 64 against {{ economy.claimants.england_rate_display }} across England. This page sits alongside [employment rates](/cheltenham-employment-history) and [median earnings](/cheltenham-earnings-history) under [All About Cheltenham](/about-cheltenham).
