---
layout: page
title: "Local Open Data for Cheltenham & Gloucestershire"
seo_title: "Cheltenham Fuel Prices, House Prices, Crime & News"
seo: "Free Cheltenham open data for Gloucestershire: compare local fuel prices, check crime stats, house prices, flood warnings, food banks, GPs, planning and news."
permalink: /
type: "cod"
description: "The open data hub for Cheltenham and Gloucestershire. Fuel prices, crime figures, flood alerts, food banks, GPs, planning, local news and weather — all free, in one place."
---

<!-- weather_marker starts -->
## On Thursday, 10 September 2026

- The average temperature today is 18.8˚C,
- With highs of 19.8˚C and lows of 9.8˚C,
- It may feel like 18.8˚C with light rain
- The wind speed is 7.7m/s
- The pressure is 1016.41hPa and humidity is 55%
- The sun will rise at 06:34 and set at 19:36

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
