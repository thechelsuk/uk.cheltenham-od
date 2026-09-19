---
layout: page
title: "Government Security Alerts"
seo: "Government Alerts and Statuses for the Cheltenham, gloucestershire area checked daily"
permalink: /cheltenham-security-alerts
description: "Government Alerts and Statuses for the Cheltenham area"
type: "environment"
---

{% assign data = site.data["terrorism"] %}
{% assign history = site.data["terrorism-history"] %}
{% assign changed_at = data.published_iso | date: "%s" %}
{% assign days_since = site.time | date: "%s" | minus: changed_at | divided_by: 86400 %}

##  MI5 Threat Level

Given the Proximity to GCHQ

### {{ data.level_title | escape }}

- Current Threat Level: {{ data.level | escape }}
- It has been {{ days_since }} day{% if days_since != 1 %}s{% endif %} since the last change ({{ data.published_iso | date: "%Y-%m-%d" }})
- Details: {{ data.details | escape }}

## Threat Level History

{% if history.records.size > 0 %}
<div class="table-scroll">
    <table class="security-history-table data-table" data-sortable>
        <thead>
            <tr>
                <th scope="col" class="date">Changed</th>
                <th scope="col">Threat Level</th>
                <th scope="col">Previous Level</th>
                <th scope="col">Details</th>
            </tr>
        </thead>
        <tbody>
            {% for r in history.records %}
            <tr>
                <td class="date" data-value="{{ r.published_iso }}">{{ r.published_iso | date: "%Y-%m-%d %H:%M" }}</td>
                <td>{{ r.level | escape }}</td>
                <td>{% if r.previous_level != "" %}{{ r.previous_level | escape }}{% else %}&mdash;{% endif %}</td>
                <td>{{ r.details | escape }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

<p class="security-attribution"><small>
        Data from <a href="{{ data.source_url }}">{{ data.source }}</a>, {{ data.licence }}. Last checked
        {{ data.generated_at | date: "%-d %B %Y" }}.
    </small></p>

## Emergency Preparation

[Get Prepared for Emergencies (Gov UK)](https://prepare.campaign.gov.uk/get-prepared-for-emergencies/)
