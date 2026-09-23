"""Build the Cheltenham crime map: crimes per 1,000 residents over rolling
12-month windows, for each small census area (LSOA) and each electoral ward.

Nothing is fetched. Street-level crimes come from _data/crime/ (written by
crime.py), LSOA boundaries and populations from _data/small-areas.json
(small-areas.py), and ward boundaries from _data/broadband-map.json, the same
polygons the ward profiles count crime against, so ward totals match them.
Run after crime.py and small-areas.py:

	.venv/bin/python _python/crime-map.py
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import helper


DATA = Path(__file__).resolve().parents[1] / "_data"
OUT = DATA / "crime-map.json"
WINDOW = 12
SHADES = 6  # colour bands on the map, matching the six blues in themes.css


def load_json(path):
	return json.loads(path.read_text(encoding="utf-8"))


def in_rings(lat, lon, rings):
	"""Even-odd point-in-polygon across every ring, so holes and multi-part
	areas both work without knowing which ring is which. Rings are [lat, lon]."""
	inside = False
	for ring in rings:
		j = len(ring) - 1
		for i in range(len(ring)):
			yi, xi = ring[i]
			yj, xj = ring[j]
			if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
				inside = not inside
			j = i
	return inside


def bbox(rings):
	lats = [p[0] for ring in rings for p in ring]
	lons = [p[1] for ring in rings for p in ring]
	return min(lats), max(lats), min(lons), max(lons)


def locate(lat, lon, areas):
	for area in areas:
		south, north, west, east = area["bbox"]
		if south <= lat <= north and west <= lon <= east and in_rings(lat, lon, area["boundary"]):
			return area
	return None


def full_months(index):
	"""Months the police have published in full. A month whose town-wide total
	is under half the usual is a gap in the feed, not a quiet month (the same
	rule the ward profiles use)."""
	town = {m["month"]: sum(n["crime_count"] for n in m["neighbourhoods"]) for m in index["months"]}
	usual = statistics.median(town.values())
	return sorted(month for month, total in town.items() if total >= usual / 2)


def population_for(area, year):
	"""The mid-year estimate for `year`, or the nearest earlier one when that
	year hasn't been published yet."""
	years = sorted(area["population"])
	usable = [y for y in years if y <= year] or years[:1]
	return usable[-1], area["population"][usable[-1]]


def load_wards():
	slugs = {}
	for path in (DATA / "wards").glob("*.json"):
		ward = load_json(path)
		if "code" in ward:
			slugs[ward["code"]] = ward["slug"]
	populations = {w["code"]: w for w in load_json(DATA / "small-areas.json")["wards"]}
	wards = []
	for feature in load_json(DATA / "broadband-map.json")["features"]:
		code = feature["properties"].get("ward_code")
		if code not in populations:
			continue
		rings = feature["geometry"]["coordinates"]
		if feature["geometry"]["type"] == "MultiPolygon":
			rings = [ring for polygon in rings for ring in polygon]
		wards.append({
			"code": code,
			"name": populations[code]["name"],
			"slug": slugs.get(code),
			"population": populations[code]["population"],
			"boundary": [[[round(lat, 5), round(lon, 5)] for lon, lat in ring] for ring in rings],
		})
	missing = set(populations) - {w["code"] for w in wards}
	if missing:
		raise RuntimeError(f"Wards with no boundary in broadband-map.json: {sorted(missing)}")
	return sorted(wards, key=lambda w: w["name"])


def load_lsoas():
	return [
		{key: area[key] for key in ("code", "name", "ward_code", "ward_name", "population", "boundary")}
		for area in load_json(DATA / "small-areas.json")["lsoas"]
	]


