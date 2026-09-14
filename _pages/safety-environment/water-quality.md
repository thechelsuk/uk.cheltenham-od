---
layout: water-quality
title: Cheltenham River Water Quality
seo: "River water quality readings for the River Chelt and nearby brooks near Cheltenham, from the Environment Agency's Water Quality Archive."
description: "Chemical water quality readings for the River Chelt and nearby brooks, from the Environment Agency's Water Quality Archive."
permalink: /cheltenham-water-quality
type: "alert"
schema: water-quality
---

## About This Data

The Environment Agency periodically samples rivers and brooks for a batch of
chemical determinands — pH, temperature, nutrients like nitrate and
ammoniacal nitrogen, and others — testing each sampling point roughly once a
month. This page shows every determinand from the most recent visit to each
open river sampling point within {{ site.data['water-quality'].radius_miles }}
miles of Cheltenham, covering the River Chelt and the brooks that feed it.

This is chemical water quality, not sewage discharge activity — see our
[sewage overflow status](/cheltenham-sewage-overflows) page for that — and
it isn't a flood risk indicator either; see [flood warnings](/cheltenham-flood-warnings)
for that.

## FAQs

### What Is a "Determinand"?

- The Environment Agency's term for a specific substance or property measured in a water sample — pH, temperature, or the concentration of a particular chemical like nitrate. Each sampling visit tests a batch of them at once, which is why one visit produces many rows on the table above.

### What Do the Common Determinands Mean?

- **pH** — how acidic or alkaline the water is, on a 0-14 scale; most healthy rivers sit around neutral, roughly 6.5-8.5.
- **Temperature of Water** — in degrees Celsius; sustained high temperatures can lower how much oxygen the water holds.
- **Oxygen, Dissolved as O2 / % Saturation** — how much oxygen is available for fish and other aquatic life; low values can indicate pollution or algal blooms.
- **Ammoniacal Nitrogen as N / Ammonia un-ionised as N** — nitrogen from sources like sewage or agricultural runoff; higher levels can be toxic to fish.
- **Nitrate as N / Nitrite as N / Nitrogen, Total Oxidised as N** — other nitrogen compounds, often from fertiliser runoff or treated sewage effluent.
- **Orthophosphate, reactive as P / Phosphorus, Total as P** — phosphorus compounds, a common cause of excessive plant and algae growth when levels are high.
- **BOD : 5 Day ATU** (Biochemical Oxygen Demand) — how much oxygen microorganisms use breaking down organic matter in the sample over 5 days; a higher figure suggests more organic pollution.
- **Conductivity at 25 C** — how well the water conducts electricity, a general indicator of dissolved mineral/salt content.
- Metals (**Cadmium**, **Lead**, **Nickel**, etc), **Chloride**, **Calcium**, **Magnesium**, **Silica** and **Suspended Solids** are also routinely tested for; specialist reference values exist for each but are outside the scope of this page.

### What Does a Value Like "<0.03" Mean?

- The substance was tested for but not detected above the laboratory's detection limit — the true value is somewhere below the number shown, not exactly that number.

### What About "GCMS Screen", "LCMS Screen" or "Non Target Screening"?

- These are broad laboratory screening tests for a wide range of chemicals at once (pesticides, industrial compounds and similar), reported as "Semi Quantitative" or a plain presence/absence result rather than a single concentration value — hence values like "1" with a unit of "Text".

### Where Does the Data Come From?

- The Environment Agency's [Water Quality Archive](https://environment.data.gov.uk/water-quality/), released under the Open Government Licence v3.0.
