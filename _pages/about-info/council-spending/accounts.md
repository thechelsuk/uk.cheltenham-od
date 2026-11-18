---
layout: about-info/council-accounts
title: "Cheltenham Council Accounts"
seo_title: "Cheltenham Council Accounts: Net Spending by Service"
seo: "Cheltenham Borough Council's net spending by service for the last five years, from car parks and leisure to waste and central services."
permalink: /cheltenham-council-spending/accounts
description: "Cheltenham Borough Council's net day-to-day spending on each service for the last five financial years, from the government's revenue outturn figures."
type: "about"
schema: council-accounts
---

{% assign accounts = site.data["council-accounts"] %}
{% assign latest_total = accounts.total.years | last %}

## Cheltenham Borough Council's Spending by Service

In {{ accounts.latest_year }}, Cheltenham Borough Council's services cost a net **{{ latest_total.display }}** after their own fees, charges and grants were taken off. The table shows how that splits between services each year since {{ accounts.years.first }}, as the council reports it to the government after each financial year ends.

These are the council's year-end figures for each service. For the individual payments behind its spending, see [council spending](/cheltenham-council-spending), and for the full audited accounts, the council's [statement of accounts](https://www.cheltenham.gov.uk/about-the-council/council-performance-and-spending/financial-information/statement-of-accounts-and-annual-reports/).
