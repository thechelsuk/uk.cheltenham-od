---
layout: home-property/planning
title: "Cheltenham Planning Applications"
seo_title: "Planning Permission in Cheltenham: Recent Applications"
seo: "Planning permission in Cheltenham: recent planning applications to Cheltenham Borough Council on a map and in a table, with the council's decisions."
permalink: /cheltenham-planning-applications
description: "Recent planning applications in Cheltenham, on a map and in a table, from Cheltenham Borough Council's PublicAccess portal, with the council's decisions."
type: "property"
schema: planschema
filters:
  - table: 1
    column: "Status"
  - table: 2
    column: "Decision"
---

{% assign planning = site.data["planning-applications"] %}

## Planning Applications in Cheltenham

This page shows recent planning applications in Cheltenham, taken from Cheltenham Borough Council's planning register: {{ planning.received_count }} applications received in the last {{ planning.lookback_days }} days, with {{ planning.pending }} still awaiting a decision and {{ planning.decided_count }} already decided. They range from single-home extensions and tree work to major housing schemes, and you can see each one on a map and in a table.

Cheltenham Borough Council decides these applications for planning permission, not this site, which only republishes the council's public register. To search the register yourself or read an application's full case file, use the council's [planning application search](https://publicaccess.cheltenham.gov.uk/online-applications/), and each row in the tables below links to its entry there.

Data is refreshed {{ planning.refresh }} from the council's PublicAccess portal. The map shows where each application is, and the tables have a pin link for each one. A pin sits at the centre of the application's postcode, so it shows the area rather than the exact site, and applications with no postcode in their address can't be placed. Where several applications share a postcode, they share a pin. Select a pin to read them. Sort the table by any column, or open an application's status to read the full case file.

Many of the town's buildings are protected: our [listed buildings](/cheltenham-listed-buildings) map shows every listed building and scheduled monument. If you're weighing up an area to move to, our [moving to Cheltenham guide](/moving-to-cheltenham) covers what's being built nearby alongside house prices, schools and safety.
