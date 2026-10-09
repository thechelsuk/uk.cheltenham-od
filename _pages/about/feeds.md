---
layout: page
title: Cheltenham Open Data Feeds
seo: "Every Cheltenham Open Data RSS and Atom feed: local news, our announcements and live alerts for floods, power cuts, road closures and more."
permalink: /feeds
description: "Every feed Cheltenham Open Data publishes, from local news to live alerts, to follow in any RSS or feed reader."
type: "cod"
---

Follow Cheltenham Open Data in any RSS or feed reader, such as Feedly, NetNewsWire or Inoreader. Copy a feed's address into your reader to get each update as it is published, with no account or newsletter sign-up needed.

New to feeds? Start with the [all-in-one alerts feed](/feeds/alerts.xml) for anything that might affect your day in Cheltenham, and [our feed](/feeds/main.xml) for new pages and analysis.

{% assign groups = site.feeds | group_by: "group" %}
{% for group in groups %}

## {{ group.name }}

{% for feed in group.items %}

- **[{{ feed.name }}]({{ feed.link }})**: {{ feed.description }}

{% endfor %}
{% endfor %}

## Frequently Asked Questions

### What Is a Feed?

- A feed is a web address that a feed reader checks for new updates, so you see them as they are published without visiting the site.
- These are Atom feeds, which every RSS reader supports.

### Do Feeds Cost Anything?

- No. Every feed is free to use, with no account needed.
