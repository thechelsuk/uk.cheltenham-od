---
layout: things-to-do/cheltenham-town-fc
title: "Cheltenham Town Fixtures, Results & Getting to the Ground"
seo: "Cheltenham Town FC's next fixture, results and league position, plus their league record every season since 1999, against every opponent and every referee."
permalink: /cheltenham-sports/cheltenham-town-fc
description: "Cheltenham Town FC's next fixture, recent results and league position, their league history, and how to get to Whaddon Road."
type: "activities"
---

{% include sponsor.html %}
{% assign ctfc = site.data["ctfc-summary"] %}
{% assign now = ctfc.current %}
{% assign first = ctfc.seasons.last %}

## Cheltenham Town FC

Cheltenham Town — nicknamed "The Robins" — are Cheltenham's professional football club. Founded in 1887, they've played at Whaddon Road since 1932. In {{ now.season_display }} they play in {{ now.division }}, the {{ now.tier }} tier of English football, and are {{ now.position }}{% case now.position %}{% when 1, 21 %}st{% when 2, 22 %}nd{% when 3, 23 %}rd{% else %}th{% endcase %}{% unless now.complete %} after {{ now.played }} league games{% endunless %}.

{% assign non_league = ctfc.seasons.size | minus: ctfc.league_seasons %}Since {{ first.season_display }}, Cheltenham have spent {{ ctfc.league_seasons }} seasons in the Football League{% if non_league > 0 %} and {{ non_league }} in the National League{% endif %}{% if ctfc.titles.size > 0 %}, winning {% for t in ctfc.titles %}{% if t.division == "National League" %}the {% endif %}{{ t.division }} in {{ t.season_display }}{% unless forloop.last %} and {% endunless %}{% endfor %}{% endif %}. Since {{ ctfc.stats_from_display }} they have played {{ ctfc.since_record.played_display }} league matches, winning {{ ctfc.since_record.won }}, drawing {{ ctfc.since_record.drawn }} and losing {{ ctfc.since_record.lost }}.

## Cheltenham Town's League History

- [Season by season](/cheltenham-sports/cheltenham-town-fc/record): final position, record and points per game in all {{ ctfc.seasons.size }} league seasons since {{ first.season_display }}, each with its full league table.
- [Head-to-head records](/cheltenham-sports/cheltenham-town-fc/vs): Cheltenham's record against all {{ ctfc.opponents.size }} clubs they have met since {{ ctfc.stats_from_display }}, with every meeting, half-time scores and match stats.
- [Referee records](/cheltenham-sports/cheltenham-town-fc/referees): how Cheltenham have fared under all {{ site.data["ctfc-referees"].table.size }} referees who have taken charge of their league matches, with cards for both sides.
- [This season's {{ now.division }} table](/cheltenham-sports/cheltenham-town-fc/record/{{ now.season }}): the table so far and every Cheltenham league match this season.
