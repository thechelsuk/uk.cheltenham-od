#!/usr/bin/env python3
"""Fetch pupil absence from the Department for Education's "Pupil absence in
schools in England" statistics on Explore Education Statistics (EES) and write
_data/school-absence.json:

- Gloucestershire, the South West and England each year: the overall absence
  rate (share of possible sessions missed), persistent absence (share of
  pupils missing 10% or more) and severe absence (50% or more), all state-
  funded primary, secondary and special schools, pupils aged 5 to 15
- The same three measures by phase for the latest year
- Each Cheltenham school in _data/schools.json that the DfE reports on,
  matched by URN (or, after an academy conversion, by its predecessor's URN
  from _data/ofsted.json)

Two releases are used. The full academic year comes out each March for the
year before; the autumn and spring terms come out each October for the year
in progress. The latest file of each kind is found through the EES data
catalogue, so a new release is picked up without a code change.

The national/regional/local authority files are a few MB; the school-level
files are 30 to 60 MB compressed and are streamed, keeping only our schools'
rows. DfE publishes three to four times a year; refreshed monthly.

Source: https://explore-education-statistics.service.gov.uk/find-statistics/pupil-absence-in-schools-in-england
"""

import csv
import json
import os
import re
from datetime import datetime, timezone

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "school-absence.json")
SCHOOLS = os.path.join(HERE, "..", "_data", "schools.json")
OFSTED = os.path.join(HERE, "..", "_data", "ofsted.json")

PUBLICATION_ID = "cbbd299f-8297-44bc-92ac-558bcf51f8ad"
PUBLICATION_SLUG = "pupil-absence-in-schools-in-england"
SOURCE_URL = f"https://explore-education-statistics.service.gov.uk/find-statistics/{PUBLICATION_SLUG}"
CATALOGUE = "https://content.explore-education-statistics.service.gov.uk/api/data-set-files"
DOWNLOAD = CATALOGUE + "/{id}/download"

GLOUCESTERSHIRE = "E10000013"
SOUTH_WEST = "E12000009"

# File names have varied ("1_absence_3term_nat_reg_la.csv",
# "Absence_2term_nat_reg_la.csv"), but always say the terms covered and the level.
FILE_KINDS = {
    "full_year_geo": re.compile(r"^(\d+[a-z]?_)?absence_3term_nat_reg_la\.csv$", re.I),
    "full_year_school": re.compile(r"^(\d+[a-z]?_)?absence_3term_school\.csv$", re.I),
    "two_term_geo": re.compile(r"^(\d+[a-z]?_)?absence_2term_nat_reg_la\.csv$", re.I),
    "two_term_school": re.compile(r"^(\d+[a-z]?_)?absence_2term_school\.csv$", re.I),
}

PHASES = {"State-funded primary": "Primary", "State-funded secondary": "Secondary", "Special": "Special"}

MEASURES = {
    "overall": "sess_overall_percent",
    "persistent": "enrolments_pa_10_exact_percent",
    "severe": "enrolments_pa_50_exact_percent",
}


# --- Choosing the files ------------------------------------------------------

def catalogue_entries():
    """Every data file the publication has ever released (a few pages of 40)."""
    entries, page = [], 1
    while True:
        params = {"publicationId": PUBLICATION_ID, "latestOnly": "false", "pageSize": 40, "page": page}
        data = helper.get(CATALOGUE, params=params).json()
        entries += data["results"]
        if page >= data["paging"]["totalPages"]:
            return entries
        page += 1


def pick_files(entries):
    """The most recently published file of each kind, ignoring superseded ones."""
    picked = {}
    for kind, pattern in FILE_KINDS.items():
        matches = [e for e in entries if pattern.match(e["filename"]) and not e.get("isSuperseded")]
        if matches:
            picked[kind] = max(matches, key=lambda e: e["published"])
    return picked


def stream_rows(entry):
    response = helper.get(DOWNLOAD.format(id=entry["id"]), timeout=600, stream=True)
    response.encoding = "utf-8-sig"
    yield from csv.DictReader(response.iter_lines(decode_unicode=True))


# --- Values and labels -------------------------------------------------------

def year_label(period):
    """'202425' -> '2024/25'."""
    return f"{period[:4]}/{period[4:6]}"


def rate(value):
    """A percentage to 2 decimal places, or None where the DfE has suppressed
    or not collected it ('c', 'z', 'x', 'low')."""
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def display(value):
    """One decimal place, from the unrounded figure (rounding the 2-place
    value again could move it the wrong way: 13.2468 -> 13.25 -> 13.3)."""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "–"


def measures(row):
    return {key: rate(row.get(column)) for key, column in MEASURES.items()}


def measure_displays(row):
    return {key: display(row.get(column)) for key, column in MEASURES.items()}


