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

# Mid-year population estimates by single year of age and sex.
POPULATION_DATASET = "NM_31_1"
POPULATION_YEARS = [2001, 2006, 2011, 2016, 2020, 2021, 2022, 2023, 2024, 2025]

# Annual Population Survey — labour market rates (percentages), aged 16-64.
EMPLOYMENT_DATASET = "NM_17_5"
EMPLOYMENT_VARIABLES = {
    "economic_activity_rate": 18,
    "employment_rate": 45,
    "unemployment_rate": 84,
}

# Census 2021 — usual resident population (TS001).
CENSUS_DATASET = "NM_2021_1"


def fetch_csv_rows(dataset, **params):
    resp = helper.request_with_retry(
        "GET", f"{BASE_URL}/{dataset}.data.csv",
        params={"geography": GEOGRAPHY, **params},
        timeout=20,
    )
    return list(csv.DictReader(io.StringIO(resp.text)))


def fetch_population_series():
    rows = fetch_csv_rows(
        POPULATION_DATASET,
        date=",".join(str(y) for y in POPULATION_YEARS),
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


def fetch_census_population():
    rows = fetch_csv_rows(CENSUS_DATASET, measures=20100)
    total_row = next((r for r in rows if r.get("C2021_RESTYPE_3_CODE") == "0"), None)
    return int(float(total_row["OBS_VALUE"])) if total_row else None


if __name__ == "__main__":
    out_path = helper.repo_root() / "_data" / "cheltenham-stats.json"

    print("Fetching population time series...")
    population_series = fetch_population_series()
    latest = population_series[-1]
    earliest = population_series[0]
    growth_pct = round((latest["population"] - earliest["population"]) / earliest["population"] * 100, 1)
    print(f"  {earliest['year']}: {earliest['population']:,} -> {latest['year']}: {latest['population']:,} ({growth_pct}%)")

    print("Fetching employment rates...")
    employment = fetch_employment_rates()
    print(f"  {employment}")

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
