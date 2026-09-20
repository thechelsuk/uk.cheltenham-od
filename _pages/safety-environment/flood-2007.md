---
layout: page
title: "The Summer 2007 Floods in Cheltenham"
seo: "What happened in Cheltenham in the June and July 2007 floods: how many properties flooded, where, why the River Chelt defences were overwhelmed, and the highest river levels recorded since."
permalink: /cheltenham-flood-warnings/2007-floods
description: "The June and July 2007 floods in Cheltenham: what happened, where, and the record river levels still held by the gauges around the town."
type: "environment"
---

{% include sponsor.html %}

[← Back to flood warnings history](/cheltenham-flood-warnings/history) &middot; [Live river levels and flood warnings](/cheltenham-flood-warnings)

## What Happened in 2007

Cheltenham's worst modern flooding came in the summer of 2007, in two separate floods, one in June and one on 20 July. They followed the wettest May to July in England and Wales since national records began in 1766<sup>[<a href="#source-1">1</a>]</sup>. Gloucestershire received 197mm of rain in July 2007, more than four times the average monthly rainfall recorded since 1766, and it fell on ground that was already saturated, so drains, sewers and streams were quickly overwhelmed<sup>[<a href="#source-1">1</a>]</sup>.

Around 600 properties flooded in Cheltenham in July<sup>[<a href="#source-1">1</a>]</sup>, and Gloucestershire County Council's later surface water management plan puts the figure for the summer floods at over 600<sup>[<a href="#source-2">2</a>]</sup>. The water came from several sources at once: surface runoff, overloaded drains and sewers, and the River Chelt, Hatherley Brook, Wymans Brook and the Mill Stream<sup>[<a href="#source-1">1</a>], [<a href="#source-2">2</a>]</sup>. The July flood exceeded the design of the River Chelt Flood Alleviation Scheme, and about 230 properties flooded as a result<sup>[<a href="#source-1">1</a>], [<a href="#source-2">2</a>]</sup>. The worst-hit areas listed in the plan were Whaddon (about 250 homes), the River Chelt (about 230), Hatherley and Warden Hill (about 100), Charlton Kings (about 70) and Prestbury (over 70)<sup>[<a href="#source-2">2</a>]</sup>. The railway line between Cheltenham and Birmingham was also affected by floodwater<sup>[<a href="#source-1">1</a>]</sup>. The July flood was assessed as having less than a 0.8% (1 in 125) chance of happening in any year, and the June flood a 1.33% (1 in 75) chance<sup>[<a href="#source-1">1</a>], [<a href="#source-2">2</a>]</sup>.

## Beyond Cheltenham

Beyond the town, the River Severn flooded. The Gloucester Docks gauge peaked at 4.92 metres on 23 July, only 1cm below the highest level recorded there, in 1947<sup>[<a href="#source-1">1</a>]</sup>. According to Wikipedia's account of the floods, Tewkesbury was cut off and its Abbey flooded for the first time in 247 years, the Mythe Water Treatment Works was flooded on 22 July, about 50,000 homes lost power on 23 July when the Castle Meads electricity substation had to be shut down, and an estimated 420,000 people, including most of the population of Gloucester, Cheltenham and Tewkesbury, were without running water by 24 July, with supplies not restored until 7 August<sup>[<a href="#source-3">3</a>]</sup>.

## Flooding Before and After 2007

The River Chelt had also caused significant flooding in 1979<sup>[<a href="#source-4">4</a>]</sup>. The 2007 floods led to an independent national review of flooding by Sir Michael Pitt<sup>[<a href="#source-1">1</a>]</sup>.

## Highest Levels on Record at Each Gauge

The gauges on the [flood warnings page](/cheltenham-flood-warnings) still show the mark of that summer: the Environment Agency's records give several of them a highest-ever level from June or July 2007, listed below<sup>[<a href="#source-5">5</a>]</sup>.

{% assign rivers = site.data["river-levels"] %}
<div class="table-scroll">
<table class="flood-records-table data-table" data-sortable>
<thead>
<tr>
<th scope="col">Gauge</th>
<th scope="col">Watercourse</th>
<th scope="col" class="number">Highest Level on Record</th>
<th scope="col" class="date">Date</th>
</tr>
</thead>
<tbody>
{% for s in rivers.stations %}{% if s.record %}<tr>
<td data-val="{{ s.label | downcase }}">{{ s.label }}</td>
<td>{{ s.river | default: "River Chelt" }}</td>
<td class="number" data-val="{{ s.record }}">{{ s.record_display }}</td>
<td class="date" data-val="{{ s.record_date }}">{{ s.record_date }}</td>
</tr>{% endif %}{% endfor %}
</tbody>
</table>
</div>

## Sources

<ol class="sources">
<li id="source-1">Halcrow Group Limited for Cheltenham Borough Council, <a href="https://www.gloucestershire.gov.uk/media/6442/cheltenham_borough_council_level_1_sfra_final-28375.pdf">Strategic Flood Risk Assessment for the Local Development Framework, Level 1, Volume 1</a>, September 2008, sections 4.5.9 to 4.5.16 (pages 40 to 42 of the report, PDF pages 43 and 44).</li>
<li id="source-2">Gloucestershire County Council, <a href="https://www.gloucestershire.gov.uk/media/gljhs0cc/1_cheltenham_swmp_final_report-63566.pdf">Cheltenham Surface Water Management Plan, Report (Phases 1-3)</a>, December 2011, section 1 (PDF pages 9 and 10) and section 3.1.2.2 (PDF page 24).</li>
<li id="source-3">Wikipedia, <a href="https://en.wikipedia.org/wiki/2007_United_Kingdom_floods">2007 United Kingdom floods</a>, Gloucestershire section.</li>
<li id="source-4">Wikipedia, <a href="https://en.wikipedia.org/wiki/River_Chelt">River Chelt</a>, citing the Gloucestershire Wildlife Trust's Love Your River Chelt project.</li>
<li id="source-5">Highest levels on record: Environment Agency <a href="https://environment.data.gov.uk/flood-monitoring/doc/reference">flood monitoring API</a>, station stage scales.</li>
</ol>
