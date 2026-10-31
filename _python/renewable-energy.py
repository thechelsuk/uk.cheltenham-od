#!/usr/bin/env python3
"""Renewable electricity in and around Cheltenham, from the Department for
Energy Security and Net Zero (DESNZ). Writes _data/renewable-energy.json.

Two DESNZ sources on GOV.UK, each found through the GOV.UK content API so a
new release is picked up without changing this script:

- Regional Renewable Statistics: one workbook with the number of
  installations, installed capacity (MW) and generation (MWh) for every
  council, by technology, each year since 2014. Cheltenham and the other
  Gloucestershire districts are kept. Published every September.
- Renewable Energy Planning Database (REPD): every renewable electricity
  and storage project of 150 kW or more that has been through planning,
  with its status and grid reference. Sites within the "area" distance band
  of the town centre are kept. Published quarterly.

The monthly run looks up the current file links first and stops when both
match the links already in the data file, so the workbooks are only
downloaded when DESNZ publishes something new. Pass --force to rebuild
anyway (after changing this script, say).

    .venv/bin/python _python/renewable-energy.py [--force]
"""
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone

import openpyxl
from pyproj import Transformer

import config
import helper

OUT = helper.repo_root() / "_data" / "renewable-energy.json"
LICENCE = "Open Government Licence v3.0"

STATS_URL = "https://www.gov.uk/government/statistics/regional-renewable-statistics"
STATS_API = "https://www.gov.uk/api/content/government/statistics/regional-renewable-statistics"
STATS_FILE_TITLE = "renewable electricity by local authority"
REPD_URL = "https://www.gov.uk/government/publications/renewable-energy-planning-database-quarterly-extract"
REPD_API = "https://www.gov.uk/api/content/government/publications/renewable-energy-planning-database-quarterly-extract"

CHELTENHAM = "E07000078"
# Gloucestershire's six districts, for comparison.
GLOUCESTERSHIRE = ("E07000078", "E07000079", "E07000080", "E07000081", "E07000082", "E07000083")
RADIUS_MILES = config.REPD_RADIUS_MILES

STATUS_GROUPS = {
    "Operational": "Operational",
    "Under Construction": "Under construction",
    "Awaiting Construction": "Approved",
    "Application Submitted": "In planning",
    "Appeal Lodged": "In planning",
    "Revised": "In planning",
    "No Application Required": "Approved",
}
STATUS_ORDER = ["Operational", "Under construction", "Approved", "In planning", "Refused, withdrawn or ended"]
TECHNOLOGIES = {
    "Solar Photovoltaics": "Solar",
    "Battery": "Battery storage",
    "Wind Onshore": "Onshore wind",
    "Biomass (dedicated)": "Biomass",
    "Biomass (co-firing)": "Biomass",
    "EfW Incineration": "Energy from waste",
    "Small Hydro": "Hydro",
    "Large Hydro": "Hydro",
}

_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def attachment_url(api, wanted):
    """URL of the first attachment on a GOV.UK page whose title includes `wanted`
    (case-insensitive), and that attachment's title."""
    for attachment in helper.get(api).json()["details"]["attachments"]:
        if wanted in attachment.get("title", "").lower():
            return attachment["url"], attachment["title"]
    raise SystemExit(f"No attachment titled '{wanted}' on {api}")


def unchanged(old, files):
    """Whether the data file was built from exactly these source files."""
    return bool(old) and old.get("files") == files


