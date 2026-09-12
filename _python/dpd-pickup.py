"""Fetch DPD Pickup drop-off/collection points in Cheltenham from DPD's own
public pickup-location API (the same one powering their pickup point finder
at https://pickup.dpd.co.uk — no API key required), and write normalised
JSON to Jekyll's _data dir.

Source: https://apis.pickup.dpd.co.uk/v1/pickuplocation
"""

import datetime

import helper

API_URL = "https://apis.pickup.dpd.co.uk/v1/pickuplocation"

SEARCH_POSTCODE = "GL501NB"
SEARCH_PAGE_SIZE = 100

# Cheltenham's own postcode districts. GL54 (Andoversford etc.) and GL1-GL4/
# GL19/GL20 (Gloucester/Tewkesbury) show up within the search radius but
# aren't Cheltenham itself, so are excluded by district rather than by a
# free-text town match.
CHELTENHAM_POSTCODE_DISTRICTS = {"GL50", "GL51", "GL52", "GL53"}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

ACRONYMS = {"UK", "NCP", "MFG", "BP"}


def fetch_points():
    resp = helper.request_with_retry(
        "GET", API_URL,
        params={
            "address": SEARCH_POSTCODE,
            "searchPageSize": SEARCH_PAGE_SIZE,
            "businessUnit": 1,
            "dropoff": "true",
        },
        timeout=20,
    )
    return resp.json().get("results", [])


def postcode_district(postcode):
    return "".join(postcode.split(" ")[:-1]) or postcode.split(" ")[0]


def day_span(windows):
    """Combine a day's open windows into one 'HH:MM-HH:MM' span, or 'Closed'."""
    if not windows:
        return "Closed"
    windows = sorted(windows, key=lambda w: w["pickupLocationOpenWindowStartTime"])
    start = windows[0]["pickupLocationOpenWindowStartTime"]
    end = windows[-1]["pickupLocationOpenWindowEndTime"]
    return f"{start}-{end}"


def summarise_hours(open_windows):
    """Collapse the week's open windows into compressed day ranges, e.g.
    'Mon-Sat 08:30-18:00, Sun 10:30-16:30'. Returns (summary, is_247)."""
    by_day = {d: [] for d in range(1, 8)}
    for w in open_windows or []:
        by_day[w["pickupLocationOpenWindowDay"]].append(w)

    spans = [day_span(by_day[d]) for d in range(1, 8)]
    is_247 = all(span == "00:01-23:59" for span in spans)

    groups = []
    start = 0
    for i in range(1, len(spans) + 1):
        if i == len(spans) or spans[i] != spans[start]:
            groups.append((start, i - 1, spans[start]))
            start = i

    parts = []
    for start_idx, end_idx, span in groups:
        label = DAY_ABBR[start_idx + 1] if start_idx == end_idx else f"{DAY_ABBR[start_idx + 1]}-{DAY_ABBR[end_idx + 1]}"
        parts.append(f"{label} {span}")

    return ", ".join(parts), is_247


def clean_point(result):
    pl = result["pickupLocation"]
    address = pl["address"]
    summary, is_247 = summarise_hours(pl["pickupLocationAvailability"]["pickupLocationOpenWindow"])
    point = pl.get("addressPoint") or {}
    return {
        "id":               pl["pickupLocationCode"],
        "name":             address.get("organisation") or "DPD Pickup Point",
        "street":           helper.clean_name(address.get("street") or "", ACRONYMS),
        "postcode":         address.get("postcode") or "",
        "lat":              point.get("latitude"),
        "lon":              point.get("longitude"),
        "distance_miles":   round(result.get("distance") or 0, 1),
        "is_247":           is_247,
        "opening_hours":    summary,
        "is_post_office":   "post office" in (address.get("organisation") or "").lower(),
    }


if __name__ == "__main__":
    out_path = helper.repo_root() / "_data" / "dpd-pickup-points.json"

    print("Fetching DPD pickup points...")
    results = fetch_points()
    print(f"  {len(results)} points within search radius")

    local = [
        r for r in results
        if postcode_district(r["pickupLocation"]["address"]["postcode"]) in CHELTENHAM_POSTCODE_DISTRICTS
    ]
    print(f"  {len(local)} in Cheltenham (GL50-GL53)")

    points = sorted((clean_point(r) for r in local), key=lambda p: p["distance_miles"])

    payload = {
        "updated":     helper.updated_timestamp(),
        "updated_iso": datetime.date.today().isoformat(),
        "source":      "https://pickup.dpd.co.uk/",
        "count":       len(points),
        "points":      points,
    }

    helper.write_json(out_path, payload)
    print(f"Wrote {len(points)} pickup points to {out_path}")