def count_crimes(index, months, levels):
	"""Adds a {month: count} `by_month` to every area in every level."""
	for areas in levels.values():
		for area in areas:
			area["bbox"] = bbox(area["boundary"])
			area["by_month"] = dict.fromkeys(months, 0)
	wanted = set(months)
	seen = set()
	unplaced = dict.fromkeys(levels, 0)
	for month in index["months"]:
		if month["month"] not in wanted:
			continue
		for hood in month["neighbourhoods"]:
			for crime in load_json(DATA / "crime" / hood["file"])["crimes"]:
				if crime["id"] in seen:
					continue
				seen.add(crime["id"])
				lat = float(crime["location"]["latitude"])
				lon = float(crime["location"]["longitude"])
				for level, areas in levels.items():
					area = locate(lat, lon, areas)
					if area:
						area["by_month"][month["month"]] += 1
					else:
						unplaced[level] += 1
	return len(seen), unplaced


def band_edges(values):
	"""Five cut points splitting every rate into six equal-sized bands, so the
	colours stay comparable as the window moves."""
	ordered = sorted(values)
	edges = []
	for i in range(1, SHADES):
		edge = round(ordered[min(len(ordered) - 1, round(i * len(ordered) / SHADES))])
		edges.append(max(edge, edges[-1] + 1) if edges else edge)
	return edges


def summarise(areas, windows, extra_keys):
	rates = []
	out = []
	for area in areas:
		crimes, rate, residents = [], [], []
		for window in windows:
			total = sum(area["by_month"][m] for m in window["months"])
			_, population = population_for(area, window["population_year"])
			crimes.append(total)
			residents.append(population)
			rate.append(round(1000 * total / population, 1))
		rates.extend(rate)
		out.append({
			"code": area["code"],
			"name": area["name"],
			**{key: area[key] for key in extra_keys},
			"boundary": area["boundary"],
			"crimes": crimes,
			"residents": residents,
			"rate": rate,
			"latest": {
				"crimes": crimes[-1],
				"crimes_display": f"{crimes[-1]:,}",
				"residents": residents[-1],
				"residents_display": f"{residents[-1]:,}",
				"rate": rate[-1],
				"rate_display": f"{rate[-1]:,.1f}",
			},
		})
	return {"bands": band_edges(rates), "areas": out}


def main():
	index = load_json(DATA / "crime" / "index.json")
	months = full_months(index)
	if len(months) < WINDOW:
		raise RuntimeError(f"Only {len(months)} full months of crime data; need {WINDOW}")

	levels = {"lsoa": load_lsoas(), "ward": load_wards()}
	crime_total, unplaced = count_crimes(index, months, levels)

	windows = []
	for end in range(WINDOW - 1, len(months)):
		span = months[end - WINDOW + 1:end + 1]
		windows.append({
			"first_month": span[0],
			"last_month": span[-1],
			"population_year": span[-1][:4],
			"months": span,
		})
	# The estimate actually used, once a window ends in a year not yet published.
	sample = levels["lsoa"][0]
	for window in windows:
		window["population_year"] = population_for(sample, window["population_year"])[0]

	small_areas = load_json(DATA / "small-areas.json")
	helper.write_json(OUT, {
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"source": "Police.uk street-level crime",
		"source_url": "https://data.police.uk/",
		"population_source": small_areas["source"],
		"population_source_url": small_areas["source_url"],
		"boundaries_source": small_areas["boundaries_source"],
		"boundaries_source_url": small_areas["boundaries_source_url"],
		"licence": "Open Government Licence v3.0",
		"window_months": WINDOW,
		"windows": [{k: w[k] for k in ("first_month", "last_month", "population_year")} for w in windows],
		"lsoa": summarise(levels["lsoa"], windows, ("ward_name",)),
		"ward": summarise(levels["ward"], windows, ("slug",)),
	})
	print(
		f"Wrote {len(windows)} windows ({windows[0]['first_month']} to {windows[-1]['last_month']}) "
		f"from {crime_total:,} crimes to {OUT}; outside every LSOA: {unplaced['lsoa']}, "
		f"outside every ward: {unplaced['ward']}"
	)


if __name__ == "__main__":
	main()
