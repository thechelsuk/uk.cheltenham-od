#!/usr/bin/env python3
"""Fetch Cheltenham Borough Council's business rates lists of occupied and
empty non-domestic properties and write _data/business-rates.json:

- the latest release's counts of occupied and empty properties, by property
  type and by rateable value band, with the reliefs and empty-property
  exemptions the council records
- every empty property with its address, type, rateable value, the reason
  it pays no empty rates (if any), when it became empty, and in how many of
  the council's releases it has been empty
- each postcode's properties for the map: rateable value, type and whether
  empty (addresses only for empty properties)
- the counts for every release, kept from earlier runs once the council
  stops linking a release

Ratepayer names are never read into the output: the council already leaves
out sole traders and individuals, and some remaining names still point to a
person. Holiday lets ("Holiday Unit" and "Camping sites, holiday centres
etc.") are counted but not listed or mapped, as many are at or next to
someone's home.

The council publishes a new pair of spreadsheets a few times a year (so far
January, April, June and October), so this runs weekly."""
import io
import json
import os
import re
import statistics
from datetime import datetime, timezone

import openpyxl

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "business-rates.json")

SITE = "https://www.cheltenham.gov.uk"
SOURCE_URL = f"{SITE}/business-and-licensing/business-rates-and-rate-relief/business-rates-data/"
LINK = re.compile(r'href="(/media/[^"]+/([a-z]+)-(\d{4})-(empty|occupied)-properties\.xlsx)"', re.I)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}

HOLIDAY_TYPES = {"Holiday Unit", "Camping sites, holiday centres etc."}
REQUIRED = ["PropertyRef", "PropAddress1", "PropPostCode", "VO-Analysis-Desc", "RV", "StartDate"]
# Rateable value bands: the council's small business rate relief limits
# (full relief up to £12,000, tapering to £15,000), the small business
# multiplier (below £51,000) and the large multiplier (£500,000 and above).
BAND_UPPER = [12000, 15000, 50999, 99999, 499999]
BAND_LABELS = ["Up to £12,000", "£12,001 to £15,000", "£15,001 to £50,999", "£51,000 to £99,999",
               "£100,000 to £499,999", "£500,000 and above"]
LOCAL_POSTCODE = re.compile(r"GL5[0-5] ")
MIN_LOCAL_SHARE = 0.9
MIN_PROPERTIES = 3000
TOP_TYPES = 12
GEOCODE_BATCH = 100


def find_releases(html):
    """Each release with both an empty and an occupied list, newest first."""
    found = {}
    for href, month, year, kind in LINK.findall(html):
        month_no = MONTHS.get(month.lower())
        if not month_no:
            continue
        key = f"{year}-{month_no:02d}"
        rel = found.setdefault(key, {"key": key, "name": f"{month.capitalize()} {year}"})
        rel[f"{kind.lower()}_url"] = SITE + href
    complete = [r for r in found.values() if "empty_url" in r and "occupied_url" in r]
    return sorted(complete, key=lambda r: r["key"], reverse=True)


def parse_rv(value):
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return int(float(str(value).replace(",", "").replace("£", "").strip() or 0))


def parse_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if not value:
        return None
    return datetime.strptime(str(value).strip(), "%d/%m/%Y").date().isoformat()


def clean_postcode(value):
    """Upper case with one space before the inward code; a letter O typed for
    a zero at the start of the inward code is corrected."""
    if not value:
        return None
    text = re.sub(r"\s+", "", str(value).upper())
    if len(text) < 5:
        return None
    outward, inward = text[:-3], text[-3:]
    if inward[0] == "O":
        inward = "0" + inward[1:]
    if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?", outward) or not re.fullmatch(r"\d[A-Z]{2}", inward):
        return None
    return f"{outward} {inward}"


def read_sheet(content):
    """The first sheet of a council workbook as property dicts, one per
    property reference, without the ratepayer's name."""
    ws = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head = [str(c).strip() if c is not None else None for c in next(rows)]
    missing = [c for c in REQUIRED if c not in head]
    if missing:
        raise SystemExit(f"Business rates sheet is missing columns {missing}")
    col = {name: i for i, name in enumerate(head) if name}
    out, seen = [], set()
    for row in rows:
        def cell(name, row=row):
            i = col.get(name)
            return row[i] if i is not None and i < len(row) else None
        ref = cell("PropertyRef")
        if ref is None or str(ref).strip() == "":
            continue
        ref = str(ref).strip()
        if ref in seen:
            continue
        seen.add(ref)
        parts = [str(cell(f"PropAddress{i}")).strip() for i in range(1, 6) if cell(f"PropAddress{i}")]
        out.append({
            "ref": ref,
            "address": ", ".join(p for p in parts if p),
            "postcode": clean_postcode(cell("PropPostCode")),
            "type": (cell("VO-Analysis-Desc") or "Not stated").strip(),
            "rv": parse_rv(cell("RV")),
            "since": parse_date(cell("StartDate")),
            "reason": (cell("ExempDesc") or "").strip() or None,
            "relief": (cell("ReliefDesc") or "").strip() or None,
            "sbr": str(cell("SBRRelief") or "").strip().lower() in ("yes", "y"),
        })
    return out


