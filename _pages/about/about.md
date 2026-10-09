---
layout: page
title: About Cheltenham Open Data
seo_title: "About Cheltenham Open Data: Who Runs It and How It Works"
permalink: /about
description: "About Cheltenham Open Data — a fast, independent, privacy-first site putting useful local data in the hands of people in Cheltenham and Gloucestershire."
type: "cod"
seo: "About Cheltenham Open Data: what the site offers, how the data is gathered and curated, how it's funded and kept independent, and who runs it."
---

## What Cheltenham Open Data Is

Cheltenham Open Data puts the town's public information in one place. Fuel prices, flood warnings, house prices, planning applications, school ratings, bus routes, care homes and more come from more than 60 official sources and are kept up to date automatically, some every few minutes and others as new figures are published.

It's free, fast and independent: no pop-ups, no tracking cookies and no clickbait, just the information people in Cheltenham look for, laid out to read quickly on a phone.

## Why It Exists

Useful local information is scattered across council PDFs, government spreadsheets and national sites that rarely focus on Cheltenham. This site brings it together and keeps it current, so you can check the cheapest fuel nearby, whether a street is in a flood zone or how a school was rated in a few seconds. [Read why Cheltenham Open Data was built →](/news/why-cheltenham-open-data-exists)

## Who Runs It

Cheltenham Open Data is built and run by Mat Benfield ([thechels.uk](https://thechels.uk)), who has lived in Cheltenham for more than 20 years. For a similar site, or a data project of your own, [get in touch](/contact).

## What You'll Find Here

{% include site-figures.html %}
{{ data_pages_count }} data pages in six topics, drawn from {{ site.data.sources | size }} data sources:

- **[Safety & Environment](/explore/safety-environment)**: crime figures, road collisions, flood warnings and river levels, air and water quality, power cuts, wildfire risk and street reports.
- **[Getting Around](/explore/getting-around)**: fuel prices, EV charging, car parks, roadworks, street works, buses, trains and cycle routes.
- **[Home & Property](/explore/home-property)**: house prices, rents, council tax, planning, broadband and a profile of every ward.
- **[Community & Support](/explore/community-support)**: food banks, helplines, GPs, pharmacies and dentists, A&E waiting times, care homes, charities and the COVID-19 pandemic.
- **[Things to Do](/explore/things-to-do)**: events, festivals, sport, where to eat, play parks and places to stay.
- **[About Cheltenham](/explore/about-info)**: the town [in numbers](/cheltenham-in-numbers), population, the economy, politics, schools and childcare, local news and the weather.

There's also a free [weekly newsletter](/newsletter), local [classifieds](/cheltenham-classifieds) and [Fix My Street](/cheltenham-fix-my-street).

## How the Data Is Made

Most of the data comes from public sources, such as the ONS, the Environment Agency, the NHS and Cheltenham Borough Council. Scripts fetch each dataset on its own schedule and the site rebuilds itself, and every new dataset is checked by hand before it goes live.

Not everything comes from an official source, though. Some lists are researched and put together by hand, and kept up to date as things change.

Each page says where its data comes from, under what licence and when it was last updated, and the [Terms of Use](/terms) list every licence.

## How It's Funded

The site is free to use, and always will be. It's kept going by optional [sponsorship](/sponsor), small affiliate commissions when you buy through some links, and [ko-fi donations](https://ko-fi.com/thechelsuk) — never by selling your data or tracking you. Sponsored placements are always clearly labelled and never influence the data or editorial content. See the [Privacy Policy](/privacy) for exactly what is and isn't collected.

## Get Involved

Spotted an error, or want to suggest a dataset? [Get in touch](/contact) — local input is what keeps this accurate. You can also [submit a classified advert](/submission) or report a local issue through [Fix My Street](/cheltenham-fix-my-street).

## Technology & Sustainability

The site is built as static HTML, CSS, and a little JavaScript, so it's lightning quick on the client end. Python and GitHub Actions handle most of the compute, with a little run on the developer's local machine; pages are built and deployed to GitHub Pages, and DNS and forms are managed by Cloudflare and Cloudflare Workers.

> Only 0.05g of CO₂ is produced every time someone visits this website. This website appears to be running on sustainable energy - [Source](https://www.websitecarbon.com/website/cheltenham-od-uk/)

[![Green Web Foundation badge](https://app.greenweb.org/api/v3/greencheckimage/cheltenham-od.uk?nocache=true)](https://www.thegreenwebfoundation.org/green-web-check/?url=cheltenham-od.uk)

[Check it out on Product Hunt →](https://www.producthunt.com/products/cheltenham-open-data?embed=true&utm_source=embed&utm_medium=post_embed)
