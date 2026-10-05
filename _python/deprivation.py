#!/usr/bin/env python3
"""The English Indices of Deprivation 2025 for Cheltenham's small areas
(LSOAs) and wards, written to _data/deprivation.json.

The indices rank all 33,755 small areas in England from most to least
deprived, overall and on seven domains. They come from the Ministry of
Housing, Communities and Local Government on GOV.UK: File 7 has every area's
ranks and deciles, and File 10 each local authority district's summary. LSOA
boundaries, populations and the LSOA-to-ward lookup come from
_data/small-areas.json (small-areas.py), so run that first.

The indices are published every four to six years, so this is run by hand
when a new edition comes out rather than on a schedule.

Run from the repository root:
    .venv/bin/python _python/deprivation.py
"""
import csv
import io
import json
import os
from datetime import datetime, timezone

import openpyxl

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
SMALL_AREAS = os.path.join(HERE, "..", "_data", "small-areas.json")
OUT = os.path.join(HERE, "..", "_data", "deprivation.json")

EDITION = "2025"
SOURCE_URL = "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025"
ASSETS = "https://assets.publishing.service.gov.uk/media/"
FILE_7 = ASSETS + "691ded56d140bbbaa59a2a7d/File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
FILE_10 = ASSETS + "6917412ebc34c86ce4e6e7fc/File_10_-_IoD2025_Local_Authority_District_Summaries__lower-tier__v2.xlsx"
LSOA_COUNT = 33755

# (key, label, column prefix in File 7)
DOMAINS = (
    ("imd", "Overall (Index of Multiple Deprivation)", "Index of Multiple Deprivation (IMD)"),
    ("income", "Income", "Income"),
    ("employment", "Employment", "Employment"),
    ("education", "Education, skills and training", "Education, Skills and Training"),
    ("health", "Health and disability", "Health Deprivation and Disability"),
    ("crime", "Crime", "Crime"),
    ("housing", "Barriers to housing and services", "Barriers to Housing and Services"),
    ("environment", "Living environment", "Living Environment"),
    ("idaci", "Income deprivation affecting children", "Income Deprivation Affecting Children Index (IDACI)"),
    ("idaopi", "Income deprivation affecting older people", "Income Deprivation Affecting Older People (IDAOPI)"),
)


def column(row, prefix, kind):
    """The rank or decile column for a domain; headers carry long explanations."""
    key = next(k for k in row if k.startswith(f"{prefix} {kind}"))
    return int(float(row[key]))


def district_summary():
    rows = list(openpyxl.load_workbook(io.BytesIO(helper.get(FILE_10, timeout=120).content),
                                       read_only=True)["IMD"].iter_rows(values_only=True))
    header = [str(h).strip() for h in rows[0]]
    districts = [dict(zip(header, r)) for r in rows[1:] if r and r[0]]
    ours = next(d for d in districts if d["Local Authority District code (2024)"] == config.AREA_CODE)
    return {
        "district_count": len(districts),
        "rank_of_average_score": ours["IMD - Rank of average score"],
        "average_score": round(ours["IMD - Average score"], 1),
        "share_most_deprived_10": round(ours["IMD - Proportion of LSOAs in most deprived 10% nationally"] * 100, 1),
    }


def main():
    with open(SMALL_AREAS, encoding="utf-8") as f:
        small = {a["code"]: a for a in json.load(f)["lsoas"]}

    text = helper.get(FILE_7, timeout=180).content.decode("utf-8-sig")
    lsoas = []
    for row in csv.DictReader(io.StringIO(text)):
        area = small.get(row["LSOA code (2021)"])
        if not area:
            continue
        lsoas.append({
            "code": area["code"],
            "name": area["name"],
            "ward_code": area["ward_code"],
            "ward_name": area["ward_name"],
            "population": area["population_latest"],
            "population_display": area["population_latest_display"],
            "score": round(float(row["Index of Multiple Deprivation (IMD) Score"]), 1),
            "rank": column(row, DOMAINS[0][2], "Rank"),
            "rank_display": f"{column(row, DOMAINS[0][2], 'Rank'):,}",
            "deciles": {key: column(row, prefix, "Decile") for key, _, prefix in DOMAINS},
            "boundary": area["boundary"],
        })
    missing = set(small) - {a["code"] for a in lsoas}
    if missing:
        raise RuntimeError(f"LSOAs with no deprivation figures: {sorted(missing)}")
    lsoas.sort(key=lambda a: a["rank"])

    # Wards: the population-weighted average score of their small areas, then
    # ranked within Cheltenham (1 = most deprived).
    wards = {}
    for area in lsoas:
        ward = wards.setdefault(area["ward_code"], {"code": area["ward_code"], "name": area["ward_name"],
                                                    "lsoas": [], "population": 0, "weighted": 0.0})
        ward["lsoas"].append(area["code"])
        ward["population"] += area["population"]
        ward["weighted"] += area["score"] * area["population"]
    for ward in wards.values():
        ward["score"] = round(ward.pop("weighted") / ward["population"], 1)
        areas = [a for a in lsoas if a["ward_code"] == ward["code"]]
        ward["most_deprived_decile"] = min(a["deciles"]["imd"] for a in areas)
        ward["least_deprived_decile"] = max(a["deciles"]["imd"] for a in areas)
        ward["lsoa_count"] = len(areas)
    for position, ward in enumerate(sorted(wards.values(), key=lambda w: -w["score"]), start=1):
        ward["rank"] = position

    deciles = {str(d): sum(1 for a in lsoas if a["deciles"]["imd"] == d) for d in range(1, 11)}
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "edition": EDITION,
        "source": "English Indices of Deprivation 2025 (Ministry of Housing, Communities and Local Government)",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "lsoa_count_england": LSOA_COUNT,
        "lsoa_count_england_display": f"{LSOA_COUNT:,}",
        "domains": [{"key": key, "label": label} for key, label, _ in DOMAINS],
        "summary": {**district_summary(), "lsoa_count": len(lsoas), "deciles": deciles,
                    "most_deprived_20": deciles["1"] + deciles["2"],
                    "least_deprived_20": deciles["9"] + deciles["10"]},
        "wards": dict(sorted(wards.items(), key=lambda kv: kv[1]["rank"])),
        "lsoas": lsoas,
    }
    helper.write_json(OUT, output)
    print(f"Wrote deprivation for {len(lsoas)} small areas and {len(wards)} wards to {OUT}")


if __name__ == "__main__":
    main()
