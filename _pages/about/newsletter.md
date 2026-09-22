---
layout: page
title: "The Cheltenham Week Ahead: Weekly Cheltenham Newsletter"
seo: "The Cheltenham Week Ahead is a free weekly email: the week's weather, roadworks, events, what's new on the site and the top local stories."
permalink: /newsletter
description: "A free weekly Cheltenham email every Monday morning, with the week's weather, roadworks, events and top local stories, from Cheltenham Open Data."
type: "cod"
---

## {{ site.newsletter.name }}

{{ site.newsletter.tagline }}

{% if site.newsletter.buttondown_username.size > 0 %}
{% include newsletter-signup.html source="newsletter-page" %}
{% else %}
Sign-up opens soon.
{% endif %}

## What You Get

Each Monday morning, one short email built from the same open data that powers this site:

- **This week in Cheltenham:** the forecast, roadworks, and what's on.
- **New on the site:** new pages and refreshed data, so you know what has changed.
- **The week's top stories:** a handful of local headlines, each with a line of context and a link to the original.
- **Somewhere to eat:** one place to try, picked from local venues.

It is free, it goes out once a week, and you can unsubscribe with one click from any email.

## Past Issues

{% assign issues = site.newsletters %}
{% if issues %}
{% assign issues = issues | sort: "issue_date" | reverse %}
{% endif %}
{% if issues.size > 0 %}
<ul>
    {% for issue in issues %}
    <li><a href="{{ issue.url }}">{{ issue.title }}</a></li>
    {% endfor %}
</ul>
{% else %}
No issues yet — the first one lands soon after sign-up opens.
{% endif %}

## Your Email Address

We only use your email address to send you the newsletter and the confirmation link you need to click when you sign up. We don't sell it or share it with anyone, including sponsors. The [privacy policy](/privacy#newsletter) explains exactly what we collect and who handles it for us.

## FAQs

### How Often Will I Hear From You?

- Once a week, on Monday morning. There are no extra emails beyond the confirmation message when you sign up.

### Why Do I Need to Confirm My Email Address?

- We send a confirmation link first so we know the address is yours and you really want the newsletter. Until you click it you won't be subscribed.

### Can I Read It Without Signing Up?

- Yes. The [daily news summary feed](/feeds/news-summary.xml) gives you the day's headlines in any feed reader, and the [site announcements](/news) list everything new on Cheltenham Open Data.
