---
layout: house
title: "Cheltenham House Price Data"
seo_title: "Cheltenham House Prices: Average Prices and Sales Data"
seo: "Cheltenham house prices: average and median sale prices, number of sales and price changes by property type, from Land Registry and ONS data."
permalink: /cheltenham-house-prices
description: "Property Data from Land Registry and ONS datasets."
type: "property"
schema: house-prices
available-years:
    - 2026
    - 2025
    - 2024
    - 2023
---

## Cheltenham House Prices from Land Registry Price Paid Data

Cheltenham has seen **{{ site.data.house-summary.current.count_display }}** properties change hands in the {{ site.data.house-summary.current.period_label | default: "past year" }}{% if site.data.house-summary.current.count_change %}, {{ site.data.house-summary.current.count_change }}{% endif %}. The typical sale (median) went for **{{ site.data.house-summary.current.median_display }}**{% if site.data.house-summary.current.median_change %}, {{ site.data.house-summary.current.median_change }}{% endif %}, with an average (mean) of **{{ site.data.house-summary.current.mean_display }}**{% if site.data.house-summary.current.mean_change %}, {{ site.data.house-summary.current.mean_change }}{% endif %}. Prices ranged from {{ site.data.house-summary.current.min_display }} up to {{ site.data.house-summary.current.max_display }}{% if site.data.house-summary.current.range_prior_display %} ({{ site.data.house-summary.current.range_prior_display }}){% endif %}.

{% if site.data.house-summary.current.new_build_count > 0 %}
Of these, **{{ site.data.house-summary.current.new_build_count_display }}** {% if site.data.house-summary.current.new_build_count == 1 %}was a new build sale{% else %}were new build sales{% endif %}{% if site.data.house-summary.current.new_build_count_change %}, {{ site.data.house-summary.current.new_build_count_change }}{% endif %}, with a median price of {{ site.data.house-summary.current.new_build_median_display }}{% if site.data.house-summary.current.new_build_median_change %}, {{ site.data.house-summary.current.new_build_median_change }}{% endif %}.
{% else %}
No new build sales were recorded in Cheltenham in the {{ site.data.house-summary.current.period_label | default: "past year" }}.
{% endif %}

{% if site.data.house-summary.current.domestic_count > 0 %}
Excluding properties classed as "Other" in Land Registry data, {{ site.data.house-summary.current.domestic_count_display }} domestic sales were recorded in the {{ site.data.house-summary.current.period_label | default: "past year" }}{% if site.data.house-summary.current.domestic_count_change %}, {{ site.data.house-summary.current.domestic_count_change }}{% endif %}, with an average (mean) price of {{ site.data.house-summary.current.domestic_mean_display }}{% if site.data.house-summary.current.domestic_mean_change %}, {{ site.data.house-summary.current.domestic_mean_change }}{% endif %}. {% if site.data.house-summary.current.other_note %}{{ site.data.house-summary.current.other_note }}{% endif %}
{% endif %}

### Overall Since 1995

{% assign history = site.data["cheltenham-house-price-history"] %}
{% assign overall = site.data.house-summary.overall %}
{% assign first_year = history.years | first %}
{% capture previous_year %}{{ site.time | date: "%Y" | minus: 1 }}{% endcapture %}
{% assign previous = site.data.house-summary.by_year | where: "year", previous_year | first %}
{% if overall %}Land Registry has recorded **{{ overall.count_display }}** Cheltenham property sales from {{ overall.first_year }} to {{ overall.to_month }}, with a mean price of **{{ overall.mean_display }}**, ranging from {{ overall.min_display }} up to {{ overall.max_display }}. {% else %}Land Registry records go back to {{ history.first_year }}. {% endif %}The typical (median) sale in Cheltenham was **{{ first_year.median_display }}** in {{ first_year.year }}{% if previous %} and **{{ previous.median_display }}** in {{ previous.year }}{% endif %}. The charts and table below show every year in between, overall and by property type, and the figures are not adjusted for inflation. The current year is a part year, so its sales count is lower than a full year's.

### Notes

Other exclusion is based on Land Registry's own property type classification which seems to indicate non-domestic buildings and should be treated as a indicative and not a guaranteed commercial/residential split.

Recently completed sales may take 2-3 months to appear, so comparisons only use complete months, and a year that isn't over yet is compared with the same months of the year before.

Thinking of relocating? Our [moving to Cheltenham guide](/moving-to-cheltenham) pulls this together with schools, crime data and neighbourhood comparisons. See also our [council tax charges by area and band](/cheltenham-council-tax) page.

For the bigger picture beyond individual sales, see how many homes Cheltenham actually [adds each year](/cheltenham-house-prices/housing-supply) — including student accommodation — and how the town's [total property stock has grown](/cheltenham-house-prices/council-tax-stock) since 1993.
