# Adding a New Data Page

This is the standard shape of a data page on Cheltenham Open Data. It's not a hard rule for every page on the site — a handful of pages are pure curated markdown (`_pages/sports.md`, `_pages/third-spaces.md`) with no fetcher behind them — but if you're adding something backed by an external source, follow this pattern so it's consistent with the rest of the site.

Good reference examples to read alongside this guide:

- **Simple list + map**: `_python/post-office.py` → `_data/post-offices.json` → `_layouts/post-offices.html` → `scripts/po-map.js`
- **Sibling pages sharing one dataset, different filters**: `_python/schools.py` → `_data/schools.json`, rendered by `_layouts/schools.html` (`/cheltenham-schools`) and `_layouts/school-catchment-areas.html` (`/cheltenham-schools/catchment-areas/secondary` and `/primary`)
- **One layout, parameterised by front matter**: `_layouts/school-catchment-areas.html` — same layout, same script, driven by `page.phase`, `page.max_miles` etc. so two pages don't duplicate markup
- **Custom map computation (Voronoi)**: `scripts/school-catchment-map.js`
- **Hand-curated dataset (no fetcher)**: `_data/third-spaces.json`, `_data/parkrun.json`'s sibling pattern but fetched — see below for when to curate instead of fetch

## 1. The Python fetcher (`_python/<name>.py`)

One script, one job: hit a source, normalise it, write one `_data/<name>.json`. Follow the shape of `_python/hotels.py` or `_python/schools.py`:

```python
#!/usr/bin/env python3
"""One-line description of what this fetches and why the refresh cadence
makes sense (e.g. 'refreshed monthly since locations rarely change')."""
import json
import os
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "example.json")

SOURCE_URL = "https://example.gov.uk/api/"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}


def main():
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    items = [...]  # normalise the raw response into plain dicts

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Example Service",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",   # be honest if there isn't one
        "items": items,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
```

Notes:

- Store `generated_at`, `source` and `source_url` (and `licence` where one genuinely applies) in the JSON itself — layouts read these back for the attribution line and JSON-LD `dateModified`/`license` fields, rather than hardcoding them in HTML.
- If a source has no formal open licence (an unofficial feed, a free API's own terms), say so plainly rather than guessing OGL/ODbL. See `_data/sources.json` for the site-wide audit of what's actually confirmed.
- If you need coordinates from an Ordnance Survey National Grid reference (Easting/Northing) rather than lat/lon, convert with `pyproj` — see `_python/schools.py`.
- Add the script to the right `.github/workflows/schedule-*.yml` based on how often the source actually changes: `schedule-monthly.yml` for things like school/parkrun locations, `schedule-daily.yml` for fixtures/prices/weather, `schedule-hourly.yml`/`schedule-minutely.yml` for anything closer to real-time. Don't default to a tight schedule just because you can — match it to the source.

### When to curate instead of fetch

Some things don't have a machine-readable source at all (club directories, third spaces). In that case, hand-write the `_data/<name>.json` directly, in the same shape a fetcher would produce (`generated_at`, `source`, locations with real lat/lon you've looked up yourself), and say so in the page copy — see `_pages/third-spaces.md`'s "Notes" section and `_data/third-spaces.json`. Don't fake a `_python/*.py` script for something that isn't actually fetched.

## 2. The page (`_pages/<name>.md` or `_pages/<group>/<name>.md`)

Front matter shape:

```yaml
---
layout: example              # matches _layouts/example.html
title: "Example Page Title"
seo: "Longer, keyword-rich description for search snippets."
permalink: /cheltenham-example
description: "Shorter description used in the page header and meta tags."
type: "third"                 # controls body theme class — check _includes/header.html
schema: example                # optional — see step 4
---

## Intro Heading

A paragraph or two of real prose introducing the page — layouts render
`{{ content }}` above the data table/map, this isn't just filler.
```

For a genuine sub-page of an existing dataset (a filtered view, not a different source), nest it under a subfolder and give it its own explicit `permalink`, matching `_pages/schools/catchment-areas-secondary.md` or `_pages/food-standards/rated-five.md` — don't rely on the folder path to produce the URL.

If two sibling pages differ only by a filter (primary vs secondary, a food hygiene rating band), share one layout and drive the difference from front matter variables (`phase:`, `max_miles:`, `other_phase_link:` in the schools example) rather than forking the layout.

## 3. The layout (`_layouts/<name>.html`)

Standard skeleton:

