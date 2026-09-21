---
layout: affordability
title: "Cheltenham Home Affordability: How Many Homes Can a Typical Earner Afford?"
seo: "How many homes sold in Cheltenham each year could a typical full-time earner afford? The share of sales within 4.5 times median pay since 2008, for all homes and by property type, from Land Registry sales and ONS earnings."
permalink: /cheltenham-house-prices/affordability
description: "The share of homes sold in Cheltenham each year that a typical full-time earner could afford, since 2008, for all homes and for flats, terraced, semi-detached and detached homes."
type: "property"
schema: affordability
---

{% assign years = site.data["cheltenham-affordability"].years %}
{% assign latest = years | last %}
{% assign first = years | first %}
{% assign lowest = years | sort: "share" | first %}
{% assign highest = years | sort: "share" | last %}

## How Many Homes Can a Typical Earner Afford?

House prices and pay tell you what has happened on average. This page asks a more practical question: of the homes that actually sold in Cheltenham, how many could someone on a typical wage have afforded?

In {{ latest.year }}, **{{ latest.within }} of the {{ latest.sales_display }} homes sold in Cheltenham ({{ latest.share_display }}) went for {{ latest.cap_display }} or less**, which is 4.5 times the {{ latest.pay_display }} median full-time pay of people who live in the borough. That is about 1 in {{ latest.one_in }}. The share was lowest in {{ lowest.year }}, when it fell to {{ lowest.share_display }} (about 1 in {{ lowest.one_in }}), and highest in {{ highest.year }} at {{ highest.share_display }}. In {{ first.year }} it was {{ first.share_display }}.

The chart and table show how the picture differs by type of home. Flats are the only kind where a typical earner has a realistic choice, while detached homes are almost never within reach.

A sale counts as affordable when its price is no more than 4.5 times median gross annual full-time pay, roughly the most a lender will usually offer one borrower. It assumes a single income and doesn't allow for a deposit, other debts or the current mortgage rate, so treat it as a guide to how much of the market is in reach rather than a mortgage calculation. Pay is the median for residents of Cheltenham from the [earnings history](/cheltenham-earnings-history), and sales come from the [house prices](/cheltenham-house-prices) data. For renters, see [rent prices](/cheltenham-rent-prices).
