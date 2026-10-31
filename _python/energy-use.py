#!/usr/bin/env python3
"""Gas and electricity use in Cheltenham, from the Department for Energy
Security and Net Zero's subnational consumption statistics. Writes
_data/energy-use.json.

Four DESNZ workbooks on GOV.UK, each found through the GOV.UK content API:

- electricity and gas use by council, each year since 2005: Cheltenham,
  the South West and England are kept, for homes and for businesses and
  other non-domestic meters;
- home electricity and gas use for every small area (LSOA) in England and
  Wales, latest year only: Cheltenham's 77 are kept and also grouped into
  the ward each one falls in (from _data/small-areas.json).

Gas figures are weather-corrected by DESNZ. All four are published once a
year, in December, so the monthly run looks up the current file links first
and stops when they match the links already in the data file. The two
small-area workbooks are about 50 MB each, so they are only downloaded when
something has changed. Pass --force to rebuild anyway.

    .venv/bin/python _python/energy-use.py [--force]
"""
import io
import json
import re
import sys
from datetime import datetime, timezone

import openpyxl

import helper

DATA = helper.repo_root() / "_data"
OUT = DATA / "energy-use.json"
LICENCE = "Open Government Licence v3.0"

ELEC_URL = "https://www.gov.uk/government/collections/sub-national-electricity-consumption-data"
GAS_URL = "https://www.gov.uk/government/collections/sub-national-gas-consumption-data"
API = "https://www.gov.uk/api/content/government/statistics/"
PAGES = {
    "electricity": ("regional-and-local-authority-electricity-consumption-statistics",
                    "subnational electricity consumption statistics"),
    "gas": ("regional-and-local-authority-gas-consumption-statistics", "subnational gas consumption statistics 2005"),
    "electricity_lsoa": ("lower-and-middle-super-output-areas-electricity-consumption", "lsoa domestic electricity"),
    "gas_lsoa": ("lower-and-middle-super-output-areas-gas-consumption", "lsoa domestic gas"),
}

CHELTENHAM = "E07000078"
PLACES = {"E07000078": "Cheltenham", "E12000009": "South West", "E92000001": "England"}
# Sheets before 2012 use older area codes, so those rows are matched on their
# region and council names instead.
PLACE_NAMES = {("South West", "Cheltenham"): "E07000078", ("South West", "All local authorities"): "E12000009",
               ("England", "All local authorities"): "E92000001"}
SHADES = 6  # colour bands on the map, matching the six blues in themes.css


def attachment_url(slug, wanted):
    """URL of the first .xlsx attachment on a GOV.UK statistics page whose
    title includes `wanted` (case-insensitive)."""
    for attachment in helper.get(API + slug).json()["details"]["attachments"]:
        if wanted in attachment.get("title", "").lower() and attachment["url"].endswith(".xlsx"):
            return attachment["url"]
    raise SystemExit(f"No .xlsx attachment titled '{wanted}' on {API + slug}")


def unchanged(old, files):
    return bool(old) and old.get("files") == files


