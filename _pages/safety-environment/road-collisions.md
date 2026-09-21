---
layout: road-collisions
title: "Cheltenham Road Collisions and Casualties"
seo: "Road collisions in Cheltenham, 2021 to 2025: injuries by severity, road user and road, a map of every fatal and serious collision, and when they happen."
permalink: /cheltenham-road-collisions
description: "How safe are Cheltenham's roads? Every police-recorded injury collision from 2021 to 2025 by severity, road user, road and time of day, with a map of the fatal and serious ones."
type: "environment"
schema: road-collisions
---

{% include sponsor.html %}

{% assign data = site.data["road-collisions"] %}
{% assign totals = data.totals %}
{% assign cyclists = data.by_user | where: "user", "Cyclist" | first %}
{% assign pedestrians = data.by_user | where: "user", "Pedestrian" | first %}
{% assign walk_cycle_ksi = pedestrians.fatal | plus: pedestrians.serious | plus: cyclists.fatal | plus: cyclists.serious %}
{% assign all_ksi = totals.casualties_fatal | plus: totals.casualties_serious %}
{% assign walk_cycle_share = walk_cycle_ksi | times: 100 | divided_by: all_ksi %}

## How Safe Are Cheltenham's Roads?

Between {{ data.first_year }} and {{ data.last_year }}, the police recorded **{{ totals.collisions_display }} road collisions in Cheltenham in which someone was injured**. Those collisions caused {{ totals.casualties_display }} casualties: {{ totals.casualties_fatal }} people died, {{ totals.casualties_serious }} were seriously injured and {{ totals.casualties_slight }} were slightly injured. The tables below break the figures down by year, road user, vehicle, road and time of day, and the map shows the {{ totals.ksi }} collisions in which someone was killed or seriously injured.

Cyclists made up {{ cyclists.share }}% of casualties and pedestrians {{ pedestrians.share }}%. Together, people on foot and on bikes were {{ walk_cycle_share }}% of those killed or seriously injured. If you cycle in town, our [cycle routes](/cheltenham-cycle-routes) map shows where the dedicated tracks and lanes are. To report a defect such as a pothole or a broken crossing, see [Fix My Street](/cheltenham-fix-my-street).

These figures count collisions, not how risky a road is for each journey, because they don't take account of how much traffic uses it. The busiest roads will always have the most collisions. Collisions that weren't reported to the police aren't included, and slight injuries are the most likely to go unreported. For the wider picture of safety in the town, see [crime data](/cheltenham-crime-data) and [flood warnings](/cheltenham-flood-warnings).
