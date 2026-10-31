---
layout: community-support/public-health
title: "Cheltenham Public Health Statistics"
seo_title: "Cheltenham Public Health: Life Expectancy & Health Stats"
seo: "Cheltenham health statistics: life expectancy, early deaths, smoking, activity, obesity, child weight by ward and cancer screening, compared with England."
permalink: /cheltenham-public-health
description: "Life expectancy, early deaths, smoking, physical activity, weight, wellbeing and cancer screening in Cheltenham, compared with England, with child weight for every ward."
type: "community"
schema: public-health
---

{% assign health = site.data["public-health"] %}
{% assign life = health.life_expectancy.latest %}
{% for group in health.groups %}{% for i in group.indicators %}{% if i.id == 92901 and i.sex == "Male" %}{% assign gap = i %}{% endif %}{% endfor %}{% endfor %}
{% assign wards_by_value = health.wards.rows | sort: "value" %}

## Public Health in Cheltenham

Public health is about how healthy a whole population is, rather than any one person: how long people live, how many die early, and the habits and conditions that shape both. This page brings together {{ health.indicator_count }} measures for Cheltenham from the Office for Health Improvement and Disparities, each next to the figure for England.

Based on deaths in {{ life.year }}, **men in Cheltenham can expect to live to {{ life.male }} and women to {{ life.female }}**, against {{ life.england_male }} and {{ life.england_female }} across England. On {{ health.better_count }} of the {{ health.indicator_count }} measures Cheltenham does significantly better than England{% if health.worse_count > 0 %}, and on {{ health.worse_count }} it does worse{% else %}, and on none does it do significantly worse{% endif %}. The averages hide wide differences within the town: men in its most deprived areas live {{ gap.value_display }} less than men in its least deprived, and the share of Year 6 children who are overweight or obese ranges from {{ wards_by_value.first.value_display }} in {{ wards_by_value.first.name }} to {{ wards_by_value.last.value_display }} in {{ wards_by_value.last.name }}.

For health services, see [GPs and pharmacies](/cheltenham-gp-pharmacies), [dentists](/cheltenham-dentists) and [A&E waiting times](/cheltenham-ae-waiting-times). For the wider picture behind these figures, see [deprivation](/cheltenham-deprivation), [child poverty](/cheltenham-child-poverty) and [air quality](/cheltenham-air-quality).
