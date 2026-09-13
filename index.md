---
layout: page
title: "Local Open Data for Cheltenham & Gloucestershire"
seo_title: "Cheltenham Fuel Prices, House Prices, Crime & News"
seo: "Free Cheltenham open data for Gloucestershire: compare local fuel prices, check crime stats, house prices, flood warnings, food banks, GPs, planning and news."
permalink: /
type: "cod"
description: "The open data hub for Cheltenham and Gloucestershire. Fuel prices, crime figures, flood alerts, food banks, GPs, planning, local news and weather — all free, in one place."
---

{% include bus-alert.html %}

## Explore Cheltenham Open Data

{% assign nav_groups = site.navigation_header | group_by: "group" %}
<div class="explore-grid">
{% for group in nav_groups %}
    <div class="explore-card">
        <h3 class="explore-card-title">{{ group.name }}</h3>
        <ul class="explore-card-links">
            {% for item in group.items limit: 3 %}
            <li><a href="{{ item.link }}">{{ item.name }}</a></li>
            {% endfor %}
        </ul>
    </div>
{% endfor %}
</div>

## Latest from Cheltenham Open Data

<ul class="home-latest-list">
{% for post in site.posts limit: 5 %}
    <li>
        <a href="{{ post.url }}">{{ post.title }}</a>
        <span class="home-latest-date">{{ post.date | date: "%-d %B %Y" }}</span>
    </li>
{% endfor %}
</ul>

- [See all announcements &rarr;](/news)

<!-- weather_marker starts -->
## On Sunday, 13 September 2026

- The average temperature today is 18.0˚C,
- With highs of 19.5˚C and lows of 17.2˚C,
- It may feel like 18.0˚C with light rain
- The wind speed is 5.4m/s
- The pressure is 1021.47hPa and humidity is 96%
- The sun will rise at 06:39 and set at 19:29

<!-- weather_marker ends -->
- [See a full 10-day Cheltenham forecast &rarr;](/cheltenham-10-day-weather-forecast)

## Local Classifieds in Cheltenham

{% assign now = site.time | date: "%s" | plus: 0 %}
{% assign count = 0 %}
{% for item in site.classifieds %}
  {% assign exp = item.expires | date: "%s" | plus: 0 %}
  {% if exp > now %}
    {% assign count = count | plus: 1 %}
  {% endif %}
{% endfor %}

- [Currently there are {{ count }} live classifieds](/cheltenham-classifieds)
- [Add yours](/submission)

{% include referral.html %}

## Sponsorships Available

{% include sponsor.html sponsor=page.sponsor %}

## Upcoming Festivals

### Cheltenham Literature Festival

- [Starting 9th October 2026](https://www.cheltenhamfestivals.org/festivals/literature-festival) &rarr;

### Cheltenham Racing Festival

- [Starting 16th March 2027](https://www.thejockeyclub.co.uk/cheltenham-festival/) &rarr;

### Cheltenham Jazz Festival

- [Starting 28th April 2027](https://www.cheltenhamfestivals.org/festivals/jazz-festival) &rarr;

### Cheltenham Science Festival

- [Starting 8th June 2027](https://www.cheltenhamfestivals.org/festivals/science-festival) &rarr;

### Cheltenham Music Festival

- [Starting 9th July 2027](https://www.cheltenhamfestivals.org/festivals/music-festival) &rarr;
