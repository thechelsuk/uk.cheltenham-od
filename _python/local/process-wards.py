#!/usr/bin/env python3
"""Build one ward profile from data the site already holds, and write it to
_data/wards/<slug>.json.

Nothing is fetched. A ward is a polygon, so every dataset that carries a
latitude/longitude is placed with a point-in-polygon test, and every dataset
that only carries a postcode (house prices, GPs, pharmacies) is placed through
the postcode-to-ward lookup. Crime is counted from the street-level records in
_data/crime/, house prices from the Land Registry files, and each amenity type
gets the ones inside the ward plus the nearest few outside it.

Needs two local-only files from _data-sources/ (gitignored): the postcode
lookup (gloucestershire-postcodes.csv) and the postcode-to-ward cache
(_ward-cache.json). Re-run after the crime or other source data refreshes:

    python3 _python/wards.py                 # every ward listed in WARDS
    python3 _python/wards.py "St Mark's"     # just one

Also writes _data/wards/index.json, the one-line-per-ward summary behind the
Cheltenham Wards page and its map.
"""
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data"
SOURCES = ROOT / "_data-sources"
OUT_DIR = DATA / "wards"

# Cheltenham's 20 wards, spelled as in _data/broadband-map.json (which also holds
# the neighbouring districts' wards). Each needs a page under _pages/about-info/wards/.
WARDS = [
    "All Saints", "Battledown", "Benhall, the Reddings & Fiddler's Green", "Charlton Kings", "Charlton Park",
    "College", "Hesters Way", "Lansdown", "Leckhampton", "Oakley", "Park", "Pittville", "Prestbury",
    "Springbank", "St Mark's", "St Paul's", "St Peter's", "Swindon Village", "Up Hatherley", "Warden Hill",
]
TOWN_CENTRE = (51.8994, -2.0783)   # lat, lon, used to say which side of town a ward is on

NEAREST = 5          # how many of the nearest to show for each amenity type
LISTED_ENOUGH = 3    # a ward with this many of something shows only its own
NEARBY_MAX_MILES = 3  # and never pads with anything further away than this
CRIME_MONTHS = 12    # length of the "recent" crime window

CRIME_LABELS = {
    "anti-social-behaviour": "Anti-social behaviour",
    "bicycle-theft": "Bicycle theft",
    "burglary": "Burglary",
    "criminal-damage-arson": "Criminal damage and arson",
    "drugs": "Drugs",
    "other-crime": "Other crime",
    "other-theft": "Other theft",
    "possession-of-weapons": "Possession of weapons",
    "public-order": "Public order",
    "robbery": "Robbery",
    "shoplifting": "Shoplifting",
    "theft-from-the-person": "Theft from the person",
    "vehicle-crime": "Vehicle crime",
    "violent-crime": "Violence and sexual offences",
}

PROPERTY_TYPES = {"D": "Detached", "S": "Semi-detached", "T": "Terraced", "F": "Flat or maisonette", "O": "Other"}


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_polygons(lon, lat, polygons):
    """polygons: list of polygons, each a list of rings (outer first, then holes)."""
    for rings in polygons:
        if in_ring(lon, lat, rings[0]) and not any(in_ring(lon, lat, h) for h in rings[1:]):
            return True
    return False


