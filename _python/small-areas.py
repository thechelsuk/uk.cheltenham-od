"""Fetch Cheltenham's small census areas (LSOAs) and electoral wards with their
resident population, for mapping rates such as crimes per 1,000 residents.

Boundaries and the LSOA-to-ward lookup come from the ONS Open Geography
Portal, and mid-year population estimates from Nomis (the ONS's keyless
statistics API). The estimates are published once a year and boundaries
change far less often, so a monthly refresh simply picks up each new year.

Run from the repository root:
	.venv/bin/python _python/small-areas.py
"""

import csv
import io
from datetime import date, datetime, timezone
from pathlib import Path

import helper


GEOGRAPHY = "E07000078"  # Cheltenham (ONS/GSS area code)
OUT = Path(__file__).resolve().parents[1] / "_data" / "small-areas.json"
TIMEOUT = 60

NOMIS_URL = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2014_1.data.csv"
# Nomis geography types for this dataset: 2021 LSOAs, and wards as of May 2025
# (the boundaries Cheltenham has used since the 2024 borough elections).
LSOA_TYPE = "TYPE151"
WARD_TYPE = "TYPE182"
FIRST_YEAR = 2021  # the dataset is 2021-census based

ARCGIS = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
BOUNDARIES_URL = f"{ARCGIS}/Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5/FeatureServer/0/query"
LOOKUP_URL = f"{ARCGIS}/LSOA21_WD25_LAD25_EW_LU_v2/FeatureServer/0/query"

SOURCE_URL = "https://www.nomisweb.co.uk/datasets/pestoa2021"
BOUNDARIES_SOURCE_URL = "https://geoportal.statistics.gov.uk/"


def fetch_populations(geography_type):
	"""{area code: {year: population}} for every year Nomis has published."""
	response = helper.request_with_retry(
		"GET", NOMIS_URL, timeout=TIMEOUT,
		params={
			"geography": f"{GEOGRAPHY}{geography_type}",
			"date": f"{FIRST_YEAR}-{date.today().year}",
			"gender": 0, "c_age": 200, "measures": 20100,
			"select": "date_name,geography_code,geography_name,obs_value",
		},
	)
	populations, names = {}, {}
	for row in csv.DictReader(io.StringIO(response.text)):
		code = row["GEOGRAPHY_CODE"]
		populations.setdefault(code, {})[row["DATE_NAME"]] = int(row["OBS_VALUE"])
		names[code] = row["GEOGRAPHY_NAME"]
	if not populations:
		raise RuntimeError(f"Nomis returned no population rows for {geography_type}")
	return populations, names


def arcgis_query(url, **params):
	response = helper.request_with_retry(
		"GET", url, timeout=TIMEOUT,
		params={"outFields": "*", "f": "json", **params},
	)
	payload = response.json()
	if "error" in payload:
		raise RuntimeError(f"ArcGIS error from {url}: {payload['error']}")
	return payload


def fetch_lookup():
	"""{LSOA code: (ward code, ward name)} from the ONS best-fit lookup."""
	payload = arcgis_query(LOOKUP_URL, where=f"LAD25CD='{GEOGRAPHY}'", returnGeometry="false")
	return {
		f["attributes"]["LSOA21CD"]: (f["attributes"]["WD25CD"], f["attributes"]["WD25NM"])
		for f in payload["features"]
	}


def fetch_boundaries(codes):
	"""{LSOA code: list of rings as [[lat, lon], ...]}, outer ring first."""
	quoted = ",".join(f"'{code}'" for code in sorted(codes))
	payload = arcgis_query(
		BOUNDARIES_URL, where=f"LSOA21CD IN ({quoted})",
		outFields="LSOA21CD", outSR=4326, returnGeometry="true",
	)
	boundaries = {}
	for feature in payload["features"]:
		rings = feature["geometry"]["rings"]
		boundaries[feature["attributes"]["LSOA21CD"]] = [
			[[round(lat, 5), round(lon, 5)] for lon, lat in ring] for ring in rings
		]
	return boundaries


def population_fields(by_year):
	latest = max(by_year)
	return {
		"population": by_year,
		"population_latest": by_year[latest],
		"population_latest_display": f"{by_year[latest]:,}",
	}


def main():
	lookup = fetch_lookup()
	lsoa_population, lsoa_names = fetch_populations(LSOA_TYPE)
	ward_population, ward_names = fetch_populations(WARD_TYPE)
	boundaries = fetch_boundaries(lookup)

	missing = set(lookup) - set(boundaries) | set(lookup) - set(lsoa_population)
	if missing:
		raise RuntimeError(f"LSOAs missing a boundary or population: {sorted(missing)}")

	lsoas = []
	for code in sorted(lookup):
		ward_code, ward_name = lookup[code]
		lsoas.append({
			"code": code,
			"name": lsoa_names[code],
			"ward_code": ward_code,
			"ward_name": ward_name,
			**population_fields(lsoa_population[code]),
			"boundary": boundaries[code],
		})

	# Nomis appends "(Cheltenham)" to ward names shared with other districts;
	# the ONS lookup carries the plain names the rest of the site uses.
	plain_names = {code: name for code, name in lookup.values()}
	wards = [
		{"code": code, "name": plain_names.get(code, ward_names[code]), **population_fields(by_year)}
		for code, by_year in sorted(ward_population.items())
	]

	years = sorted({year for area in lsoas for year in area["population"]})
	helper.write_json(OUT, {
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"source": "ONS mid-year population estimates for small areas, via Nomis",
		"source_url": SOURCE_URL,
		"boundaries_source": "ONS Open Geography Portal",
		"boundaries_source_url": BOUNDARIES_SOURCE_URL,
		"licence": "Open Government Licence v3.0",
		"population_years": years,
		"lsoa_count": len(lsoas),
		"ward_count": len(wards),
		"lsoas": lsoas,
		"wards": wards,
	})
	print(f"Wrote {len(lsoas)} LSOAs and {len(wards)} wards ({years[0]}-{years[-1]}) to {OUT}")


if __name__ == "__main__":
	main()
