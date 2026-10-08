#!/usr/bin/env python3
"""Build _data/covid.json, the COVID-19 history of Cheltenham from February 2020
to December 2023, from the UK Health Security Agency (UKHSA) data dashboard API.

Run manually — not part of any scheduled workflow. This is a one-off history:
free testing ended in April 2022, ONS stopped publishing weekly COVID-19 deaths
by local area at the end of 2023, and the page stops there. Run it again only if
UKHSA revises the figures for that period:

  python _python/local/process-covid.py

Cases, tests, positivity and deaths are for Cheltenham borough (lower tier
local authority E07000078). Hospital admissions and occupied beds are for
Gloucestershire Hospitals NHS Foundation Trust, which runs Cheltenham General
and Gloucestershire Royal. Vaccine uptake is for Cheltenham borough by age.
"""
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helper  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "_data" / "covid.json"

API = "https://api.ukhsa-dashboard.data.gov.uk/themes/infectious_disease/sub_themes/respiratory/topics/COVID-19"
SOURCE = "UK Health Security Agency data dashboard"
SOURCE_URL = "https://ukhsa-dashboard.data.gov.uk/respiratory-viruses/covid-19"
LICENCE = "Open Government Licence v3.0"

FIRST_DATE = "2020-02-01"
LAST_DATE = "2023-12-31"

AREA = ("Lower Tier Local Authority", "Cheltenham")
TRUST = ("NHS Trust", "Gloucestershire Hospitals NHS Foundation Trust")

# (key, geography, metric, how each week is summarised)
WEEKLY_SERIES = [
    ("cases", AREA, "COVID-19_cases_casesByDay", "sum"),
    ("tests", AREA, "COVID-19_testing_PCRcountByDay", "sum"),
    ("positivity", AREA, "COVID-19_testing_positivity7DayRolling", "last"),
    ("deaths", AREA, "COVID-19_deaths_ONSByWeek", "sum"),
    ("admissions", TRUST, "COVID-19_healthcare_admissionByDay", "sum"),
    ("beds", TRUST, "COVID-19_healthcare_occupiedBedsByDay", "mean"),
]
YEARLY_KEYS = ("cases", "tests", "deaths", "admissions")

VACCINE_CAMPAIGNS = [
    ("Autumn 2022", "COVID-19_vaccinations_autumn22_uptakeByDay"),
    ("Spring 2023", "COVID-19_vaccinations_spring23_uptakeByDay"),
    ("Autumn 2023", "COVID-19_vaccinations_autumn23_uptakeByDay"),
]


def in_range(rows):
    return [r for r in rows if FIRST_DATE <= r["date"] <= LAST_DATE]


def week_start(iso):
    d = date.fromisoformat(iso)
    return (d - timedelta(days=d.weekday())).isoformat()


def is_everyone(r):
    return r.get("stratum", "default") == "default" and r.get("sex", "all") == "all" and r.get("age", "all") == "all"


def weekly(rows, how):
    """[{week, value}] by Monday-starting week: the sum, the mean, or the
    last value in each week (for a figure that is already a 7-day rolling rate)."""
    weeks = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["date"]):
        if is_everyone(r) and r["metric_value"] is not None:
            weeks[week_start(r["date"])].append(r["metric_value"])
    out = []
    for week in sorted(weeks):
        values = weeks[week]
        if how == "sum":
            value = sum(values)
        elif how == "mean":
            value = sum(values) / len(values)
        else:
            value = values[-1]
        value = round(value, 1) if how == "last" else round(value)
        out.append({"week": week, "value": value})
    return out


def yearly(rows):
    """{calendar year: total} of the daily (or, for deaths, weekly) figures,
    each counted in the year of its own date."""
    totals = defaultdict(int)
    for r in rows:
        if is_everyone(r) and r["metric_value"] is not None:
            totals[r["date"][:4]] += round(r["metric_value"])
    return dict(totals)


def peak(weeks):
    if not weeks:
        return None
    best = max(weeks, key=lambda w: (w["value"], -date.fromisoformat(w["week"]).toordinal()))
    return {"week": best["week"], "value": best["value"]}


def uptake_at_cutoff(rows):
    """Uptake (%) by age band for everyone, as at the last report on or before LAST_DATE."""
    latest = {}
    for r in sorted(in_range(rows), key=lambda r: r["date"]):
        if r.get("sex") == "all" and r.get("stratum", "default") == "default" and r["metric_value"] is not None:
            latest[r["age"]] = {"age": r["age"], "uptake": r["metric_value"], "date": r["date"]}
    return [latest[a] for a in sorted(latest)]


def fetch(geography, metric):
    geo_type, geo = geography
    url = f"{API}/geography_types/{quote(geo_type)}/geographies/{quote(geo)}/metrics/{metric}"
    rows, params = [], {"page_size": 365, "page": 1}
    while True:
        payload = helper.get(url, params=params, timeout=60).json()
        rows += payload["results"]
        if not payload.get("next"):
            return rows
        params["page"] += 1


def main():
    weekly_series, by_year = {}, {}
    for key, geography, metric, how in WEEKLY_SERIES:
        rows = in_range(fetch(geography, metric))
        weekly_series[key] = weekly(rows, how)
        if key in YEARLY_KEYS:
            by_year[key] = yearly(rows)
        print(f"{key}: {len(weekly_series[key])} weeks")

    years = []
    for year in sorted({y for totals in by_year.values() for y in totals}):
        entry = {"year": year}
        for key in YEARLY_KEYS:
            entry[key] = by_year[key].get(year, 0)
            entry[f"{key}_display"] = f"{entry[key]:,}"
        years.append(entry)
    totals = {}
    for key in YEARLY_KEYS:
        totals[key] = sum(by_year[key].values())
        totals[f"{key}_display"] = f"{totals[key]:,}"

    peaks = {key: peak(weeks) for key, weeks in weekly_series.items()}
    for p in peaks.values():
        if p:
            p["value_display"] = f"{p['value']:,}"

    vaccinations = []
    for campaign, metric in VACCINE_CAMPAIGNS:
        vaccinations.append({"campaign": campaign, "ages": uptake_at_cutoff(fetch(AREA, metric))})

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "first_date": FIRST_DATE,
        "last_date": LAST_DATE,
        "area": AREA[1],
        "trust": TRUST[1],
        "weekly": weekly_series,
        "years": years,
        "totals": totals,
        "peaks": peaks,
        "vaccinations": vaccinations,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
