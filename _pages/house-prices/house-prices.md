---
layout: house
title: "Cheltenham House Price Data"
seo: "Is cheltenham expensive area to live, check out the average house prices in the area"
permalink: /cheltenham-house-prices
description: "Property Data from Land Registry and ONS datasets."
type: "house"
available-years:
    - 2026
    - 2025
    - 2024
    - 2023
---

## Cheltenham House Prices from Land Registry Price Paid Data

Cheltenham has seen **{{ site.data.house-summary.current.count_display }}** properties change hands over the past year{% if site.data.house-summary.current.count_change %}, {{ site.data.house-summary.current.count_change }}{% endif %}. The typical sale (median) went for **{{ site.data.house-summary.current.median_display }}**{% if site.data.house-summary.current.median_change %}, {{ site.data.house-summary.current.median_change }}{% endif %}, with an average (mean) of **{{ site.data.house-summary.current.mean_display }}**{% if site.data.house-summary.current.mean_change %}, {{ site.data.house-summary.current.mean_change }}{% endif %}. Prices ranged from {{ site.data.house-summary.current.min_display }} up to {{ site.data.house-summary.current.max_display }}{% if site.data.house-summary.current.range_prior_display %} ({{ site.data.house-summary.current.range_prior_display }}){% endif %}.

{% if site.data.house-summary.current.new_build_count > 0 %}
Of these, **{{ site.data.house-summary.current.new_build_count_display }}** were new build sales{% if site.data.house-summary.current.new_build_count_change %}, {{ site.data.house-summary.current.new_build_count_change }}{% endif %}, with a median price of {{ site.data.house-summary.current.new_build_median_display }}{% if site.data.house-summary.current.new_build_median_change %}, {{ site.data.house-summary.current.new_build_median_change }}{% endif %}.
{% else %}
No new build sales were recorded in Cheltenham over the past year.
{% endif %}

{% if site.data.house-summary.current.domestic_count > 0 %}
Excluding properties classed as "Other" in Land Registry data, {{ site.data.house-summary.current.domestic_count_display }} domestic sales were recorded over the past year{% if site.data.house-summary.current.domestic_count_change %}, {{ site.data.house-summary.current.domestic_count_change }}{% endif %}, with an average (mean) price of {{ site.data.house-summary.current.domestic_mean_display }}{% if site.data.house-summary.current.domestic_mean_change %}, {{ site.data.house-summary.current.domestic_mean_change }}{% endif %}. {% if site.data.house-summary.current.other_note %}{{ site.data.house-summary.current.other_note }}{% endif %}

### Overall Since January 2023

Across the full dataset, **{{ site.data.house-summary.full_dataset.count_display }}** Cheltenham property sales were recorded, with a median price of **{{ site.data.house-summary.full_dataset.median_display }}** (mean {{ site.data.house-summary.full_dataset.mean_display }}), ranging from {{ site.data.house-summary.full_dataset.min_display }} to {{ site.data.house-summary.full_dataset.max_display }}.
{% endif %}

### Notes

Other exclusion is based on Land Registry's own property type classification which seems to indicate non-domestic buildings and should be treated as a indicative and not a guaranteed commercial/residential split.

Recently completed sales may take 2-3 months to appear.

Thinking of relocating? Our [moving to Cheltenham guide](/moving-to-cheltenham) pulls this together with schools, crime data and neighbourhood comparisons.