```liquid
{% include header.html %}
{% assign data = site.data["example"] %}
<div class="{{page.type}} herobar">
    <div class="{{page.type}}">
        <header class="{{page.type}} header">
            <h1>{{page.title}}</h1>
            <p>{{page.description}}</p>
            <ul>
                <li><a href="/parent-page">&lAarr; Back to Parent</a></li>
            </ul>
        </header>

        {{ content }}

        <h2>Map</h2>
        <div id="example-map" style="height: 480px;" aria-label="Map of examples in Cheltenham"></div>

        <h2>Table</h2>
        <div class="table-scroll">
            <table class="example-table data-table" data-sortable>
                <thead><tr><th scope="col">Name</th></tr></thead>
                <tbody>
                    {% for item in data.items %}
                    <tr><td>{{ item.name }}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <p class="example-attribution"><small>
            Data from <a href="{{ data.source_url }}">{{ data.source }}</a>.
            {% if data.generated_at %}Last updated {{ data.generated_at | date: "%-d %B %Y" }}.{% endif %}
        </small></p>
    </div>
</div>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script id="example-data" type="application/json">{{ data.items | jsonify }}</script>
<script src="/scripts/example-map.js"></script>
{% include footer.html %}
```

- `data-sortable` on a `<table>` is picked up generically by `scripts/table-sort.js` — no per-page JS needed for sorting.
- Pull page-specific values through front matter (`page.phase`, `page.max_miles`) rather than hardcoding them in the layout, if the same layout serves more than one page.

## 4. The map script (`scripts/<name>-map.js`)

Every map on the site follows the same IIFE shape — read the JSON out of a `<script type="application/json">` tag, guard against missing elements/empty data, build a Leaflet map, fit bounds to the markers:

```js
(function () {
    var el = document.getElementById("example-map");
    var dataEl = document.getElementById("example-data");
    if (!el || !dataEl || typeof L === "undefined") return;

    var items = [];
    try {
        items = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        return;
    }
    if (!items.length) return;

    var map = L.map(el);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    var bounds = [];
    items.forEach(function (item) {
        if (item.lat == null || item.lon == null) return;
        var html = "<strong>" + item.name + "</strong>";
        L.marker([item.lat, item.lon]).addTo(map).bindPopup(html);
        bounds.push([item.lat, item.lon]);
    });

    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
})();
```

Reference examples, roughly in order of complexity:

- `scripts/po-map.js` — the simplest version, plain markers
- `scripts/parkrun-map.js` — markers with richer popups
- `scripts/third-spaces-map.js` — markers plus a separate `-centre` JSON script tag for the initial view
- `scripts/school-catchment-map.js` — the complex end: computes a Voronoi diagram client-side with `d3-delaunay` (loaded from unpkg alongside Leaflet), colours cells with golden-angle hue rotation so it scales to any number of points, reads its exclusion radius from a `data-max-miles` attribute on the map `<div>` so one script serves multiple pages

Load Leaflet (and `d3-delaunay` if needed) from unpkg in the layout, pinned to an exact version, before the page's own script tag.

## 5. Structured data (`schema:` front matter + `_includes/schema/<name>.html`)

Add `schema: example` to the page's front matter, then create `_includes/schema/example.html` — `_includes/header.html` picks it up automatically (`{% include schema/{{ page.schema }}.html %}`).

Not every page needs this. Add it when there's a real dataset and it's worth a search engine indexing it as one:

```liquid
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "Example Dataset Name",
  "description": "One sentence describing what this is and where it's from.",
  "url": "{{ page.url | absolute_url }}",
  "dateModified": "{{ site.data['example'].generated_at }}",
  "isAccessibleForFree": true,
  "license": "https://www.nationalarchives.gov.uk/doc/open-government-licence/",
  "creator": { "@type": "Organization", "name": "{{ site.title }}", "url": "{{ site.url }}" },
  "spatialCoverage": { "@type": "Place", "name": "Cheltenham, Gloucestershire, UK" },
  "variableMeasured": ["Name", "Address", "..."]
}
</script>
```

If the page also has a real `## FAQs` section, add a second `FAQPage` block in the same file, copying the FAQ text verbatim so the two stay in sync — see `_includes/schema/inpost.html` or `_includes/schema/schools-catchment-secondary.html`. Don't invent an `FAQPage` block for a page that doesn't actually have FAQ content on it, and don't force a `Dataset` schema onto something too thin or short-lived to be worth indexing as one (a live fixtures page with one upcoming match, say) — `/cheltenham-sports/cheltenham-town-fc` deliberately has none.

## 6. Checklist

- [ ] `_python/<name>.py` fetches and normalises, writes `_data/<name>.json` with `generated_at`/`source`/`source_url`/`licence`
- [ ] Added to the right `schedule-*.yml` workflow for how often the source actually changes
- [ ] `_pages/<name>.md` (or `_pages/<group>/<name>.md`) with full front matter and real intro prose, not just a data dump
- [ ] `_layouts/<name>.html` — map + table + attribution line, reusing an existing layout via front matter variables if it's a filtered sibling of another page
- [ ] `scripts/<name>-map.js` if there's a map, following the standard IIFE shape
- [ ] Linked from the relevant parent/sibling pages, and added to `navigation_header`/`footer_columns` in `_config.yml`
- [ ] `schema:` + `_includes/schema/<name>.html` if the page has a real dataset and/or a real FAQ section worth marking up
- [ ] Checked `_data/sources.json` — add or update the entry for this source, being honest about the licence
