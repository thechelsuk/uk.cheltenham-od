---
layout: where-to-eat
title: "Where to Eat in Cheltenham: Restaurants, Pubs and Takeaways"
seo: "Where to eat in Cheltenham: a map and list of restaurants, cafés, pubs, bars and takeaways, each with its official Food Standards Agency hygiene rating."
permalink: /cheltenham-where-to-eat
description: "Restaurants, cafés, pubs, bars and takeaways in Cheltenham on a map, each with its official food hygiene rating and the date it was last inspected."
type: "activities"
schema: where-to-eat
venue_types:
  - type: "Restaurant/Cafe/Canteen"
    label: "Restaurants and cafés"
  - type: "Pub/bar/nightclub"
    label: "Pubs and bars"
  - type: "Takeaway/sandwich shop"
    label: "Takeaways and sandwich shops"
---

{% include sponsor.html %}

{% assign type_names = page.venue_types | map: "type" %}
{% assign venues = site.data["food-standards"] | where_exp: "v", "type_names contains v.type" %}
{% assign five_star = venues | where: "rating", "5" | size %}

## Where to Eat in Cheltenham

Find somewhere to eat or drink in Cheltenham. The map and list below show **{{ venues.size }} restaurants, cafés, pubs, bars and takeaways**, each with the hygiene rating the Food Standards Agency gave it at its last inspection. {{ five_star }} of them hold the top rating of 5.

A hygiene rating tells you how well a venue handles food safely, from how the food is prepared and stored to how clean the premises are and how well the business is managed. It is not a review of the food, the service or the atmosphere, so use it alongside your own taste. Can't decide? The random picker below chooses a well-rated place for you. Select a pin for a venue's rating, when it was inspected and a link to its official record. The list doesn't include opening hours, and venues change them often, so check a venue's hours before you set out, especially for evenings, Sundays and bank holidays. If you'd rather see every rating band, our [food hygiene ratings](/cheltenham-food-standards) pages list all {{ site.data["food-standards"].size }} food businesses in Cheltenham, and [five-star venues](/cheltenham-food-standards/rated-five) has just the top-rated ones.

Visiting for a festival or a weekend? Our [visiting Cheltenham guide](/visiting-cheltenham) has more on where to stay and what to see, and [things to do](/explore/things-to-do) covers the rest.
