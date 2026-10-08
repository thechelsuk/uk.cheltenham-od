---
layout: page
title: "Guide: Displaying Data"
permalink: /admin/guide/displaying-data
description: "The page, layout, map, chart and structured data that turn a _data file into a page on the site."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

## The Page (`_pages/<name>.md` or `_pages/<group>/<name>.md`)

Front matter shape:

```yaml
---
layout: example              # matches _layouts/example.html
title: "Example Page Title"
seo: "Keyword-rich meta description for search snippets, 160 characters or fewer."
permalink: /cheltenham-example
description: "Description shown in the page header (and used as the meta description if seo is missing)."
type: "third"                 # controls body theme class — check _includes/header.html
schema: example                # optional, see Structured Data below
---

## Intro Heading

A paragraph or two of real prose introducing the page — layouts render
`{{ content }}` above the data table/map, this isn't just filler.
```

**Keep `seo` to 160 characters or fewer.** It is the meta description (`_includes/header.html` uses `seo`, then `description`), and search results cut descriptions off at about 160 characters. Lead with the main keyword and a concrete hook, and count the characters before you finish. This applies to pages, news posts, classifieds and events alike. The admin page lists any entries over the limit.

Every sentence of that intro prose is copy for the site's actual visitors — write it as finished, SEO/GEO-friendly page content, not as a note explaining an implementation or data decision to whoever's reading the diff. "Curated by hand rather than fetched, since OpenStreetMap's coverage of these is patchy" is a fact about the pipeline, not something a visitor searching for a pump track needs to read. If a decision genuinely needs explaining, that's what a code comment, commit message, or PR description is for — never the page body. Before finalising any page's prose, reread it and ask: would this sentence make sense to someone who never saw the commit history?

For a genuine sub-page of an existing dataset (a filtered view, not a different source), nest it under a subfolder and give it its own explicit `permalink`, matching `_pages/schools/catchment-areas-secondary.md` or `_pages/food-standards/rated-five.md` — don't rely on the folder path to produce the URL.

If two sibling pages differ only by a filter (primary vs secondary, a food hygiene rating band), share one layout and drive the difference from front matter variables (`phase:`, `max_miles:`, `other_phase_link:` in the schools example) rather than forking the layout.

## The Layout (`_layouts/<name>.html`)

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
        <div id="example-map" class="map-canvas" aria-label="Map of examples in Cheltenham"></div>

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
            Data from <a href="{{ data.source_url }}">{{ data.source }}</a>{% if data.licence %}, published under the {{ data.licence }}{% endif %}.
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

