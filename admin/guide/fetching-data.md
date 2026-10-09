---
layout: page
title: "Guide: Fetching Data"
permalink: /admin/guide/fetching-data
description: "How a Python fetcher gets data from a source into _data, and when to curate by hand instead."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

## The Python Fetcher (`_python/<name>.py`)

One script, one job: hit a source, normalise it, write one `_data/<name>.json`. Shared settings live in `_python/config.py` (the site's User-Agent, the town-centre point, the Cheltenham area code, postcode districts, shared API addresses and each dataset's search radius) and shared functions in `_python/helper.py`, so a new fetcher uses those rather than defining its own. Follow the shape of `_python/hotels.py` or `_python/dentists.py`:

```python
#!/usr/bin/env python3
"""One-line description of what this fetches and why the refresh cadence
makes sense (e.g. 'refreshed monthly since locations rarely change')."""
import os
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "example.json")

SOURCE_URL = "https://example.gov.uk/api/"
RADIUS_MILES = config.EXAMPLE_RADIUS_MILES   # add the setting to config.py


def main():
    raw = helper.get(SOURCE_URL).json()   # retries, site User-Agent, 30s timeout
    items = [...]  # normalise the raw response into plain dicts, e.g. with
                   # round(helper.miles_from_centre(lat, lon), 1) for distance

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Example Service",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",   # be honest if there isn't one
        "items": items,
    }

    helper.write_json(OUT, output)
    print(f"Wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
```

What's already shared, so don't write your own:

- `helper.get()` / `helper.post()`: requests with retries, the site's User-Agent (extra headers are added to it) and a default timeout.
- `helper.miles_from_centre()`, `helper.haversine_miles()`, `helper.haversine_km()`: distances, all measured from `config.CENTRE` for "from the town centre".
- `helper.overpass(query)`: OpenStreetMap queries, falling back through `config.OVERPASS_ENDPOINTS` when a server is busy.
- `helper.nomis_rows(dataset, **params)`: rows from a Nomis CSV download.
- `helper.ods_get()`, `helper.ods_address()`, `helper.geocode_postcodes()`: the NHS organisation directory and postcodes.io bulk lookups.
- `helper.write_json(path, payload)`: writes the file (creating its folder) with 2-space indents and unescaped Unicode.

Scripts in `_python/local/` and `_python/pi/` add the parent folder to the import path first: `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`, then `import config` and `import helper`. Offline tests for the shared code are in `_python/tests/`; run them with `.venv/bin/python -m pytest _python/tests` (`pip install -r _python/requirements-dev.txt` once).

Notes:

- Store `source` (the display name, not a URL), `source_url`, and `licence` in the JSON itself. Layouts read these back for the attribution line and JSON-LD `dateModified`/`license` fields, rather than hardcoding them in HTML. `licence` is the display name of a real licence (for example "Open Government Licence v3.0" or "Open Database Licence (ODbL)"). Leave the key out entirely when there is no formal licence; the honest note about it belongs in `_data/sources.json`.
- Freshness: data refreshed daily or less often stores an ISO `generated_at`, shown as "Last updated". Data checked every two hours or more often (the "hourly" workflow and the Pi) stores a fixed `refresh` phrase instead, such as `"every two hours"`, `"hourly"` or `"every 5 minutes"`, shown as "Checked every two hours." That value only changes when the schedule does, so it doesn't cause a commit on every run.
- A fetcher whose output is a plain list, with no room for these fields, gets them from its entry in `_data/sources.json` instead: add `name`, `licence_name` (only for a real licence) and, if needed, `refresh`, and have the layout look the entry up by `id`. See `_layouts/hotels.html`.
- Store any date or time value in the JSON as ISO 8601 — `2026-09-21T21:00` (or `2026-09-21` when there's no meaningful time) — not as a pre-formatted display string, so layouts can sort on it and format it in one consistent way (see the date rule on [Displaying Data](/admin/guide/displaying-data)).
- Format numbers for display in the fetcher, not in Liquid: alongside each raw number, store a `*_display` string with thousands separators (`f"{n:,}"`, and `f"£{n:,}"` for money) — e.g. `amount: 344350` and `display_amount: "£344,350"`. Liquid has no built-in way to add separators, so layouts just print the `_display` field and keep the raw value for sorting (`data-val`). See `_python/house_summary.py`, `_python/land_registry.py` and `_python/station-usage.py`. (Dates are the exception — store those as ISO only, as above, and format them in Liquid.)
- If a source has no formal open licence (an unofficial feed, a free APIs own terms), say so plainly rather than guessing OGL/ODbL. See `_data/sources.json` for the site-wide audit of what's actually confirmed.
- If you need coordinates from an Ordnance Survey National Grid reference (Easting/Northing) rather than lat/lon, convert with `pyproj` — see `_python/schools.py`.
- Add the script to the right `.github/workflows/schedule-*.yml` based on how often the source actually changes: `schedule-weekly.yml` for sources that change through the month (CQC ratings), `schedule-monthly.yml` for things like school/parkrun locations, `schedule-daily.yml` for fixtures/prices/weather, `schedule-hourly.yml`/`schedule-minutely.yml` for anything closer to real-time. Don't default to a tight schedule just because you can — match it to the source.

## When to Curate Instead of Fetch

Some things don't have a machine-readable source at all (club directories, third spaces). In that case, hand-write the `_data/<name>.json` directly, in the same shape a fetcher would produce (`generated_at`, `source`, locations with real lat/lon you've looked up yourself), and say so in the page copy — see `_pages/third-spaces.md`'s "Notes" section and `_data/third-spaces.json`. Don't fake a `_python/*.py` script for something that isn't actually fetched.
