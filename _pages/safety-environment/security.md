---
layout: page
title: "Government Security Alerts"
seo: "The current UK terrorism threat level, days since it last changed & every change since 2006, with what each level means. Tracked for Cheltenham, checked daily."
permalink: /cheltenham-security-alerts
description: "The UK terrorism threat level and how it has changed since 2006, with what each level means and how the government responds."
type: "environment"
schema: security
---

{% assign data = site.data["terrorism"] %}
{% assign history = site.data["terrorism-history"] %}
{% assign changed_at = data.published_iso | date: "%s" %}
{% assign days_since = site.time | date: "%s" | minus: changed_at | divided_by: 86400 %}

##  MI5 Threat Level

GCHQ (Government Communications Headquarters) is based in Cheltenham. One of the
UK's three intelligence and security agencies, alongside MI5 and MI6, it works
from a circular headquarters in Benhall known locally as the Doughnut, and
employs thousands of people in and around the town.

The national threat level is set for the whole UK, so it doesn't measure a
threat to Cheltenham specifically. We track it here because of that local
connection, and to show how it has changed over time.

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
            </tr>
        </thead>
        <tbody>
            {% for r in new_records %}
            {% assign older = new_records[forloop.index] %}
            {% if older and older.level == r.level %}{% continue %}{% endif %}
            <tr>
                <td class="date" data-value="{{ r.published_iso }}">{{ r.published_iso | date: "%Y-%m-%d" }}</td>
                <td>{{ r.level_title | escape }}</td>
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
                <th scope="col">Northern Ireland-Related, in Great Britain</th>
            </tr>
        </thead>
        <tbody>
            {% for r in old_records %}
            <tr>
                <td class="date" data-value="{{ r.published_iso }}">{{ r.published_iso | date: "%Y-%m-%d" }}</td>
                <td>{{ r.level_title | escape }}</td>
                <td>{% if r.great_britain_level != "" %}{{ r.great_britain_level | capitalize | escape }}{% else %}Not reported{% endif %}</td>
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