- Give every map container `class="map-canvas"` (600px, rounded corners) rather than an inline height, and a swatch legend above it `class="map-legend"` with one `<span>` per item. Don't use `class="map"`: it belongs to the pin-link table cells.
- `data-sortable` on a `<table>` is picked up generically by `assets/scripts/table-sort.js` — no per-page JS needed for sorting.
- Any numeric column — counts, prices, distances, years-as-quantities — gets `class="number"` on both the `<th>` and every `<td>` in that column, so it right-aligns instead of sitting left like text (see `assets/style.css`'s `.data-table .number` rule). Applies even to a single-number-column table like a simple `Year` / `Total` pair. Print the fetcher's pre-formatted `*_display` value (`2,418,292`, `£344,350`) in the cell and put the raw number in `data-val` so sorting is numeric.
- A postcode column gets `class="postcode"` on both `<th>` and `<td>` so it doesn't wrap mid-postcode (`.data-table .postcode` is one of a few columns — `.date`, `.type`, `.category`, `.rating-date`, `.listing` — the site already sets to `white-space: nowrap`).
- **Dates and times shown as data are always `YYYY-MM-DD HH:MM`** (24-hour clock), or `YYYY-MM-DD` when there's no meaningful time — e.g. `2026-09-21 21:00`, never `21 Sep 2026`, `Sep 21` or `21/09/2026`. This covers every date/time cell in a table and every date in a map popup. In Liquid use `{{ item.start | date: "%Y-%m-%d %H:%M" }}` (`"%Y-%m-%d"` for date-only), put the raw ISO value from the JSON in `data-val` on the `<td>` so `table-sort.js` sorts chronologically rather than alphabetically, and give the `<th>` and `<td>`s `class="date"` so the value doesn't wrap. The prose "Last updated" line in the attribution `<small>` is a sentence rather than a data value and stays in the skeleton's `%-d %B %Y` form. See `_layouts/roadworks.html` for a worked example.
- Pull page-specific values through front matter (`page.phase`, `page.max_miles`) rather than hardcoding them in the layout, if the same layout serves more than one page.

## The Map Script (`assets/scripts/<name>-map.js`)

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

Dates in a popup follow the same `YYYY-MM-DD HH:MM` rule as the table (see The Layout). Don't use `toLocaleString`/`toLocaleDateString` — they produce `21 Sept 2026` and vary by browser. Reformat the ISO string from the JSON instead, e.g. `iso.replace("T", " ")` for `2026-09-21T21:00` (see `assets/scripts/roadworks-map.js`).

Load Leaflet (and `d3-delaunay` if needed) from unpkg in the layout, pinned to an exact version, before the page's own script tag.

### Charts

Charts use Chart.js. Load it with `{% include chartjs.html %}` rather than a script tag of your own. The include pins the Chart.js version and adds `assets/scripts/chart-defaults.js`, which:

- sets the font, text colour and gridline colour from the site's CSS variables, and redraws charts when the light/dark toggle changes
- colours any series that has no colour of its own from a fixed, colour-blind-safe palette in both themes. Places keep one colour everywhere (Cheltenham, South West, England, Gloucestershire), and other series take the remaining colours in order
- makes each chart fill its wrapper instead of keeping an aspect ratio

Wrap every canvas in the standard 400px container, and don't add a `height` attribute or inline style:

```html
<div class="chart-canvas"><canvas id="example-chart" aria-label="Line chart of …"></canvas></div>
{% include chartjs.html %}
<script src="/assets/scripts/example-chart.js"></script>
```

Leave `borderColor`/`backgroundColor` off datasets so the palette applies. Only set them when a colour carries meaning, as with the fatal/serious/slight severity colours on the road collisions page.

## Structured Data (`schema:` Front Matter and `_includes/schema/<name>.html`)

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

**FAQs don't need a schema block.** Write them in the standard shape and `_plugins/faq_schema.rb` generates the `FAQPage` JSON-LD from them at build time: an `<h2>` reading exactly "Frequently Asked Questions", then each question as an `<h3>`, with its answer as a `<ul>` (one `<li>` per point, so a longer answer is several bullets). Because the structured data is read from the visible text, the two can't drift apart, and FAQs that use Liquid values (like the ward pages) work too. Put the FAQs at the bottom of the page, after the data: in the page's own layout when it has one, and in the Markdown only for pages on the shared `page` layout (such as recycling and the newsletter). In a layout:

```html
<h2>Frequently Asked Questions</h2>

<h3>Where Does the Data Come From?</h3>
<ul>
    <li>…</li>
</ul>
```

In a Markdown page:

```markdown
## Frequently Asked Questions

### How Often Are Prices Updated?

- Checked hourly…
```

Don't write an `FAQPage` block by hand; the plugin skips any page that already has one and logs a warning. Don't force a `Dataset` schema onto something too thin or short-lived to be worth indexing as one (a live fixtures page with one upcoming match, say) — `/cheltenham-sports/cheltenham-town-fc` deliberately has none.

## Map Pins in Table Cells

Examples:

```html
<td class="map">{% include pin.html lat=s.latitude lng=s.longitude label=s.name %}</td>
<td class="map">{% include pin.html lat=p.lat lng=p.lng label=p.name %}</td>
```
