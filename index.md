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

<div class="home-hero-grid">
    <div class="home-hero-weather">
        <h2>Weather at a Glance</h2>

<!-- weather_marker starts -->
<div class="weather-glance">
    <p class="weather-glance-date">Sunday, 13 September 2026</p>
    <div class="weather-glance-header">
        <img src="https://openweathermap.org/img/wn/10d@2x.png" alt="light rain" class="weather-glance-icon" width="80" height="80">
        <div>
            <span class="weather-glance-temp">18.0&deg;C</span>
            <span class="weather-glance-desc">Light rain &middot; feels like 18.0&deg;C</span>
        </div>
    </div>
    <ul class="weather-glance-stats">
        <li><span>High / Low</span><strong>19.5&deg; / 17.2&deg;</strong></li>
        <li><span>Wind</span><strong>5.4 m/s</strong></li>
        <li><span>Humidity</span><strong>96%</strong></li>
        <li><span>Sunrise / Sunset</span><strong>06:39 / 19:29</strong></li>
    </ul>
</div>

<!-- weather_marker ends -->
        <p><a href="/cheltenham-10-day-weather-forecast">See a full 10-day Cheltenham forecast &rarr;</a></p>
    </div>
    <div class="home-hero-categories">
        <h2>Explore by Category</h2>
        {% include home-categories.html %}
    </div>
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
