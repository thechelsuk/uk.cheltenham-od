---
layout: page
title: "Glossary: Terms and Areas Used on This Site"
seo_title: "Cheltenham Open Data Glossary: Terms & Areas"
seo: "What we mean by the town centre, distance bands, wards, the borough, the constituency, postcode districts and what 'Last updated' means."
permalink: /glossary
description: "What the terms on Cheltenham Open Data mean, from how far around Cheltenham each page looks to wards and how fresh the data is."
type: "cod"
parent: /policies
---

## Glossary

The pages on this site use a few terms in the same way throughout. This page explains what they mean, starting with how far around Cheltenham each page looks.

{% assign bands = site.data["distance-bands"] %}

## Town Centre

Every "miles from the town centre" figure, and every search around Cheltenham, is measured in a straight line from one point: {{ bands.centre }}.

## Distance Bands

Pages that list places around Cheltenham use one of four distances, so that "nearby" means the same thing from page to page.

{% for band in bands.bands %}

### {{ band.label }}: {{ band.miles }} Miles

{{ band.meaning }}

- **Used for:** {% for p in band.pages %}[{{ p.name }}]({{ p.url }}){% unless forloop.last %}, {% endunless %}{% endfor %}

{% endfor %}

### Pages That Follow a Boundary or Fixed Rule

Some pages don't use a distance band:

{% for e in bands.exceptions %}

- **{{ e.name }}:** {{ e.rule }}. {{ e.why }}

{% endfor %}

## Borough

The area run by Cheltenham Borough Council: the town and the areas around it that have joined the borough over the years, such as Charlton Kings, Leckhampton and Swindon Village. Official statistics for "Cheltenham", from population to earnings, are usually for the borough.

## Ward

The borough is split into {{ site.data.wards.index.wards | size }} wards, the areas that elect borough councillors. See the [Cheltenham wards](/cheltenham-wards) page for a profile of each.

## Constituency

The area that elects Cheltenham's MP. Its boundary is set separately from the borough's and was last redrawn for the 2024 general election, so general election results and borough statistics may not cover exactly the same streets.

## Postcode District

The first half of a postcode. Cheltenham and its nearby villages are covered by GL50, GL51, GL52, GL53 and GL54, and some pages use these to decide what counts as Cheltenham.

## Last Updated and Checked

Every data page ends with **About This Data**, which names the source and its licence and says when the data last changed and how often we check it, such as "Last updated 9 September 2026, checked daily." The date moves only when the data itself changes, not each time we check and find nothing new. Lists we put together ourselves are checked monthly.