def heading(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def number(value):
    return float(value) if isinstance(value, (int, float)) else None


def column(names, *wanted):
    for name in wanted:
        if name in names:
            return names.index(name)
    return None


def council_rows(rows):
    """One year's council sheet as {code: {domestic_meters, domestic_gwh,
    non_domestic_gwh, mean_kwh, median_kwh}}. Older years say "Domestic",
    newer ones "All Domestic", and only newer ones have a median."""
    rows = iter(rows)
    for row in rows:
        if row and heading(row[0]) == "Code":
            names = [heading(c) for c in row]
            break
    else:
        return {}

    def col(measure, *labels):
        return column(names, *(f"{measure}: {label}" for label in labels))

    meters = col("Number of meters (thousands)", "All Domestic", "Domestic")
    domestic = col("Total consumption (GWh)", "All Domestic", "Domestic")
    non_domestic = col("Total consumption (GWh)", "All Non-Domestic", "Non-Domestic")
    mean = col("Mean consumption (kWh per meter)", "All Domestic", "Domestic")
    median = col("Median consumption (kWh per meter)", "All Domestic", "Domestic")

    out = {}
    for row in rows:
        code = heading(row[0]) if row else ""
        if code not in PLACES and row and len(row) > 2:
            code = PLACE_NAMES.get((heading(row[1]), heading(row[2])), code)
        if code not in PLACES or code in out:
            continue

        def value(i):
            return number(row[i]) if i is not None and i < len(row) else None

        m, md = value(mean), value(median)
        out[code] = {
            "domestic_meters": round(value(meters) * 1000) if value(meters) is not None else None,
            "domestic_gwh": round(value(domestic), 1) if value(domestic) is not None else None,
            "non_domestic_gwh": round(value(non_domestic), 1) if value(non_domestic) is not None else None,
            "mean_kwh": round(m) if m is not None else None,
            "median_kwh": round(md) if md is not None else None,
        }
    return out


def small_area_rows(rows):
    """Cheltenham's rows of a small-area sheet as {lsoa: {meters, kwh,
    mean_kwh, median_kwh}}."""
    rows = iter(rows)
    for row in rows:
        if row and heading(row[0]) == "Local authority code":
            names = [heading(c) for c in row]
            break
    else:
        return {}
    code_i = names.index("LSOA code")
    meters_i = next(i for i, n in enumerate(names) if n.startswith("Number of meters"))
    total_i = next(i for i, n in enumerate(names) if n.startswith("Total consumption"))
    mean_i = next(i for i, n in enumerate(names) if n.startswith("Mean consumption"))
    median_i = next(i for i, n in enumerate(names) if n.startswith("Median consumption"))
    out = {}
    for row in rows:
        if not row or row[0] != CHELTENHAM:
            continue
        out[row[code_i]] = {
            "meters": int(row[meters_i] or 0),
            "kwh": number(row[total_i]),
            "mean_kwh": round(row[mean_i]) if number(row[mean_i]) is not None else None,
            "median_kwh": round(row[median_i]) if number(row[median_i]) is not None else None,
        }
    return out


def by_ward(lsoas, use):
    """Small-area use added up for the ward each small area sits in, with
    the mean per meter worked out from the totals."""
    wards = {}
    for lsoa in lsoas:
        row = use.get(lsoa["code"])
        if not row or not row.get("meters") or row.get("kwh") is None:
            continue
        ward = wards.setdefault(lsoa["ward_code"], {"meters": 0, "kwh": 0.0})
        ward["meters"] += row["meters"]
        ward["kwh"] += row["kwh"]
    for ward in wards.values():
        ward["mean_kwh"] = round(ward["kwh"] / ward["meters"])
    return wards


def band_edges(values):
    """Five cut points splitting the values into six equal-sized bands, each
    larger than the last and the first above the lowest value."""
    ordered = sorted(values)
    edges = []
    for i in range(1, SHADES):
        edge = round(ordered[min(len(ordered) - 1, round(i * len(ordered) / SHADES))], -1)
        floor = edges[-1] + 10 if edges else ordered[0] + 10
        edges.append(int(max(edge, floor)))
    return edges


def workbook(url):
    return openpyxl.load_workbook(io.BytesIO(helper.get(url, timeout=300).content), read_only=True, data_only=True)


def year_sheets(book):
    return sorted((int(n), n) for n in book.sheetnames if n.strip().isdigit())


def council_history(book):
    return {year: council_rows(book[name].iter_rows(values_only=True)) for year, name in year_sheets(book)}


def latest_small_areas(book):
    year, name = year_sheets(book)[-1]
    return year, small_area_rows(book[name].iter_rows(values_only=True))


def display(n):
    return f"{n:,}" if n is not None else None


def borough_summary(elec, gas, year):
    e, g = elec[year][CHELTENHAM], gas[year][CHELTENHAM]
    first = min(y for y in elec if CHELTENHAM in elec[y])
    e0, g0 = elec[first][CHELTENHAM], gas[first][CHELTENHAM]

    def change(now, then):
        return round(100 * (now - then) / then) if now is not None and then else None

    return {
        "first_year": first,
        "electricity_gwh": round(e["domestic_gwh"] + e["non_domestic_gwh"]),
        "electricity_domestic_gwh": round(e["domestic_gwh"]),
        "electricity_non_domestic_gwh": round(e["non_domestic_gwh"]),
        "electricity_domestic_meters_display": display(e["domestic_meters"]),
        "electricity_mean_kwh": e["mean_kwh"],
        "electricity_mean_kwh_display": display(e["mean_kwh"]),
        "electricity_median_kwh_display": display(e["median_kwh"]),
        "electricity_mean_change_pct": change(e["mean_kwh"], e0["mean_kwh"]),
        "gas_gwh": round(g["domestic_gwh"] + g["non_domestic_gwh"]),
        "gas_domestic_gwh": round(g["domestic_gwh"]),
        "gas_non_domestic_gwh": round(g["non_domestic_gwh"]),
        "gas_domestic_meters_display": display(g["domestic_meters"]),
        "gas_mean_kwh_display": display(g["mean_kwh"]),
        "gas_median_kwh_display": display(g["median_kwh"]),
        "gas_mean_change_pct": change(g["mean_kwh"], g0["mean_kwh"]),
    }


def history(elec, gas):
    years = []
    for year in sorted(set(elec) & set(gas)):
        e, g = elec[year].get(CHELTENHAM), gas[year].get(CHELTENHAM)
        if not (e and g):
            continue
        years.append({
            "year": year,
            "electricity_domestic_gwh": e["domestic_gwh"],
            "electricity_non_domestic_gwh": e["non_domestic_gwh"],
            "gas_domestic_gwh": g["domestic_gwh"],
            "gas_non_domestic_gwh": g["non_domestic_gwh"],
            "electricity_mean_kwh": {PLACES[c]: elec[year][c]["mean_kwh"] for c in PLACES if c in elec[year]},
            "gas_mean_kwh": {PLACES[c]: gas[year][c]["mean_kwh"] for c in PLACES if c in gas[year]},
        })
    return years


def compare(elec, gas, year):
    return [{
        "name": PLACES[code],
        "electricity_mean_kwh_display": display(elec[year][code]["mean_kwh"]),
        "electricity_median_kwh_display": display(elec[year][code]["median_kwh"]),
        "gas_mean_kwh_display": display(gas[year][code]["mean_kwh"]),
        "gas_median_kwh_display": display(gas[year][code]["median_kwh"]),
        "electricity_mean_kwh": elec[year][code]["mean_kwh"],
        "gas_mean_kwh": gas[year][code]["mean_kwh"],
    } for code in PLACES if code in elec[year] and code in gas[year]]


def area_row(base, elec, gas):
    row = dict(base)
    for key, use in (("electricity", elec), ("gas", gas)):
        row[f"{key}_meters"] = use.get("meters") if use else None
        row[f"{key}_meters_display"] = display(use.get("meters")) if use else None
        row[f"{key}_mean_kwh"] = use.get("mean_kwh") if use else None
        row[f"{key}_mean_kwh_display"] = display(use.get("mean_kwh")) if use else None
        if use and "median_kwh" in use:
            row[f"{key}_median_kwh_display"] = display(use.get("median_kwh"))
    return row


def level(areas):
    return {
        "electricity_edges": band_edges([a["electricity_mean_kwh"] for a in areas if a["electricity_mean_kwh"]]),
        "gas_edges": band_edges([a["gas_mean_kwh"] for a in areas if a["gas_mean_kwh"]]),
        "areas": areas,
    }


def main():
    force = "--force" in sys.argv[1:]
    files = {key: attachment_url(slug, wanted) for key, (slug, wanted) in PAGES.items()}
    old = json.loads(OUT.read_text()) if OUT.exists() else None
    if unchanged(old, files) and not force:
        print("Energy use: no new DESNZ files, nothing to do")
        return

    elec = council_history(workbook(files["electricity"]))
    gas = council_history(workbook(files["gas"]))
    year = max(y for y in set(elec) & set(gas) if CHELTENHAM in elec[y] and CHELTENHAM in gas[y])
    lsoa_year, elec_lsoa = latest_small_areas(workbook(files["electricity_lsoa"]))
    gas_year, gas_lsoa = latest_small_areas(workbook(files["gas_lsoa"]))
    if gas_year != lsoa_year:
        raise SystemExit(f"Small-area electricity ({lsoa_year}) and gas ({gas_year}) years differ")

    small = json.loads((DATA / "small-areas.json").read_text())["lsoas"]
    wards_index = json.loads((DATA / "wards" / "index.json").read_text())["wards"]
    missing = [a["code"] for a in small if a["code"] not in elec_lsoa]
    if missing:
        raise SystemExit(f"Small areas missing from the DESNZ electricity file: {missing}")

    lsoas = [area_row({"code": a["code"], "name": a["name"], "ward_name": a["ward_name"], "boundary": a["boundary"]},
                      elec_lsoa.get(a["code"]), gas_lsoa.get(a["code"])) for a in small]
    elec_ward, gas_ward = by_ward(small, elec_lsoa), by_ward(small, gas_lsoa)
    wards = [area_row({"code": w["code"], "name": w["name"], "slug": w["slug"], "boundary": [w["boundary"]]},
                      elec_ward.get(w["code"]), gas_ward.get(w["code"])) for w in wards_index]

    helper.write_json(OUT, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Subnational electricity and gas consumption statistics (Department for Energy Security and Net Zero)",
        "source_url": ELEC_URL,
        "gas_source_url": GAS_URL,
        "licence": LICENCE,
        "files": files,
        "year": year,
        "small_area_year": lsoa_year,
        "borough": borough_summary(elec, gas, year),
        "compare": compare(elec, gas, year),
        "years": history(elec, gas),
        "lsoa": level(lsoas),
        "ward": level(wards),
    })
    print(f"Energy use: {year} council figures, {len(lsoas)} small areas and {len(wards)} wards for {lsoa_year}")


if __name__ == "__main__":
    main()
