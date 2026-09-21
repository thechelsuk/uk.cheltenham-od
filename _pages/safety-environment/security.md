---
layout: security
title: "Government Security Alerts"
seo_title: "UK Terrorism Threat Level: Current Level and History"
seo: "The current UK terrorism threat level, days since it last changed & every change since 2006, with what each level means. Tracked for Cheltenham, checked daily."
permalink: /cheltenham-security-alerts
description: "The UK terrorism threat level and how it has changed since 2006, with what each level means and how the government responds."
type: "environment"
schema: security
---

{% assign data = site.data["terrorism"] %}
{% assign changed_at = data.published_iso | date: "%s" %}
{% assign days_since = site.time | date: "%s" | minus: changed_at | divided_by: 86400 %}

## MI5 Threat Level

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