def number(value):
    """A cell as a float, or None when blank or suppressed ([X], [x], [c])."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def heading(text):
    """A column heading without its [note n] markers and extra spaces."""
    return re.sub(r"\s+", " ", re.sub(r"\[note \d+\]", "", str(text or ""))).strip()


def council_table(rows):
    """One council sheet as {code: {technology: value, "households": n}}.
    The header row is the one starting "Local Authority Code"; technology
    columns are those between the households column and Total (inclusive)."""
    rows = iter(rows)
    for row in rows:
        if row and str(row[0] or "").startswith("Local Authority Code"):
            names = [heading(c) for c in row]
            break
    else:
        return {}
    first = next(i for i, n in enumerate(names) if n.startswith("Estimated number of households"))
    last = names.index("Total")
    table = {}
    for row in rows:
        code = str(row[0] or "").strip() if row else ""
        if not re.fullmatch(r"[ENSW]\d{8}", code):
            continue
        entry = {"name": row[1], "households": number(row[first])}
        for i in range(first + 1, last + 1):
            entry[names[i]] = number(row[i])
        table[code] = entry
    return table


def read_workbook(content):
    """{year: {"Sites"|"Capacity"|"Generation": council_table}} for every
    year sheet in the workbook."""
    book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    years = {}
    for name in book.sheetnames:
        match = re.fullmatch(r"LA - (Sites|Capacity|Generation),? (\d{4})", name.strip())
        if match:
            years.setdefault(int(match.group(2)), {})[match.group(1)] = council_table(book[name].iter_rows(values_only=True))
    return years


def per_thousand(sites, households):
    return round(1000 * sites / households, 1) if households else None


def council_summary(years):
    latest = max(years)
    tables = years[latest]
    sites, capacity, generation = (tables[k][CHELTENHAM] for k in ("Sites", "Capacity", "Generation"))
    technologies = [k for k in sites if k not in ("name", "households", "Total")]

    by_technology = []
    for tech in technologies:
        n, mw = sites.get(tech) or 0, capacity.get(tech) or 0
        if not n and not mw:
            continue
        mwh = generation.get(tech)
        by_technology.append({
            "name": tech,
            "sites": int(n),
            "sites_display": f"{int(n):,}",
            "capacity_mw": round(mw, 2),
            "generation_mwh": round(mwh) if mwh is not None else None,
            "generation_display": f"{round(mwh):,}" if mwh is not None else None,
        })

    history = []
    for year in sorted(years):
        t = years[year]
        s, c, g = t["Sites"].get(CHELTENHAM), t["Capacity"].get(CHELTENHAM), t["Generation"].get(CHELTENHAM)
        if not (s and c):
            continue
        history.append({
            "year": year,
            "sites": int(s["Total"] or 0),
            "solar_sites": int(s.get("Solar PV") or 0),
            "capacity_mw": round(c["Total"] or 0, 2),
            "solar_capacity_mw": round(c.get("Solar PV") or 0, 2),
            "generation_mwh": round(g["Total"]) if g and g["Total"] is not None else None,
        })
        history[-1]["sites_display"] = f"{history[-1]['sites']:,}"
        mwh = history[-1]["generation_mwh"]
        history[-1]["generation_display"] = f"{mwh:,}" if mwh is not None else None

    compare = []
    for code in GLOUCESTERSHIRE:
        s, c = tables["Sites"].get(code), tables["Capacity"].get(code)
        if not (s and c):
            continue
        households = int(s["households"] or 0)
        compare.append({
            "code": code,
            "name": s["name"],
            "households": households,
            "households_display": f"{households:,}",
            "sites": int(s["Total"] or 0),
            "sites_display": f"{int(s['Total'] or 0):,}",
            "per_1000_households": per_thousand(s["Total"] or 0, households),
            "capacity_mw": round(c["Total"] or 0, 1),
            "solar_capacity_mw": round(c.get("Solar PV") or 0, 1),
        })
    compare.sort(key=lambda r: -(r["per_1000_households"] or 0))
    rank = next(i for i, r in enumerate(compare, 1) if r["code"] == CHELTENHAM)

    total_sites, households = int(sites["Total"] or 0), int(sites["households"] or 0)
    total_mwh = generation.get("Total")
    first = history[0]
    return {
        "year": latest,
        "first_year": first["year"],
        "borough": {
            "households": households,
            "households_display": f"{households:,}",
            "sites": total_sites,
            "sites_display": f"{total_sites:,}",
            "solar_sites": int(sites.get("Solar PV") or 0),
            "solar_sites_display": f"{int(sites.get('Solar PV') or 0):,}",
            "solar_share_pct": round(100 * (sites.get("Solar PV") or 0) / total_sites, 1) if total_sites else None,
            "per_1000_households": per_thousand(total_sites, households),
            "gloucestershire_rank": helper.ord(rank),
            "gloucestershire_districts": len(compare),
            "average_kw": round(1000 * (capacity["Total"] or 0) / total_sites, 1) if total_sites else None,
            "capacity_mw": round(capacity["Total"] or 0, 1),
            "generation_mwh": round(total_mwh) if total_mwh is not None else None,
            "generation_display": f"{round(total_mwh):,}" if total_mwh is not None else None,
            "capacity_growth": round((capacity["Total"] or 0) / first["capacity_mw"], 1) if first["capacity_mw"] else None,
            "first_capacity_mw": round(first["capacity_mw"], 1),
        },
        "by_technology": by_technology,
        "years": history,
        "compare": compare,
    }


def iso(text):
    text = (text or "").strip()
    try:
        return datetime.strptime(text, "%d/%m/%Y").date().isoformat() if text else None
    except ValueError:
        return None


def status_group(status):
    return STATUS_GROUPS.get((status or "").strip(), "Refused, withdrawn or ended")


def tidy(text):
    return re.sub(r"\s+", " ", text or "").strip()


def nearby_sites(rows, radius_miles):
    """REPD rows within radius_miles of the town centre, nearest first."""
    sites = []
    for row in rows:
        try:
            x, y = float(tidy(row.get("X-coordinate"))), float(tidy(row.get("Y-coordinate")))
        except ValueError:
            continue
        lng, lat = _to_wgs84.transform(x, y)
        miles = helper.miles_from_centre(lat, lng)
        if miles > radius_miles:
            continue
        technology = tidy(row.get("Technology Type"))
        detail = tidy(row.get("Development Status")) or tidy(row.get("Development Status (short)"))
        sites.append({
            "ref": tidy(row.get("Ref ID")),
            "name": tidy(row.get("Site Name")),
            "operator": tidy(row.get("Operator (or Applicant)")) or None,
            "technology": TECHNOLOGIES.get(technology, technology),
            "capacity_mw": number(tidy(row.get("Installed Capacity (MWelec)"))),
            "status": status_group(row.get("Development Status (short)")),
            "status_detail": detail,
            "council": tidy(row.get("Planning Authority")),
            "planning_ref": tidy(row.get("Planning Application Reference")) or None,
            "operational": iso(row.get("Operational")),
            "updated": iso(row.get("Record Last Updated (dd/mm/yyyy)")),
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "miles": round(miles, 1),
        })
    sites.sort(key=lambda s: (s["miles"], s["name"]))
    return sites


def read_repd(content):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(row for row in reader if "Site Name" in row)
    return [dict(zip(header, row)) for row in reader]


def repd_summary(sites, title):
    counts = {group: sum(1 for s in sites if s["status"] == group) for group in STATUS_ORDER}
    capacity = {group: round(sum(s["capacity_mw"] or 0 for s in sites if s["status"] == group), 1) for group in STATUS_ORDER}
    edition = re.search(r"\):\s*(.+?)\s*\(", title)
    return {
        "edition": edition.group(1) if edition else None,
        "radius_miles": RADIUS_MILES,
        "statuses": STATUS_ORDER,
        "counts": counts,
        "capacity_mw": capacity,
        "in_cheltenham": sum(1 for s in sites if s["council"] == "Cheltenham"),
        "sites": sites,
    }


def main():
    force = "--force" in sys.argv[1:]
    stats_file, _ = attachment_url(STATS_API, STATS_FILE_TITLE)
    repd_file, repd_title = attachment_url(REPD_API, "(csv)")
    files = {"council": stats_file, "repd": repd_file}

    old = json.loads(OUT.read_text()) if OUT.exists() else None
    if unchanged(old, files) and not force:
        print("Renewable energy: no new DESNZ files, nothing to do")
        return

    council = council_summary(read_workbook(helper.get(stats_file, timeout=120).content))
    sites = nearby_sites(read_repd(helper.get(repd_file, timeout=120).content), RADIUS_MILES)

    written = helper.write_json(OUT, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Regional Renewable Statistics (Department for Energy Security and Net Zero)",
        "source_url": STATS_URL,
        "repd_source": "Renewable Energy Planning Database (Department for Energy Security and Net Zero)",
        "repd_source_url": REPD_URL,
        "licence": LICENCE,
        "files": files,
        **council,
        "repd": repd_summary(sites, repd_title),
    })
    print(f"Renewable energy: {council['borough']['sites_display']} installations in {council['year']}, "
          f"{len(sites)} planning database sites within {RADIUS_MILES} miles"
          f"{'' if written else ' (unchanged)'}")


if __name__ == "__main__":
    main()