def count(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def pupil_counts(row):
    """Pupil enrolments, and how many were persistently or severely absent."""
    counts = {"enrolments": count(row.get("enrolments")),
              "persistent": count(row.get("enrolments_pa_10_exact")),
              "severe": count(row.get("enrolments_pa_50_exact"))}
    return {**counts, **{key + "_display": "–" if n is None else f"{n:,}" for key, n in counts.items()}}


# --- Area series -------------------------------------------------------------

def area_of(row):
    level = row["geographic_level"]
    if level == "National":
        return "england"
    if level == "Regional" and (row.get("region_code") == SOUTH_WEST or row.get("region_name") == "South West"):
        return "south_west"
    if level == "Local authority" and (row.get("new_la_code") == GLOUCESTERSHIRE
                                       or row.get("la_name") == "Gloucestershire"):
        return "gloucestershire"
    return None


def full_years_only(row):
    # Full-year files label each year five or six half terms; only six-half-term
    # years (2012/13 on) are comparable with today's. Two-term files have no column.
    return row.get("year_breakdown") in (None, "", "Six half terms")


def area_years(rows, phase):
    years = {}
    for row in rows:
        area = area_of(row)
        if not area or row["education_phase"] != phase or not full_years_only(row):
            continue
        years.setdefault(row["time_period"], {})[area] = (measures(row), measure_displays(row), pupil_counts(row))
    return years


def area_entry(period, areas):
    entry = {"year": year_label(period)}
    for area in ("gloucestershire", "south_west", "england"):
        figures, shown, pupils = areas.get(area, (None, None, None))
        entry[area] = figures
        entry[area + "_display"] = shown
        entry[area + "_pupils"] = pupils
    return entry


def area_series(rows):
    """One entry per year for all schools, oldest first."""
    years = area_years(rows, "Total")
    return [area_entry(period, years[period]) for period in sorted(years)]


def by_phase(rows):
    """The latest year for each phase (primary, secondary, special)."""
    out = []
    for phase, label in PHASES.items():
        years = area_years(rows, phase)
        if not years:
            continue
        latest = max(years)
        out.append({"phase": label, **area_entry(latest, years[latest])})
    return out


# --- Schools -----------------------------------------------------------------

def urn_from_url(url):
    return url.rstrip("/").split("/")[-1]


def predecessor_aliases(ofsted):
    """{old URN: current URN} from _data/ofsted.json's predecessor links."""
    return {p["urn"]: urn for urn, school in ofsted.get("schools", {}).items()
            for p in school.get("predecessors") or []}


def school_figures(rows, urns, aliases=None):
    """(latest year label, {urn: figures}) for the schools in `urns`, using only
    the file's latest year so every school is compared over the same period.

    A school that became an academy has a new URN, but the DfE's latest year
    can still be under its old one. A predecessor's row is used only when the
    school has no row of its own that year and exactly one predecessor has."""
    aliases = aliases or {}
    own, inherited = {}, {}
    for row in rows:
        urn = row["school_urn"]
        if urn in urns:
            own.setdefault(row["time_period"], {})[urn] = row
        elif aliases.get(urn) in urns:
            inherited.setdefault(row["time_period"], {}).setdefault(aliases[urn], []).append(row)
    periods = set(own) | set(inherited)
    if not periods:
        return None, {}
    latest = max(periods)
    chosen = {urn: rows_[0] for urn, rows_ in inherited.get(latest, {}).items() if len(rows_) == 1}
    chosen.update(own.get(latest, {}))
    schools = {}
    for urn, row in chosen.items():
        pupils = count(row.get("enrolments"))
        schools[urn] = {"enrolments": pupils, "enrolments_display": "–" if pupils is None else f"{pupils:,}",
                        **measures(row),
                        **{key + "_display": shown for key, shown in measure_displays(row).items()}}
    return year_label(latest), schools


def school_list(our_schools, full_year, two_term):
    listed = []
    for school in sorted(our_schools, key=lambda s: s["name"]):
        urn = urn_from_url(school["urn_url"])
        if urn not in full_year and urn not in two_term:
            continue
        listed.append({"urn": urn, "name": school["name"], "phase": school["phase"],
                       "full_year": full_year.get(urn), "two_term": two_term.get(urn)})
    return listed


# --- Run ---------------------------------------------------------------------

def release_info(entry, period):
    return {
        "release": entry["release"]["title"],
        "release_url": f"{SOURCE_URL}/{entry['release']['slug']}",
        "published": entry["published"][:10],
        "latest_year": period,
    }


def main():
    files = pick_files(catalogue_entries())
    missing = sorted(set(FILE_KINDS) - set(files))
    if missing:
        raise SystemExit(f"No data file found for: {', '.join(missing)}")

    with open(SCHOOLS, encoding="utf-8") as f:
        our_schools = json.load(f)
    urns = {urn_from_url(s["urn_url"]) for s in our_schools}
    with open(OFSTED, encoding="utf-8") as f:
        aliases = predecessor_aliases(json.load(f))

    full_geo = list(stream_rows(files["full_year_geo"]))
    two_geo = list(stream_rows(files["two_term_geo"]))
    full_series, two_series = area_series(full_geo), area_series(two_geo)
    full_period, full_schools = school_figures(stream_rows(files["full_year_school"]), urns, aliases)
    two_period, two_schools = school_figures(stream_rows(files["two_term_school"]), urns, aliases)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Department for Education, Pupil absence in schools in England",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "full_year": {
            **release_info(files["full_year_geo"], full_series[-1]["year"]),
            "school_year": full_period,
            "series": full_series,
            "by_phase": by_phase(full_geo),
        },
        "two_term": {
            **release_info(files["two_term_geo"], two_series[-1]["year"]),
            "school_year": two_period,
            "series": two_series,
            "by_phase": by_phase(two_geo),
        },
        "schools": school_list(our_schools, full_schools, two_schools),
    }

    helper.write_json(OUT, output)
    print(f"Wrote {len(full_series)} full years, {len(two_series)} part years and "
          f"{len(output['schools'])} schools to {OUT}")


if __name__ == "__main__":
    main()
