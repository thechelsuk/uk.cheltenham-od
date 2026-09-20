#!/usr/bin/env python3
"""Fetch Cheltenham's housing supply figures and write _data/housing-supply.json:

- Net additional dwellings by year (MHCLG Live Table 122)
- Communal accommodation net change, split student/other, by year, both as
  Council Tax Listings and Bedspaces (MHCLG Live Table 124)
- Total number of properties by year (VOA Council Tax stock of properties,
  CTSOP1.1) — the 1993-2024 run is a one-off backfill kept in
  _data/council-tax-stock-history.json (see local/council-tax-stock-history-backfill.py);
  this script only fetches the latest single-year snapshot and appends it

The gov.uk asset URLs for these change with every release, so both pages are
scraped for their current download links rather than hardcoding a URL."""
import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "housing-supply.json")
HISTORY_PATH = os.path.join(HERE, "..", "_data", "council-tax-stock-history.json")

LIVE_TABLES_PAGE_URL = "https://www.gov.uk/government/statistical-data-sets/live-tables-on-net-supply-of-housing"
CTSOP_COLLECTION_URL = "https://www.gov.uk/government/collections/valuation-office-agency-council-tax-statistics"
DCLG_CODE, FORMER_ONS_CODE, ECODE = "B1605", "23UB", "E07000078"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}


def find_link(page_url, pattern):
    resp = requests.get(page_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    match = re.search(rf'href="({re.escape("https://assets.publishing.service.gov.uk/media/")}[^"]*{pattern}[^"]*)"', resp.text)
    if not match:
        raise SystemExit(f"Could not find a link matching {pattern!r} on {page_url}")
    return match.group(1)


def download(url, timeout=60):
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def cheltenham_row(df, code_col=2):
    mask = df.iloc[:, code_col] == ECODE
    rows = df[mask]
    if rows.empty:
        raise SystemExit(f"Could not find Cheltenham ({ECODE}) row")
    return rows.iloc[0]


def fetch_net_additional_dwellings():
    url = find_link(LIVE_TABLES_PAGE_URL, r"Live_Table_122\.ods")
    df = pd.read_excel(io.BytesIO(download(url)), engine="odf", sheet_name="LT_122", header=None)
    headers = df.iloc[4].tolist()
    row = cheltenham_row(df)

    years = []
    for col in range(4, len(headers)):
        year_label = re.sub(r"\s*\[note \d+\]|\s*\[r\]|\s*\[p\]", "", str(headers[col])).strip()
        value = row[col]
        if pd.isna(value):
            continue
        years.append({"year": year_label, "net_additional_dwellings": int(value)})
    return {"source_url": url, "years": years}


def fetch_communal_accommodation():
    url = find_link(LIVE_TABLES_PAGE_URL, r"Live_Table_124\.ods")
    raw = download(url)
    xl = pd.ExcelFile(io.BytesIO(raw), engine="odf")

    entries = []
    for sheet in xl.sheet_names:
        match = re.match(r"^(\d{4}-\d{2})_\((Council_Tax_Listings|Bedspaces)\)$", sheet)
        if not match:
            continue
        year_label, kind = match.group(1), match.group(2)
        df = xl.parse(sheet, header=None)
        row = cheltenham_row(df)
        entries.append({
            "year": year_label,
            "metric": "council_tax_listings" if kind == "Council_Tax_Listings" else "bedspaces",
            "student_gain": int(row[4]), "student_loss": int(row[5]), "student_net_change": int(row[6]),
            "other_gain": int(row[7]), "other_loss": int(row[8]), "other_net_change": int(row[9]),
            "total_net_change": int(row[10]),
        })

    entries.sort(key=lambda e: (e["year"], e["metric"]))
    return {"source_url": url, "entries": entries}


def find_latest_ctsop_page():
    resp = requests.get(CTSOP_COLLECTION_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    years = [int(y) for y in re.findall(r"council-tax-stock-of-properties-(\d{4})", resp.text)]
    if not years:
        raise SystemExit("Could not find any council-tax-stock-of-properties-YYYY link")
    return f"https://www.gov.uk/government/statistics/council-tax-stock-of-properties-{max(years)}", max(years)


def fetch_latest_council_tax_stock():
    page_url, year = find_latest_ctsop_page()
    zip_url = find_link(page_url, r"CTSOP1\.1\.zip")
    raw = download(zip_url)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(csv_name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            for row in reader:
                if row.get("ecode") == ECODE:
                    return {"source_url": zip_url, "year": year, "all_properties": int(row["all_properties"])}
    raise SystemExit("Could not find Cheltenham row in CTSOP1.1 snapshot")


def build_council_tax_stock_series(latest):
    with open(HISTORY_PATH, encoding="utf-8") as f:
        history = json.load(f)
    years = {y["year"]: y["all_properties"] for y in history["years"]}
    years[latest["year"]] = latest["all_properties"]
    return [{"year": y, "all_properties": years[y]} for y in sorted(years)]


def main():
    net_additional = fetch_net_additional_dwellings()
    communal = fetch_communal_accommodation()
    latest_stock = fetch_latest_council_tax_stock()
    stock_series = build_council_tax_stock_series(latest_stock)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Ministry of Housing, Communities & Local Government / Valuation Office Agency",
        "net_additional_dwellings": {
            "source_url": net_additional["source_url"],
            "years": net_additional["years"],
        },
        "communal_accommodation": {
            "source_url": communal["source_url"],
            "entries": communal["entries"],
        },
        "council_tax_stock": {
            "source_url": latest_stock["source_url"],
            "history_source_url": "https://www.gov.uk/government/statistics/council-tax-stock-of-properties-2024",
            "years": stock_series,
        },
        "licence": "Open Government Licence v3.0",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote housing supply data ({len(net_additional['years'])} dwelling years, "
          f"{len(communal['entries'])} communal accommodation entries, "
          f"{len(stock_series)} council tax stock years) to {OUT}")


if __name__ == "__main__":
    main()