def polygons_of(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    return geometry["coordinates"]


def centroid_and_area(polygons):
    """Area-weighted centroid (lon, lat) and area in km2 of the outer rings."""
    lat0 = polygons[0][0][0][1]
    kx = 111.32 * math.cos(math.radians(lat0))
    ky = 110.57
    total = cx = cy = 0.0
    for rings in polygons:
        ring = rings[0]
        for i in range(len(ring) - 1):
            x0, y0 = ring[i][0] * kx, ring[i][1] * ky
            x1, y1 = ring[i + 1][0] * kx, ring[i + 1][1] * ky
            cross = x0 * y1 - x1 * y0
            total += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
    area = total / 2
    return (cx / (6 * area) / kx, cy / (6 * area) / ky), abs(area)


def position_from_centre(lat, lon):
    """Compass side of town as an adjective ('western'), or 'central' near the middle."""
    miles = haversine_miles(TOWN_CENTRE[0], TOWN_CENTRE[1], lat, lon)
    if miles < 0.6:
        return "central", round(miles, 1)
    dy = lat - TOWN_CENTRE[0]
    dx = (lon - TOWN_CENTRE[1]) * math.cos(math.radians(lat))
    bearing = (math.degrees(math.atan2(dx, dy)) + 360) % 360
    names = ["northern", "north-eastern", "eastern", "south-eastern", "southern", "south-western", "western", "north-western"]
    return names[int((bearing + 22.5) // 45) % 8], round(miles, 1)


def touches(polys_a, polys_b, tolerance_miles=0.03):
    pts_b = [pt for rings in polys_b for pt in rings[0]]
    for rings in polys_a:
        for lon, lat in rings[0]:
            for blon, blat in pts_b:
                if haversine_miles(lat, lon, blat, blon) < tolerance_miles:
                    return True
    return False


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

@lru_cache(maxsize=None)
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_postcodes():
    """postcode -> (lat, lon) from the local postcode lookup."""
    lookup = {}
    with open(SOURCES / "gloucestershire-postcodes.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                lookup[row["Postcode"]] = (float(row["Latitude"]), float(row["Longitude"]))
            except ValueError:
                continue
    return lookup


def postcode_in(text):
    m = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", text.upper())
    return f"{m.group(1)} {m.group(2)}" if m else ""


def money(n):
    return f"£{n:,.0f}"


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


# --------------------------------------------------------------------------
# Amenity sources. Each returns a list of dicts with name, lat, lon and
# optionally address, postcode, detail, url.
# --------------------------------------------------------------------------

def src_toilets():
    for t in load_json(DATA / "toilets.json"):
        bits = []
        if t.get("accessible"):
            bits.append("Accessible")
        if t.get("payment_details"):
            bits.append(t["payment_details"])
        elif t.get("no_payment"):
            bits.append("Free")
        yield {"name": t["name"], "lat": t["latitude"], "lon": t["longitude"],
               "detail": ", ".join(bits), "url": t.get("maps_url", "")}


def src_dentists():
    for p in load_json(DATA / "dentists.json")["practices"]:
        yield {"name": p["name"], "address": p["address"], "postcode": p["postcode"], "lat": p["lat"], "lon": p["lon"]}


def src_opticians():
    for p in load_json(DATA / "opticians.json")["opticians"]:
        yield {"name": p["name"], "address": p["address"], "postcode": p["postcode"], "lat": p["lat"], "lon": p["lon"]}


def src_hospitals():
    for h in load_json(DATA / "nhs-hospitals.json")["hospitals"]:
        yield {"name": h["name"], "address": h["address"], "postcode": h["postcode"], "lat": h["lat"], "lon": h["lon"],
               "detail": "A&E" if h.get("has_ae") else ""}


def src_schools():
    for s in load_json(DATA / "schools.json"):
        yield {"name": s["name"], "address": s["address"], "postcode": s["postcode"], "lat": s["lat"], "lon": s["lon"],
               "detail": ", ".join(b for b in (s["phase"], s["type"]) if b and b != "Not applicable")}


def src_play_areas():
    for p in load_json(DATA / "play-areas.json")["play_areas"]:
        yield {"name": p["name"], "lat": p["lat"], "lon": p["lon"]}


def src_parks():
    seen = set()
    kinds = {"Parks, Gardens and open space", "Open Space Land and Allottments"}
    skip = re.compile(r"pavili?on|depot|entrance", re.I)
    for a in load_json(DATA / "council-land-and-assets.json")["items"]:
        if a["holding_type"] not in kinds or a.get("lat") is None:
            continue
        # The register gives an address, not a name: drop the town, county and postcode.
        name = re.sub(r",?\s*Cheltenham(,?\s*Gloucestershire)?(,?\s*[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})?\s*$", "",
                      a["address"].split(",")[0].strip() if "," in a["address"] else a["address"]).strip()
        if skip.search(name) or name in seen:
            continue
        seen.add(name)
        yield {"name": name, "lat": a["lat"], "lon": a["lon"],
               "detail": a["holding_type"].replace("Allottments", "Allotments")}


def src_parkrun():
    for p in load_json(DATA / "parkrun.json")["events"]:
        yield {"name": p["name"], "lat": p["lat"], "lon": p["lon"], "detail": p["distance"], "url": p["event_page"]}


def src_post_offices():
    for p in load_json(DATA / "post-offices.json"):
        yield {"name": p["name"], "address": p["address"], "lat": p["lat"], "lon": p["lon"]}


def src_car_parks():
    for p in load_json(DATA / "car-parks.json")["car_parks"]:
        yield {"name": p["name"], "lat": p["lat"], "lon": p["lon"], "detail": p.get("operator") or ""}


def src_ev():
    for s in load_json(DATA / "ev-charging.json")["stations"]:
        yield {"name": s["name"], "address": s.get("address") or "", "postcode": s.get("postcode") or "",
               "lat": s["latitude"], "lon": s["longitude"],
               "detail": f"{s['num_points']} points, up to {s['max_power_kw']} kW" if s.get("max_power_kw") else ""}


def src_fuel():
    for s in load_json(DATA / "fuel-prices.json")["stations"]:
        yield {"name": s["name"], "address": s["address"], "postcode": s["postcode"], "lat": s["lat"], "lon": s["lon"]}


def src_parcels():
    for p in load_json(DATA / "inpost-lockers.json")["lockers"]:
        yield {"name": p["name"], "address": p["street"], "postcode": p["postcode"], "lat": p["lat"], "lon": p["lon"],
               "detail": "InPost locker"}
    for p in load_json(DATA / "dpd-pickup-points.json")["points"]:
        yield {"name": p["name"], "address": p["street"], "postcode": p["postcode"], "lat": p["lat"], "lon": p["lon"],
               "detail": "DPD Pickup"}


def src_foodbanks():
    for f in load_json(DATA / "foodbank.json")["foodbanks"]:
        yield {"name": f["display_name"], "address": f["address"], "postcode": f["postcode"], "lat": f["lat"], "lon": f["lon"],
               "url": f.get("homepage", "")}


def src_third_spaces():
    for t in load_json(DATA / "third-spaces.json")["locations"]:
        yield {"name": t["name"], "address": t["address"], "lat": t["latitude"], "lon": t["longitude"], "url": t.get("website", "")}


def src_sights():
    for p in load_json(DATA / "points_of_interest.json"):
        if p["category"] in ("Hill", "Plaque"):
            continue
        yield {"name": p["name"], "lat": p["lat"], "lon": p["lng"], "detail": p["category"]}


def src_listed():
    for b in load_json(DATA / "listed-buildings.json")["buildings"]:
        yield {"name": b["name"], "lat": b["lat"], "lon": b["lon"], "detail": f"Grade {b['grade']}", "url": b["hyperlink"]}


def src_food_venues():
    for v in load_json(DATA / "food-standards.json"):
        if v.get("latitude") is None:
            continue
        if v["type"] in ("Restaurant/Cafe/Canteen", "Pub/bar/nightclub", "Takeaway/sandwich shop", "Other catering premises"):
            rating = v["rating"] if v["rating"] else "n/a"
            yield {"name": v["name"], "address": v["address"], "postcode": v["postcode"],
                   "lat": v["latitude"], "lon": v["longitude"],
                   "type": v["type"], "detail": f"Rating {rating}" if rating.isdigit() else rating}


# (id, group, label, source, mode, limit). mode "nearest" shows everything in the
# ward plus the nearest few outside; "in_ward" shows only what is inside.
SERVICES = [
    ("gp", "Health", "GP practices", None, "nearest"),      # parsed from the GP page
    ("pharmacy", "Health", "Pharmacies", None, "nearest"),  # parsed from the GP page
    ("dentist", "Health", "Dentists", src_dentists, "nearest"),
    ("optician", "Health", "Opticians", src_opticians, "nearest"),
    ("hospital", "Health", "Hospitals", src_hospitals, "nearest"),
    ("school", "Schools", "Schools", src_schools, "nearest"),
    ("park", "Parks and Play", "Parks and open spaces", src_parks, "nearest"),
    ("play", "Parks and Play", "Play areas", src_play_areas, "nearest"),
    ("parkrun", "Parks and Play", "Running events", src_parkrun, "nearest"),
    ("toilet", "Everyday Services", "Public toilets", src_toilets, "nearest"),
    ("post", "Everyday Services", "Post offices", src_post_offices, "nearest"),
    ("parcel", "Everyday Services", "Parcel pick-up points", src_parcels, "nearest"),
    ("foodbank", "Everyday Services", "Food banks", src_foodbanks, "nearest"),
    ("space", "Everyday Services", "Community spaces", src_third_spaces, "nearest"),
    ("carpark", "Getting Around", "Car parks", src_car_parks, "nearest"),
    ("ev", "Getting Around", "EV charging", src_ev, "nearest"),
    ("fuel", "Getting Around", "Fuel stations", src_fuel, "nearest"),
    ("venue", "Food and Drink", "Pubs, cafes and takeaways", src_food_venues, "in_ward"),
    ("sight", "Heritage", "Places to visit", src_sights, "nearest"),
    ("listed", "Heritage", "Listed buildings", src_listed, "in_ward"),
]


def parse_gp_page(postcodes):
    """GPs and pharmacies only exist as Markdown on the GP page, so read them back
    from it and place each one by postcode."""
    text = (ROOT / "_pages/community-support/gp-pharmacy.md").read_text(encoding="utf-8")
    sections = {"GP Practices": [], "Pharmacies": []}
    section = None
    entry = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            entry = None
        elif line.startswith("### ") and section in sections:
            entry = {"name": line[4:].strip()}
            sections[section].append(entry)
        elif entry is not None and line.startswith("- Address:"):
            m = re.match(r"- Address: \[(.*?)\]\(", line)
            if m:
                entry["address"] = m.group(1)
                entry["postcode"] = postcode_in(m.group(1))
        elif entry is not None and line.startswith("- Phone:"):
            m = re.match(r"- Phone: \[(.*?)\]\(", line)
            if m:
                entry["detail"] = m.group(1)
    result = {}
    for key, name in (("gp", "GP Practices"), ("pharmacy", "Pharmacies")):
        items = []
        for e in sections[name]:
            pc = e.get("postcode", "")
            if pc not in postcodes:
                continue
            e["lat"], e["lon"] = postcodes[pc]
            items.append(e)
        result[key] = items
    return result


# --------------------------------------------------------------------------
# Per-ward measures
# --------------------------------------------------------------------------

def build_services(polygons, centre, postcodes):
    gp_page = parse_gp_page(postcodes)
    services = []
    for sid, group, label, source, mode in SERVICES:
        raw = gp_page[sid] if source is None else list(source())
        items = []
        for r in raw:
            lat, lon = r.get("lat"), r.get("lon")
            if lat is None or lon is None:
                continue
            item = {k: r[k] for k in ("name", "address", "postcode", "detail", "type", "url") if r.get(k)}
            item["lat"] = round(lat, 6)
            item["lon"] = round(lon, 6)
            item["in_ward"] = in_polygons(lon, lat, polygons)
            item["distance_miles"] = round(haversine_miles(centre[1], centre[0], lat, lon), 2)
            items.append(item)
        items.sort(key=lambda i: (i["distance_miles"], i["name"]))
        inside = [i for i in items if i["in_ward"]]
        if mode == "nearest" and len(inside) < LISTED_ENOUGH:
            outside = [i for i in items if not i["in_ward"] and i["distance_miles"] <= NEARBY_MAX_MILES][:NEAREST]
            shown = sorted(inside + outside, key=lambda i: (i["distance_miles"], i["name"]))
        else:
            shown = inside
        services.append({"id": sid, "group": group, "label": label, "mode": mode,
                         "in_ward": len(inside), "items": shown})
    return services


def build_crime(polygons):
    index = load_json(DATA / "crime" / "index.json")
    by_month = defaultdict(Counter)       # month -> category -> count
    streets = defaultdict(Counter)        # month -> street -> count
    seen = set()
    for month in index["months"]:
        for hood in month["neighbourhoods"]:
            path = DATA / "crime" / hood["file"]
            if not path.exists():
                continue
            for c in load_json(path)["crimes"]:
                if c["id"] in seen:
                    continue
                seen.add(c["id"])
                loc = c["location"]
                if not in_polygons(float(loc["longitude"]), float(loc["latitude"]), polygons):
                    continue
                by_month[month["month"]][c["category"]] += 1
                street = re.sub(r"^On or near ", "", loc["street"]["name"]).strip()
                if street and street != "No Location":
                    streets[month["month"]][street] += 1
    # Only months the police have published in full count: a month whose town-wide
    # total is under half the usual is a gap in the feed, not a quiet month.
    town = {m["month"]: sum(n["crime_count"] for n in m["neighbourhoods"]) for m in index["months"]}
    usual = statistics.median(town.values())
    published = sorted(m for m, n in town.items() if n >= usual / 2)
    window = published[-CRIME_MONTHS:]
    previous = published[-2 * CRIME_MONTHS:-CRIME_MONTHS]

    def total(months, cat=None):
        return sum(v for m in months for k, v in by_month[m].items() if cat is None or k == cat)

    categories = sorted({k for m in window + previous for k in by_month[m]})
    cats = []
    for k in categories:
        n, p = total(window, k), total(previous, k)
        cats.append({"category": k, "label": CRIME_LABELS.get(k, k.replace("-", " ").capitalize()),
                     "count": n, "previous": p if len(previous) == CRIME_MONTHS else None})
    cats.sort(key=lambda c: (-c["count"], c["label"]))
    all_total = total(window)
    for c in cats:
        c["share"] = round(100 * c["count"] / all_total, 1) if all_total else 0
    top = Counter()
    for m in window:
        top.update(streets[m])
    return {
        "first_month": window[0], "last_month": window[-1], "months": len(window),
        "total": all_total,
        "previous_total": total(previous) if len(previous) == CRIME_MONTHS else None,
        "change_pct": round(100 * (all_total - total(previous)) / total(previous), 1)
        if len(previous) == CRIME_MONTHS and total(previous) else None,
        "per_month": round(all_total / len(window), 1),
        "by_category": cats,
        "by_month": [{"month": m, "count": total([m])} for m in published],
        "top_streets": [{"street": s, "count": n} for s, n in top.most_common(10)],
    }


def build_house_prices(ward_postcodes):
    """Recent sales from the Land Registry file the site already fetches, extended
    back to 1995 with the full-history CSV when it is available locally."""
    recent = load_json(DATA / "cheltenham-house-prices.json")["transactions"]
    sales = []
    cutoff = min(t["date"] for t in recent)
    for t in recent:
        if t["postcode"] in ward_postcodes:
            sales.append((t["date"], t["amount"], t["property_type"].replace("Flat-maisonette", "Flat or maisonette"),
                          t["new_build"]))
    history = SOURCES / "pp-cheltenham-1995-2022.csv"
    if history.exists():
        with open(history, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                d = row["date"][:10]
                if row["postcode"] in ward_postcodes and d < cutoff:
                    sales.append((d, int(row["price"]), PROPERTY_TYPES.get(row["property_type"], "Other"),
                                  row["new_build"] == "Y"))
    sales.sort()
    by_year = defaultdict(list)
    for d, amount, _, _ in sales:
        by_year[d[:4]].append(amount)
    years = [{"year": y, "sales": len(v), "median": int(statistics.median(v)), "median_display": money(statistics.median(v))}
             for y, v in sorted(by_year.items())]

    latest = max(d for d, *_ in sales)
    start = f"{int(latest[:4]) - 1}{latest[4:]}"
    last12 = [s for s in sales if s[0] > start] or sales[-1:]
    types = defaultdict(list)
    for d, amount, kind, _ in last12:
        types[kind].append(amount)
    by_type = [{"type": k, "sales": len(v), "median": int(statistics.median(v)), "median_display": money(statistics.median(v)),
                "min_display": money(min(v)), "max_display": money(max(v))}
               for k, v in sorted(types.items(), key=lambda kv: -len(kv[1]))]
    amounts = [s[1] for s in last12]
    return {
        "latest_sale": latest,
        "first_year": years[0]["year"],
        "sales_total": len(sales),
        "sales_total_display": f"{len(sales):,}",
        "last12_sales": len(last12),
        "last12_median": int(statistics.median(amounts)),
        "last12_median_display": money(statistics.median(amounts)),
        "by_year": years,
        "by_type": by_type,
    }


def build_local_issues(polygons):
    def inside(items, lat="lat", lon="lon"):
        return [i for i in items if i.get(lat) is not None and in_polygons(i[lon], i[lat], polygons)]

    reports = inside(load_json(DATA / "fix-my-street.json")["items"])
    planning = inside(load_json(DATA / "planning-applications.json")["applications"])
    collisions = inside(load_json(DATA / "road-collisions.json")["serious_collisions"])
    by_year = Counter(c["date"][:4] for c in collisions)
    return {
        "fix_my_street": [{"title": r["title"], "group": r["group"], "published": r["published_iso"][:10], "url": r["url"],
                           "lat": r["lat"], "lon": r["lon"]} for r in reports],
        "planning": [{"ref": p["ref"], "address": p["address"], "description": p["description"], "status": p["status"],
                      "received": p["received_date"], "url": p["url"], "lat": p["lat"], "lon": p["lon"]} for p in planning],
        "serious_collisions": [{"date": c["date"], "severity": c["severity"], "road": c["road"], "lat": c["lat"], "lon": c["lon"]}
                               for c in sorted(collisions, key=lambda c: c["date"], reverse=True)],
        "serious_collisions_by_year": [{"year": y, "count": n} for y, n in sorted(by_year.items())],
    }


def build_ward(name, features, ward_cache, postcodes):
    feature = next(f for f in features if f["properties"]["name"] == name)
    code = feature["properties"]["ward_code"]
    polygons = polygons_of(feature["geometry"])
    (clon, clat), area_km2 = centroid_and_area(polygons)

    neighbours = sorted(f["properties"]["name"] for f in features
                        if f["properties"]["name"] != name and touches(polygons, polygons_of(f["geometry"])))
    ward_postcodes = {pc for pc, w in ward_cache.items() if w["ward_code"] == code}

    outer = polygons[0][0]
    position, centre_miles = position_from_centre(clat, clon)
    broadband = next((w for w in load_json(DATA / "broadband-summary.json")["ward_summary"] if w["name"] == name), None)

    services = build_services(polygons, (clon, clat), postcodes)
    venues = next(s for s in services if s["id"] == "venue")
    listed = next(s for s in services if s["id"] == "listed")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "name": name,
        "slug": slugify(name),
        "code": code,
        "centre": {"lat": round(clat, 5), "lon": round(clon, 5)},
        "area_km2": round(area_km2, 2),
        "position": position,
        "centre_distance_miles": centre_miles,
        "postcode_count": len(ward_postcodes),
        "neighbours": neighbours,
        "boundary": [[round(lat, 5), round(lon, 5)] for lon, lat in outer],
        "broadband": broadband,
        "crime": build_crime(polygons),
        "house_prices": build_house_prices(ward_postcodes),
        "local_issues": build_local_issues(polygons),
        "venue_types": [{"type": t, "count": n} for t, n in Counter(i["type"] for i in venues["items"]).most_common()],
        "listed_grades": [{"grade": g, "count": n} for g, n in sorted(Counter(i["detail"] for i in listed["items"]).items())],
        "services": services,
    }


def write_index():
    """One summary row per ward profile on disk, for the Cheltenham Wards page."""
    rows = []
    for path in sorted(OUT_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        with open(path, encoding="utf-8") as f:
            w = json.load(f)
        listed = next(s for s in w["services"] if s["id"] == "listed")
        rows.append({
            "name": w["name"], "slug": w["slug"], "code": w["code"], "position": w["position"],
            "area_km2": w["area_km2"], "postcode_count": w["postcode_count"],
            "crime_total": w["crime"]["total"], "crime_change_pct": w["crime"]["change_pct"],
            "crime_last_month": w["crime"]["last_month"],
            "median": w["house_prices"]["last12_median"], "median_display": w["house_prices"]["last12_median_display"],
            "sales": w["house_prices"]["last12_sales"],
            "gigabit_pct": w["broadband"]["gigabit_pct"] if w["broadband"] else None,
            "listed": listed["in_ward"],
            "centre": w["centre"], "boundary": w["boundary"],
        })
    rows.sort(key=lambda r: r["name"])
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "wards": rows}
    with open(OUT_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {(OUT_DIR / 'index.json').relative_to(ROOT)}: {len(rows)} wards")


def main(argv):
    names = argv or WARDS
    features = load_json(DATA / "broadband-map.json")["features"]
    ward_cache = load_json(SOURCES / "_ward-cache.json")
    postcodes = load_postcodes()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        ward = build_ward(name, features, ward_cache, postcodes)
        path = OUT_DIR / f"{ward['slug']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ward, f, indent=2, ensure_ascii=False)
            f.write("\n")
        shown = sum(len(s["items"]) for s in ward["services"])
        print(f"Wrote {path.relative_to(ROOT)}: {ward['crime']['total']} crimes, "
              f"{ward['house_prices']['sales_total']} sales, {shown} places")
    write_index()


if __name__ == "__main__":
    main(sys.argv[1:])
