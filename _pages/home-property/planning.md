---
layout: planning
title: "Cheltenham Planning Applications"
seo: "Track recent planning applications submitted to Cheltenham Borough Council on a map and in a table — new homes, conversions, extensions and commercial schemes, updated daily."
permalink: /cheltenham-planning-applications
description: "Recent planning applications submitted to Cheltenham Borough Council, on a map and in a table, updated daily from the council's PublicAccess portal."
type: "property"
schema: planschema
---

{% assign planning = site.data["planning-applications"] %}

## What Is Being Planned in Cheltenham

This page tracks the {{ planning.received_count }} applications Cheltenham Borough Council has received in the last {{ planning.lookback_days }} days with {{ planning.pending }} still awaiting a decision and {{ planning.decided_count }} already determined. Applications range from single-home extensions to major housing schemes, as well as managing trees, lots and lots of trees.

Data is refreshed daily from the council's PublicAccess portal. The map shows where each application is, and the tables have a pin link for each one. A pin sits at the centre of the application's postcode, so it shows the area rather than the exact site, and applications with no postcode in their address can't be placed. Where several applications share a postcode, they share a pin. Select a pin to read them. Sort the table by any column, or open an application's status to read the full case file.

If you're weighing up an area to move to, our [moving to Cheltenham guide](/moving-to-cheltenham) covers what's being built nearby alongside house prices, schools and safety.
