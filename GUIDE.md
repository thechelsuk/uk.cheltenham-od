# Adding a New Data Page

This is the standard shape of a data page on Cheltenham Open Data. It's not a hard rule for every page on the site — a handful of pages are pure curated Markdown (`_pages/sports.md`, `_pages/third-spaces.md`) with no fetcher behind them — but if you're adding something backed by an external source, follow this pattern so it's consistent with the rest of the site.

Good reference examples to read alongside this guide:

- **Simple list + map**: `_python/post-office.py` → `_data/post-offices.json` → `_layouts/post-offices.html` → `assets/scripts/po-map.js`
- **Sibling pages sharing one dataset, different filters**: `_python/schools.py` → `_data/schools.json`, rendered by `_layouts/schools.html` (`/cheltenham-schools`) and `_layouts/school-catchment-areas.html` (`/cheltenham-schools/catchment-areas/secondary` and `/primary`)
- **One layout, parameterised by front matter**: `_layouts/school-catchment-areas.html` — same layout, same script, driven by `page.phase`, `page.max_miles` etc. so two pages don't duplicate markup
- **Custom map computation (Voronoi)**: `assets/scripts/school-catchment-map.js`
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
- Store any date or time value in the JSON as ISO 8601 — `2026-09-21T21:00` (or `2026-09-21` when there's no meaningful time) — not as a pre-formatted display string, so layouts can sort on it and format it in one consistent way (see the date rule in section 3).
- Format numbers for display in the fetcher, not in Liquid: alongside each raw number, store a `*_display` string with thousands separators (`f"{n:,}"`, and `f"£{n:,}"` for money) — e.g. `amount: 344350` and `display_amount: "£344,350"`. Liquid has no built-in way to add separators, so layouts just print the `_display` field and keep the raw value for sorting (`data-val`). See `_python/house_summary.py`, `_python/land_registry.py` and `_python/station-usage.py`. (Dates are the exception — store those as ISO only, as above, and format them in Liquid.)
- If a source has no formal open licence (an unofficial feed, a free APIs own terms), say so plainly rather than guessing OGL/ODbL. See `_data/sources.json` for the site-wide audit of what's actually confirmed.
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

Every sentence of that intro prose is copy for the site's actual visitors — write it as finished, SEO/GEO-friendly page content, not as a note explaining an implementation or data decision to whoever's reading the diff. "Curated by hand rather than fetched, since OpenStreetMap's coverage of these is patchy" is a fact about the pipeline, not something a visitor searching for a pump track needs to read. If a decision genuinely needs explaining, that's what a code comment, commit message, or PR description is for — never the page body. Before finalising any page's prose, reread it and ask: would this sentence make sense to someone who never saw the commit history?

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
<script src="/assets/scripts/example-map.js"></script>
{% include footer.html %}
```

- `data-sortable` on a `<table>` is picked up generically by `assets/scripts/table-sort.js` — no per-page JS needed for sorting.
- Any numeric column — counts, prices, distances, years-as-quantities — gets `class="number"` on both the `<th>` and every `<td>` in that column, so it right-aligns instead of sitting left like text (see `assets/style.css`'s `.data-table .number` rule). Applies even to a single-number-column table like a simple `Year` / `Total` pair. Print the fetcher's pre-formatted `*_display` value (`2,418,292`, `£344,350`) in the cell and put the raw number in `data-val` so sorting is numeric.
- A postcode column gets `class="postcode"` on both `<th>` and `<td>` so it doesn't wrap mid-postcode (`.data-table .postcode` is one of a few columns — `.date`, `.type`, `.category`, `.rating-date`, `.listing` — the site already sets to `white-space: nowrap`).
- **Dates and times shown as data are always `YYYY-MM-DD HH:MM`** (24-hour clock), or `YYYY-MM-DD` when there's no meaningful time — e.g. `2026-09-21 21:00`, never `21 Sep 2026`, `Sep 21` or `21/09/2026`. This covers every date/time cell in a table and every date in a map popup. In Liquid use `{{ item.start | date: "%Y-%m-%d %H:%M" }}` (`"%Y-%m-%d"` for date-only), put the raw ISO value from the JSON in `data-val` on the `<td>` so `table-sort.js` sorts chronologically rather than alphabetically, and give the `<th>` and `<td>`s `class="date"` so the value doesn't wrap. The prose "Last updated" line in the attribution `<small>` is a sentence rather than a data value and stays in the skeleton's `%-d %B %Y` form. See `_layouts/roadworks.html` for a worked example.
- Pull page-specific values through front matter (`page.phase`, `page.max_miles`) rather than hardcoding them in the layout, if the same layout serves more than one page.

## 4. The map script (`assets/scripts/<name>-map.js`)

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

- `assets/scripts/po-map.js` — the simplest version, plain markers
- `assets/scripts/parkrun-map.js` — markers with richer popups
- `assets/scripts/third-spaces-map.js` — markers plus a separate `-centre` JSON script tag for the initial view
- `assets/scripts/school-catchment-map.js` — the complex end: computes a Voronoi diagram client-side with `d3-delaunay` (loaded from unpkg alongside Leaflet), colours cells with golden-angle hue rotation so it scales to any number of points, reads its exclusion radius from a `data-max-miles` attribute on the map `<div>` so one script serves multiple pages

Dates in a popup follow the same `YYYY-MM-DD HH:MM` rule as the table (section 3). Don't use `toLocaleString`/`toLocaleDateString` — they produce `21 Sept 2026` and vary by browser. Reformat the ISO string from the JSON instead, e.g. `iso.replace("T", " ")` for `2026-09-21T21:00` (see `assets/scripts/roadworks-map.js`).

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
- [ ] `_pages/<name>.md` (or `_pages/<group>/<name>.md`) with full front matter and real intro prose, not just a data dump — reread every sentence as a visitor would: no implementation/data-decision notes ("hand-curated because OSM coverage is patchy") leaking into published copy
- [ ] `_layouts/<name>.html` — map + table + attribution line, reusing an existing layout via front matter variables if it's a filtered sibling of another page
- [ ] Every numeric table column has `class="number"` on its `<th>` and `<td>`s (right-aligned), and any postcode column has `class="postcode"` (no mid-postcode wrapping)
- [ ] Every date/time cell in a table and every date in a map popup is `YYYY-MM-DD HH:MM` (or `YYYY-MM-DD` with no time), with the ISO value in `data-val` and `class="date"` on the `<th>`/`<td>`s
- [ ] `assets/scripts/<name>-map.js` if there's a map, following the standard IIFE shape
- [ ] Linked from the relevant parent/sibling pages
- [ ] Decided whether this is a headline main-menu item or a sub-page of an existing one — if it's a genuine new topic, add it to `navigation_header`/`footer_columns` in `_config.yml`; if it's a filtered view or a natural sub-topic of an existing page (like `/cheltenham-employment-history` under `/about-cheltenham`, or `/cheltenham-listed-buildings` under `/about-cheltenham`), link it inline from the parent page's prose instead and leave the nav/footer alone
- [ ] If the page went into `navigation_header`, **asked** whether to add it to its category's row in the sponsor categories table (`_layouts/sponsor.html`, the `/sponsor` page) — don't edit that table without an answer, since it's sales copy the site owner words themselves. The **Pages** count in that table is calculated from `navigation_header`, so it updates itself; the **Pages included** text is hardcoded per row, is kept deliberately loose (short names, only some sub-pages in an `(incl. …)` note) and will not change on its own, so it goes stale unless the question is asked. If the answer is yes, add the page's short name in nav order (e.g. `Roadworks`); for a child of an existing entry, only add it to that entry's `(incl. …)` note if it's worth a sponsor knowing about. A page linked inline from a parent (no nav entry) doesn't need the question.
- [ ] `schema:` + `_includes/schema/<name>.html` if the page has a real dataset and/or a real FAQ section worth marking up
- [ ] Checked `_data/sources.json` — add or update the entry for this source, being honest about the licence
- [ ] Asked whether a `_posts/<date>-<name>-added.md` news post announcing the new page is warranted — follow the shape of recent posts like `_posts/2026-09-09-broadband-internet-added.md` (intro paragraph linking the new page, a short "what it shows" summary, an FAQs section). Not every page needs one (a minor filter/sub-page usually doesn't), but a genuinely new dataset or page usually does.

## Maps

Examples

```html
<td class="map">{% include pin.html lat=s.latitude lng=s.longitude label=s.name %}</td>
<td class="map">{% include pin.html lat=p.lat lng=p.lng label=p.name %}</td>
```