def addresses_look_local(props):
    """True when nearly every postcode is a Cheltenham one. A release whose
    address columns hold ratepayers' billing addresses fails this."""
    codes = [p["postcode"] for p in props if p.get("postcode")]
    if not codes:
        return False
    return sum(1 for c in codes if LOCAL_POSTCODE.match(c)) / len(codes) >= MIN_LOCAL_SHARE


def band_of(rv):
    if not rv:
        return None
    for i, upper in enumerate(BAND_UPPER):
        if rv <= upper:
            return i
    return len(BAND_UPPER)


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0


def money(n):
    return f"£{n:,}"


def counted(counter):
    return [{"name": name, "count": n, "count_display": f"{n:,}"}
            for name, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def release_entry(release, occupied, empty):
    occ = [p for p in occupied if p["type"] not in HOLIDAY_TYPES]
    emp = [p for p in empty if p["type"] not in HOLIDAY_TYPES]
    total = len(occ) + len(emp)
    return {"key": release["key"], "name": release["name"], "occupied": len(occ), "empty": len(emp),
            "occupied_display": f"{len(occ):,}", "empty_display": f"{len(emp):,}",
            "empty_pct": pct(len(emp), total), "empty_pct_display": f"{pct(len(emp), total)}%",
            "empty_refs": sorted(p["ref"] for p in emp)}


def build(occupied, empty, release, history, coords):
    """The data file's content for the latest release, given earlier
    releases' entries and postcode coordinates."""
    holiday = sum(1 for p in occupied + empty if p["type"] in HOLIDAY_TYPES)
    occ = [p for p in occupied if p["type"] not in HOLIDAY_TYPES]
    emp = [p for p in empty if p["type"] not in HOLIDAY_TYPES]
    total = len(occ) + len(emp)
    current = release_entry(release, occupied, empty)
    releases = sorted({r["key"]: r for r in history + [current]}.values(), key=lambda r: r["key"])
    empty_sets = [set(r.get("empty_refs", [])) for r in releases]

    rvs = [p["rv"] for p in occ + emp if p["rv"]]
    summary = {
        "properties": total, "properties_display": f"{total:,}",
        "occupied": len(occ), "occupied_display": f"{len(occ):,}",
        "empty": len(emp), "empty_display": f"{len(emp):,}",
        "empty_pct": pct(len(emp), total), "empty_pct_display": f"{pct(len(emp), total)}%",
        "holiday_lets": holiday, "holiday_lets_display": f"{holiday:,}",
        "awaiting_rv": sum(1 for p in occ + emp if not p["rv"]),
        "total_rv": sum(rvs), "total_rv_display": money(sum(rvs)),
        "median_rv": int(statistics.median(rvs)) if rvs else 0,
        "median_rv_display": money(int(statistics.median(rvs))) if rvs else "£0",
        "empty_rv": sum(p["rv"] for p in emp), "empty_rv_display": money(sum(p["rv"] for p in emp)),
    }
    summary["awaiting_rv_display"] = f"{summary['awaiting_rv']:,}"

    bands = []
    for i, label in enumerate(BAND_LABELS):
        o = sum(1 for p in occ if band_of(p["rv"]) == i)
        e = sum(1 for p in emp if band_of(p["rv"]) == i)
        bands.append({"band": i, "label": label, "occupied": o, "empty": e, "total": o + e,
                      "occupied_display": f"{o:,}", "empty_display": f"{e:,}", "total_display": f"{o + e:,}",
                      "empty_pct": pct(e, o + e), "empty_pct_display": f"{pct(e, o + e)}%"})

    by_type = {}
    for p, status in [(p, "occupied") for p in occ] + [(p, "empty") for p in emp]:
        t = by_type.setdefault(p["type"], {"type": p["type"], "occupied": 0, "empty": 0, "rvs": []})
        t[status] += 1
        if p["rv"]:
            t["rvs"].append(p["rv"])
    ranked = sorted(by_type.values(), key=lambda t: (-(t["occupied"] + t["empty"]), t["type"]))
    top, rest = ranked[:TOP_TYPES], ranked[TOP_TYPES:]
    if rest:
        top.append({"type": "Other types", "occupied": sum(t["occupied"] for t in rest),
                    "empty": sum(t["empty"] for t in rest), "rvs": [v for t in rest for v in t["rvs"]]})
    types = []
    for t in top:
        n = t["occupied"] + t["empty"]
        med = int(statistics.median(t["rvs"])) if t["rvs"] else 0
        types.append({"type": t["type"], "occupied": t["occupied"], "empty": t["empty"], "total": n,
                      "occupied_display": f"{t['occupied']:,}", "empty_display": f"{t['empty']:,}",
                      "total_display": f"{n:,}", "empty_pct": pct(t["empty"], n),
                      "empty_pct_display": f"{pct(t['empty'], n)}%", "median_rv": med,
                      "median_rv_display": money(med) if med else "None yet"})

    empty_out = []
    for p in sorted(emp, key=lambda p: (p["since"] or "", p["address"])):
        lat, lon = coords.get(p["postcode"], (None, None))
        empty_out.append({"ref": p["ref"], "address": p["address"], "postcode": p["postcode"], "type": p["type"],
                          "rv": p["rv"], "rv_display": money(p["rv"]) if p["rv"] else "Awaiting value",
                          "band": band_of(p["rv"]), "reason": p["reason"] or "None (empty rates payable)",
                          "since": p["since"], "lat": lat, "lon": lon,
                          "releases_empty": sum(1 for s in empty_sets if p["ref"] in s)})

    # Map points, one per postcode. Each property is [rateable value, index
    # into map_types, index into the empty list or None], to keep the page small.
    map_types = sorted({p["type"] for p in occ + emp})
    type_index = {name: i for i, name in enumerate(map_types)}
    empty_index = {e["ref"]: i for i, e in enumerate(empty_out)}
    summary["release_count"] = len(releases)
    summary["empty_every_release"] = sum(1 for e in empty_out if e["releases_empty"] == len(releases))
    summary["empty_every_release_display"] = f"{summary['empty_every_release']:,}"

    postcodes = {}
    for p in occ + emp:
        if p["postcode"] not in coords:
            continue
        lat, lon = coords[p["postcode"]]
        entry = postcodes.setdefault(p["postcode"], {"postcode": p["postcode"], "lat": lat, "lon": lon, "p": []})
        entry["p"].append([p["rv"], type_index[p["type"]], empty_index.get(p["ref"])])

    return {
        "release": {"key": release["key"], "name": release["name"],
                    "empty_url": release.get("empty_url"), "occupied_url": release.get("occupied_url")},
        "summary": summary,
        "bands": bands,
        "band_upper": BAND_UPPER,
        "by_type": types,
        "reliefs": counted(_count(p["relief"] for p in occ if p["relief"])),
        "small_business_relief": sum(1 for p in occ if p["sbr"]),
        "small_business_relief_display": f"{sum(1 for p in occ if p['sbr']):,}",
        "exemptions": counted(_count(p["reason"] or "None (empty rates payable)" for p in emp)),
        "releases": releases,
        "empty": empty_out,
        "map_types": map_types,
        "postcodes": sorted(postcodes.values(), key=lambda pc: pc["postcode"]),
        "unmapped": sum(1 for p in occ + emp if p["postcode"] not in coords),
    }


def _count(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def check(occupied, empty):
    both = {p["ref"] for p in occupied} & {p["ref"] for p in empty}
    if both:
        raise SystemExit(f"{len(both)} properties are on both the empty and occupied lists, e.g. {sorted(both)[:3]}")
    if len(occupied) + len(empty) < MIN_PROPERTIES:
        raise SystemExit(f"Only {len(occupied) + len(empty)} properties: far too few for Cheltenham")


def geocode(postcodes):
    found = {}
    ordered = sorted(postcodes)
    for i in range(0, len(ordered), GEOCODE_BATCH):
        found.update(helper.geocode_postcodes(ordered[i:i + GEOCODE_BATCH]))
    return found


def download(url):
    resp = helper.get(url, timeout=60)
    resp.raise_for_status()
    return read_sheet(resp.content)


def previous_releases():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f).get("releases", [])
    except (FileNotFoundError, ValueError, AttributeError):
        return []


def main():
    page = helper.get(SOURCE_URL, timeout=30)
    page.raise_for_status()
    releases = find_releases(page.text)
    if not releases:
        raise SystemExit(f"No business rates spreadsheets linked from {SOURCE_URL}")

    history = {r["key"]: r for r in previous_releases()}
    latest = releases[0]
    lists = {}
    for rel in releases:
        occupied, empty = download(rel["occupied_url"]), download(rel["empty_url"])
        check(occupied, empty)
        lists[rel["key"]] = (occupied, empty)
        if rel is not latest:
            history[rel["key"]] = release_entry(rel, occupied, empty)

    occupied, empty = lists[latest["key"]]
    if not (addresses_look_local(occupied) and addresses_look_local(empty)):
        raise SystemExit(f"{latest['name']}: postcodes are mostly outside Cheltenham, so the address columns "
                         "probably hold ratepayers' billing addresses; not publishing them")
    history.pop(latest["key"], None)

    coords = geocode({p["postcode"] for p in occupied + empty if p["postcode"]})
    body = build(occupied, empty, latest, list(history.values()), coords)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Cheltenham Borough Council",
        "source_url": SOURCE_URL,
        **body,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {latest['name']}: {body['summary']['occupied']} occupied, {body['summary']['empty']} empty, "
          f"{body['unmapped']} without a mapped postcode, {len(body['releases'])} releases to {OUT}")


if __name__ == "__main__":
    main()
