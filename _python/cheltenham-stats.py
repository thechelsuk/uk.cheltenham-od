"""Fetch population, growth and employment statistics for Cheltenham from
Nomis (the ONS's official labour market and census data service) — a public,
keyless API — and write normalised JSON to Jekyll's _data dir.

Source: https://www.nomisweb.co.uk/api/v01/
"""

import csv
import datetime
import io

import helper

BASE_URL = "https://www.nomisweb.co.uk/api/v01/dataset"
GEOGRAPHY = "E07000078"  # Cheltenham (ONS/GSS area code)

# Mid-year population estimates by single year of age and sex. Nomis has
# annual data from 2001 onwards for this geography — request every year in
# the range (not just a handful of sample years) so the growth chart doesn't
# show misleading gaps; Nomis simply omits years not yet published.
POPULATION_DATASET = "NM_31_1"
POPULATION_START_YEAR = 2001

# Annual Population Survey — labour market rates (percentages), aged 16-64.
EMPLOYMENT_DATASET = "NM_17_5"
EMPLOYMENT_VARIABLES = {
    "economic_activity_rate": 18,
    "employment_rate": 45,
    "unemployment_rate": 84,
}

# Census 2021 — usual resident population (TS001).
CENSUS_DATASET = "NM_2021_1"

EMPLOYMENT_START_YEAR = 2004


def fetch_csv_rows(dataset, **params):
    resp = helper.request_with_retry(
        "GET", f"{BASE_URL}/{dataset}.data.csv",
        params={"geography": GEOGRAPHY, **params},
        timeout=20,
    )
    return list(csv.DictReader(io.StringIO(resp.text)))


def fetch_population_series():
    current_year = datetime.date.today().year
    rows = fetch_csv_rows(
        POPULATION_DATASET,
        date=f"{POPULATION_START_YEAR}-{current_year}",
        sex=7, age=0, measures=20100,
    )
    series = []
    for row in sorted(rows, key=lambda r: r["DATE"]):
        population = int(float(row["OBS_VALUE"]))
        series.append({
            "year": int(row["DATE"]),
            "population": population,
            "population_formatted": f"{population:,}",
        })
    return series


def fetch_employment_rates():
    """Some rates (typically unemployment) are suppressed by Nomis at local
    authority level as statistically unreliable — those come back with an
    empty OBS_VALUE and are recorded as None rather than fetched."""
    rates = {}
    for key, variable in EMPLOYMENT_VARIABLES.items():
        rows = fetch_csv_rows(EMPLOYMENT_DATASET, date="latest", variable=variable, measures=20599)
        if not rows:
            continue
        value = rows[0]["OBS_VALUE"]
        rates[key] = float(value) if value else None
        rates["period"] = rows[0]["DATE_NAME"]
    return rates


def fetch_employment_series():
    """Full annual history (calendar-year-ending, i.e. the Jan-Dec Q4 rolling
    period) for each rate, back to 2004 — the earliest Nomis has for this
    geography. The underlying data is quarterly/rolling; we keep just the
    Dec-ending point per year so the chart shows one clean value per year.
    As with the latest-only figures, some years' unemployment rate is
    suppressed by the ONS as statistically unreliable — recorded as None.
    """
    current_year = datetime.date.today().year
    by_year = {}
    for key, variable in EMPLOYMENT_VARIABLES.items():
        rows = fetch_csv_rows(
            EMPLOYMENT_DATASET,
            date=f"{EMPLOYMENT_START_YEAR}-12-{current_year}-12",
            variable=variable, measures=20599,
        )
        for row in rows:
            if not row["DATE"].endswith("-12"):
                continue
            year = int(row["DATE"][:4])
            by_year.setdefault(year, {"year": year})
            value = row["OBS_VALUE"]
            by_year[year][key] = float(value) if value else None

    return [by_year[year] for year in sorted(by_year)]


def fetch_census_population():
    rows = fetch_csv_rows(CENSUS_DATASET, measures=20100)
    total_row = next((r for r in rows if r.get("C2021_RESTYPE_3_CODE") == "0"), None)
    return int(float(total_row["OBS_VALUE"])) if total_row else None


if __name__ == "__main__":
    root = helper.repo_root()
    out_path = root / "_data" / "cheltenham-stats.json"
    employment_out_path = root / "_data" / "cheltenham-employment.json"

    print("Fetching population time series...")
    population_series = fetch_population_series()
    latest = population_series[-1]
    earliest = population_series[0]
    growth_pct = round((latest["population"] - earliest["population"]) / earliest["population"] * 100, 1)
    print(f"  {earliest['year']}: {earliest['population']:,} -> {latest['year']}: {latest['population']:,} ({growth_pct}%)")

    print("Fetching employment rates...")
    employment = fetch_employment_rates()
    print(f"  {employment}")

    print("Fetching employment history...")
    employment_series = fetch_employment_series()
    print(f"  {len(employment_series)} years, {employment_series[0]['year']}-{employment_series[-1]['year']}")

    print("Fetching Census 2021 population...")
    census_population = fetch_census_population()
    print(f"  {census_population:,}")

    payload = {
        "updated":            helper.updated_timestamp(),
        "updated_iso":        datetime.date.today().isoformat(),
        "source":             "https://www.nomisweb.co.uk/",
        "geography_code":     GEOGRAPHY,
        "population_series":  population_series,
        "population_latest":  latest,
        "population_earliest": earliest,
        "growth_pct":         growth_pct,
        "growth_years":       latest["year"] - earliest["year"],
        "employment":         employment,
        "census_2021_population": census_population,
        "census_2021_population_formatted": f"{census_population:,}",
    }

    helper.write_json(out_path, payload)
    print(f"Wrote stats to {out_path}")

    employment_payload = {
        "updated":     helper.updated_timestamp(),
        "updated_iso": datetime.date.today().isoformat(),
        "source":      "https://www.nomisweb.co.uk/",
        "series":      employment_series,
    }
    helper.write_json(employment_out_path, employment_payload)
    print(f"Wrote employment history to {employment_out_path}")
