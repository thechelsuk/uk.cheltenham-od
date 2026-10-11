#!/usr/bin/env python3
"""Energy Performance Certificate (EPC) ratings for homes in Cheltenham, from
the Energy Performance of Buildings Register's domestic search API
(Get energy performance of buildings data, MHCLG). Writes _data/epc.json.

Every domestic certificate lodged for the Cheltenham council area is
fetched (about 66,000, in pages of 5,000), and each home keeps only its
latest certificate, matched on UPRN or, without one, on address and
postcode. Homes are then placed by their postcode's centre (postcodes.io)
into the small areas (LSOAs) and wards the crime map uses, and each area
gets its A to G mix, the share rated C or better (C+) and its median rating.

Postcodes and addresses carry Ordnance Survey and Royal Mail terms, so they
are only used in memory to place homes; the output holds area totals only.

Needs EPC_KEY (a bearer token from the service) in the environment or the
repository's .env. Runs monthly.

    .venv/bin/python _python/epc.py
"""
import json
import os
from datetime import datetime, timezone

import helper

API = "https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search"
SOURCE = "Energy Performance of Buildings Register (MHCLG)"
SOURCE_URL = "https://get-energy-performance-data.communities.gov.uk/"
COUNCIL = "Cheltenham"
PAGE_SIZE = 5000
GEOCODE_BATCH = 100
BANDS = "ABCDEFG"
SHADES = 6  # colour bands on the map, matching the six blues in themes.css


def load_key():
    env_file = helper.repo_root() / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip("\"'"))
    key = os.environ.get("EPC_KEY")
    if not key:
        raise SystemExit("EPC_KEY is not set (add it to .env or the environment)")
    return key


def fetch_certificates(key):
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    certs, page = [], 1
    while page:
        body = helper.get(API, headers=headers, timeout=120, params={
            "council[]": COUNCIL, "page_size": PAGE_SIZE, "current_page": page,
        }).json()
        certs.extend(body["data"])
        page = body["pagination"].get("nextPage")
    return certs


def latest_per_home(certs):
    """Each home's latest certificate with a valid A to G band, as
    {band, date, postcode}. Homes are matched on UPRN, or on address and
    postcode when a certificate has no UPRN."""
    latest = {}
    for c in certs:
        band = (c.get("currentEnergyEfficiencyBand") or "").upper()
        if len(band) != 1 or band not in BANDS:
            continue
        if c.get("uprn"):
            key = f"uprn:{c['uprn']}"
        else:
            key = " ".join(str(c.get(f) or "") for f in ("addressLine1", "addressLine2", "postcode")).upper()
        date = c.get("registrationDate") or ""
        if key not in latest or date > latest[key]["date"]:
            latest[key] = {"band": band, "date": date, "postcode": (c.get("postcode") or "").upper()}
    return list(latest.values())


def median_band(bands):
    """The rating of the middle home with every home lined up from A to G,
    taking the better of the two middle homes when the count is even."""
    if not bands:
        return None
    ordered = sorted(bands, key=BANDS.index)
    return ordered[(len(ordered) - 1) // 2]


def summarise(bands):
    homes = len(bands)
    counts = {band: bands.count(band) for band in BANDS}
    return {
        "homes": homes,
        "homes_display": f"{homes:,}",
        "counts": counts,
        "counts_display": {band: f"{n:,}" for band, n in counts.items()},
        "shares": {band: round(100 * n / homes, 1) for band, n in counts.items()} if homes else {},
        "c_plus_pct": round(100 * (counts["A"] + counts["B"] + counts["C"]) / homes, 1) if homes else None,
        "median_band": median_band(bands),
    }


def area_for(lat, lon, areas):
    """Code of the area whose rings contain the point (even-odd across all
    rings, so holes and multi-part areas work), or None."""
    for area in areas:
        inside = False
        for ring in area["rings"]:
            if helper.point_in_ring(lat, lon, ring):
                inside = not inside
        if inside:
            return area["code"]
    return None


def band_edges(values, decimals):
    """Five cut points splitting the values into six equal-sized bands, each
    larger than the last and the first above the lowest value, so no band
    on the legend is empty."""
    ordered = sorted(values)
    step = 10 ** -decimals
    edges = []
    for i in range(1, SHADES):
        edge = round(ordered[min(len(ordered) - 1, round(i * len(ordered) / SHADES))], decimals)
        edges.append(round(max(edge, edges[-1] + step), decimals) if edges else round(max(edge, ordered[0] + step), decimals))
    return edges


def geocode(postcodes):
    found = {}
    ordered = sorted(postcodes)
    for i in range(0, len(ordered), GEOCODE_BATCH):
        found.update(helper.geocode_postcodes(ordered[i:i + GEOCODE_BATCH]))
    return found


def build_level(areas, homes_by_area):
    out = []
    for area in areas:
        row = {k: v for k, v in area.items() if k != "rings"}
        row["boundary"] = area["rings"]
        row.update(summarise(homes_by_area.get(area["code"], [])))
        out.append(row)
    rated = [a for a in out if a["homes"]]
    return {
        "c_plus_edges": band_edges([a["c_plus_pct"] for a in rated], 0),
        "band_edges": {band: band_edges([a["shares"][band] for a in rated], 1) for band in BANDS},
        "areas": out,
    }


def main():
    certs = fetch_certificates(load_key())
    homes = latest_per_home(certs)
    points = geocode({h["postcode"] for h in homes if h["postcode"]})

    data = helper.repo_root() / "_data"
    lsoas = [{"code": a["code"], "name": a["name"], "ward_name": a["ward_name"], "rings": a["boundary"]}
             for a in json.loads((data / "small-areas.json").read_text())["lsoas"]]
    wards = [{"code": w["code"], "name": w["name"], "slug": w["slug"], "rings": [w["boundary"]]}
             for w in json.loads((data / "wards" / "index.json").read_text())["wards"]]

    by_lsoa, by_ward, placed = {}, {}, 0
    for home in homes:
        point = points.get(home["postcode"])
        if not point:
            continue
        lsoa, ward = area_for(*point, lsoas), area_for(*point, wards)
        if lsoa:
            by_lsoa.setdefault(lsoa, []).append(home["band"])
        if ward:
            by_ward.setdefault(ward, []).append(home["band"])
        placed += 1 if (lsoa or ward) else 0

    years = [h["date"][:4] for h in homes if h["date"]]
    helper.write_json(data / "epc.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "certificates": len(certs),
        "certificates_display": f"{len(certs):,}",
        "placed": placed,
        "first_year": min(years) if years else None,
        "bands": list(BANDS),
        "borough": summarise([h["band"] for h in homes]),
        "older_than_ten_years_pct": round(100 * sum(1 for y in years if int(y) < datetime.now().year - 10) / len(years), 1)
        if years else None,
        "ward": build_level(wards, by_ward),
        "lsoa": build_level(lsoas, by_lsoa),
    })
    print(f"Wrote EPC ratings for {len(homes):,} homes ({len(certs):,} certificates, "
          f"{placed:,} placed in an area) to _data/epc.json")


if __name__ == "__main__":
    main()
