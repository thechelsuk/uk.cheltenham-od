---
layout: page
title: "Government Security Alerts"
seo: "Government Alerts and Statuses for the Cheltenham, gloucestershire area checked daily"
permalink: /cheltenham-security-alerts
description: "Government Alerts and Statuses for the Cheltenham area"
type: "environment"
schema: security
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

{% assign new_records = history.records | where: "reporting_format", "new" %}
{% assign old_records = history.records | where: "reporting_format", "old" %}

### Changes Since July 2019

<div class="table-scroll">
    <table class="security-history-table data-table" data-sortable>
        <thead>
            <tr>
                <th scope="col" class="date">Changed</th>
                <th scope="col">National Threat Level</th>
                <th scope="col">Northern Ireland Threat Level</th>
                <th scope="col">Notes</th>
            </tr>
        </thead>
        <tbody>
            {% for r in new_records %}
            <tr>
                <td class="date" data-value="{{ r.published_iso }}">{{ r.published_iso | date: "%Y-%m-%d" }}</td>
                <td>{{ r.level_title | escape }}</td>
                <td>{{ r.northern_ireland_level | capitalize | escape }}</td>
                <td>{% if r.note %}{{ r.note | escape }}{% else %}&mdash;{% endif %}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

### Changes From August 2006 to July 2019

<div class="table-scroll">
    <table class="security-history-old-table data-table" data-sortable>
        <thead>
            <tr>
                <th scope="col" class="date">Changed</th>
                <th scope="col">International Terrorism</th>
                <th scope="col">Northern Ireland-Related, in Northern Ireland</th>
                <th scope="col">Northern Ireland-Related, in Great Britain</th>
                <th scope="col">Notes</th>
            </tr>
        </thead>
        <tbody>
            {% for r in old_records %}
            <tr>
                <td class="date" data-value="{{ r.published_iso }}">{{ r.published_iso | date: "%Y-%m-%d" }}</td>
                <td>{{ r.level_title | escape }}</td>
                <td>{% if r.northern_ireland_level != "" %}{{ r.northern_ireland_level | capitalize | escape }}{% else %}Not reported{% endif %}</td>
                <td>{% if r.great_britain_level != "" %}{{ r.great_britain_level | capitalize | escape }}{% else %}Not reported{% endif %}</td>
                <td>{% if r.note %}{{ r.note | escape }}{% else %}&mdash;{% endif %}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<p class="security-attribution"><small>
        Current level from <a href="{{ data.source_url }}">{{ data.source }}</a>, {{ data.licence }}. Last checked
        {{ data.generated_at | date: "%-d %B %Y" }}. Changes before 19 September 2026 were compiled from
        <a href="{{ history.backfill_source.url }}">{{ history.backfill_source.name }}</a>
        (<a href="{{ history.backfill_source.licence_url }}">{{ history.backfill_source.licence }}</a>).
    </small></p>

## Emergency Preparation

[Get Prepared for Emergencies (Gov UK)](https://prepare.campaign.gov.uk/get-prepared-for-emergencies/)

## Security Alerts FAQs

### What Do the UK Terrorism Threat Levels Mean?

There are five levels. Low means an attack is highly unlikely. Moderate means an attack is possible, but not likely. Substantial means an attack is likely. Severe means an attack is highly likely. Critical means an attack is highly likely in the near future.

### How Does the Government Respond to Each Threat Level?

Government departments and agencies respond in one of three states. Normal applies at Low and Moderate and means routine protective security. Heightened applies at Substantial and Severe and means additional and sustainable protective security measures. Exceptional applies at Critical and means maximum protective security.

### Who Sets the Threat Level and How?

The Joint Terrorism Analysis Centre sets the national threat level and MI5 sets the Northern Ireland-related level. They weigh the available intelligence, the capability and intentions of the terrorists involved, and how soon an attack might happen. Threat levels have no set expiry date but are reviewed regularly.

### What Changed in the 2019 Reporting Format?

Before July 2019 the government published a national threat level for international terrorism and, from September 2010, threat levels for Northern Ireland-related terrorism in Northern Ireland and in Great Britain. Since 23 July 2019 there is a single national threat level covering all forms of terrorism, including Islamist, Northern Ireland, left-wing and right-wing terrorism, plus a separate Northern Ireland-related threat level for Northern Ireland.

### Why Is the History Shown in Two Tables?

Because the reporting format changed in 2019, the two periods can't be compared directly. The first table covers changes since July 2019 in the current format. The second covers August 2006 to July 2019, when international terrorism was reported separately from Northern Ireland-related terrorism.

### Where Does the Threat Level History Come From?

Changes since this page began tracking MI5's threat level feed on 19 September 2026 are recorded automatically. Earlier changes were compiled by hand from [Wikipedia's UK Threat Levels article](https://en.wikipedia.org/wiki/UK_Threat_Levels).

### How Often Is This Page Updated?

The threat level is checked once a day. It changes rarely, so the date of the last change is shown above.
