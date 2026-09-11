"""Fetch street-level crime data for Cheltenham neighbourhoods.

The Police API anonymises crime locations, so the coordinates in the output
must not be treated as the exact location of an incident.

Run from the repository root:
	.venv/bin/python _python/crime.py
	.venv/bin/python _python/crime.py --date 2026-07
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


API_ROOT = "https://data.police.uk/api"
FORCE = {"id": "gloucestershire", "name": "Gloucestershire Constabulary"}
AREA_NAME = "Cheltenham"
TIMEOUT = 60
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "_data" / "crime"
HEADERS = {"User-Agent": "uk.cheltenham-od crime data importer"}

# These are the Cheltenham neighbourhoods in the Gloucestershire force area.
# Keeping the names explicit prevents nearby Gloucester and Tewkesbury areas
# from being included if the force adds more neighbourhoods later.
CHELTENHAM_NEIGHBOURHOODS = {
	"Hesters Way",
	"Springbank and Fiddlers Green",
	"St Marks",
	"Swindon Village and Wymans Brook",
	"Whaddon Lynworth and Oakley",
	"Prestbury",
	"St Pauls and Pittville",
	"Lansdown",
	"Cheltenham Town Centre",
	"Fairview",
	"Leckhampton",
	"Benhall and Hatherley",
	"Charlton Kings",
	"Tivoli",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def request_json(method, url, **kwargs):
	for attempt in range(5):
		response = requests.request(
			method, url, headers=HEADERS, timeout=TIMEOUT, **kwargs
		)
		if response.status_code not in (429, 502, 503, 504):
			response.raise_for_status()
			return response.json()
		if attempt == 4:
			response.raise_for_status()
		retry_after = response.headers.get("Retry-After")
		delay = float(retry_after) if retry_after else 2 ** attempt
		log.warning("%s from Police API; retrying in %ss", response.status_code, delay)
		time.sleep(delay)
	raise RuntimeError("Police API request failed after retries")


def get_json(url, **kwargs):
	return request_json("GET", url, **kwargs)


def post_json(url, data):
	return request_json("POST", url, data=data)


def fetch_neighbourhoods():
	neighbourhoods = get_json(f"{API_ROOT}/{FORCE['id']}/neighbourhoods")
	selected = [
		neighbourhood
		for neighbourhood in neighbourhoods
		if neighbourhood["name"] in CHELTENHAM_NEIGHBOURHOODS
	]
	missing = CHELTENHAM_NEIGHBOURHOODS - {item["name"] for item in selected}
	if missing:
		raise RuntimeError(f"Cheltenham neighbourhoods missing from API: {sorted(missing)}")
	return sorted(selected, key=lambda item: item["name"])


def fetch_latest_month():
	latest = get_json(f"{API_ROOT}/crime-last-updated")
	return latest["date"][:7]


def fetch_boundary(neighbourhood):
	neighbourhood_id = neighbourhood["id"]
	return get_json(
		f"{API_ROOT}/{FORCE['id']}/{neighbourhood_id}/boundary"
	)


def fetch_neighbourhood_data(neighbourhood, boundary, date):
	polygon = ":".join(
		f"{point['latitude']},{point['longitude']}" for point in boundary
	)
	crimes = post_json(
		f"{API_ROOT}/crimes-street/all-crime",
		{"date": date, "poly": polygon},
	)
	return {
		"schema_version": 1,
		"source": "https://data.police.uk/docs/method/crime-street/",
		"force": FORCE,
		"area": AREA_NAME,
		"neighbourhood": neighbourhood,
		"month": date,
		"boundary": boundary,
		"crimes": crimes,
		"crime_count": len(crimes),
	}


def month_range(start_date, end_date):
	start = datetime.strptime(start_date, "%Y-%m")
	end = datetime.strptime(end_date, "%Y-%m")
	if start > end:
		raise ValueError("start date must not be after end date")
	months = []
	current = start
	while current <= end:
		months.append(current.strftime("%Y-%m"))
		if current.month == 12:
			current = current.replace(year=current.year + 1, month=1)
		else:
			current = current.replace(month=current.month + 1)
	return months


def save_data(records_by_month):
	month_summaries = {}
	index_path = OUTPUT_DIR / "index.json"
	if index_path.exists():
		try:
			existing_index = json.loads(index_path.read_text(encoding="utf-8"))
			month_summaries = {
				item["month"]: item for item in existing_index.get("months", [])
			}
		except (json.JSONDecodeError, KeyError):
			log.warning("Could not read existing crime index; rebuilding it")

	for date, records in records_by_month.items():
		month_dir = OUTPUT_DIR / date
		month_dir.mkdir(parents=True, exist_ok=True)
		summaries = []
		for record in records:
			filename = month_dir / f"{record['neighbourhood']['id']}.json"
			filename.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
			summaries.append(
				{
					**record["neighbourhood"],
					"crime_count": record["crime_count"],
					"file": f"{date}/{filename.stem}.json",
				}
			)
		month_summaries[date] = {"month": date, "neighbourhoods": summaries}

	sorted_months = [month_summaries[date] for date in sorted(month_summaries)]
	years = sorted({date[:4] for date in month_summaries}, reverse=True)

	index = {
		"schema_version": 1,
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"source": "https://data.police.uk/docs/method/crime-street/",
		"force": FORCE,
		"area": AREA_NAME,
		"years": years,
		"months": sorted_months,
	}
	(OUTPUT_DIR / "index.json").write_text(
		json.dumps(index, indent=2) + "\n", encoding="utf-8"
	)


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--date",
		help="Single month to fetch in YYYY-MM format",
	)
	parser.add_argument("--start-date", help="First month in an inclusive YYYY-MM range")
	parser.add_argument("--end-date", help="Last month in an inclusive YYYY-MM range")
	parser.add_argument(
		"--overwrite",
		action="store_true",
		help="Re-fetch and overwrite months that already have saved data",
	)
	args = parser.parse_args()
	if args.date and (args.start_date or args.end_date):
		parser.error("use --date or --start-date/--end-date, not both")
	if args.date:
		start_date = end_date = args.date
	else:
		start_date = args.start_date or fetch_latest_month()
		end_date = args.end_date or start_date
	try:
		months = month_range(start_date, end_date)
	except ValueError as error:
		parser.error(str(error))

	existing_months = [date for date in months if (OUTPUT_DIR / date).exists()]
	if existing_months and not args.overwrite:
		parser.error(
			f"data already saved for {', '.join(existing_months)}; "
			"pass --overwrite to re-fetch and replace it"
		)

	neighbourhoods = fetch_neighbourhoods()
	boundaries = {}
	for neighbourhood in neighbourhoods:
		log.info("Fetching boundary for %s", neighbourhood["name"])
		boundaries[neighbourhood["id"]] = fetch_boundary(neighbourhood)

	records_by_month = {}
	for date in months:
		records_by_month[date] = []
		for neighbourhood in neighbourhoods:
			log.info("Fetching %s for %s", neighbourhood["name"], date)
			records_by_month[date].append(
				fetch_neighbourhood_data(
					neighbourhood, boundaries[neighbourhood["id"]], date
				)
			)
	save_data(records_by_month)
	log.info("Saved %s neighbourhood files across %s month(s) in %s", len(neighbourhoods) * len(months), len(months), OUTPUT_DIR)


if __name__ == "__main__":
	main()
