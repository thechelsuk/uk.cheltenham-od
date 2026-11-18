#!/usr/bin/env python3
"""Build _data/council-accounts.json: Cheltenham Borough Council's net
current spending by service for the last five financial years, from the
government's revenue outturn statistics (Ministry of Housing, Communities and
Local Government, "Local authority revenue expenditure and financing England:
individual local authority data - outturn", Open Government Licence v3.0).

Download the "Revenue outturn service expenditure summary (RSX)" spreadsheet
for each year from that year's GOV.UK statistics page into
_data-sources/council-accounts/, then run:

  python _python/local/process-council-accounts.py

It reads every RSX file in that folder, keeps the newest five years, and
finds Cheltenham by its ONS code. Figures are published in thousands of
pounds and are stored here in pounds. The outturn for a year is published
between May and September of the following year.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helper  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "_data-sources" / "council-accounts"
OUT = ROOT / "_data" / "council-accounts.json"
ONS_CODE = "E07000078"
YEARS = 5
COLLECTION = ("https://www.gov.uk/government/collections/"
              "local-authority-revenue-expenditure-and-financing")

# The RSX summary's service columns, in the order the government publishes
# them. 2021-22's file leaves the name off the environmental column, so
# columns are matched by position and checked against the name where given.
SERVICES = [
    ("Education services", "Education"),
    ("Highways and transport services", "Highways"),
    ("Children's social care", "Children"),
    ("Adult social care", "Adult"),
    ("Public health", "Public Health"),
    ("Housing services (general fund)", "Housing"),
    ("Cultural and related services", "Cultural"),
    ("Environmental and regulatory services", "Environmental"),
    ("Planning and development services", "Planning"),
    ("Police services", "Police"),
    ("Fire and rescue services", "Fire"),
    ("Central services", "Central"),
    ("Other services", "Other"),
    ("Total service spending", "Total"),
]


def money(value):
    sign = "-" if value < 0 else ""
    return f"{sign}£{abs(value):,.0f}"


def read_year(path):
    sheet = pd.ExcelFile(path, engine="odf").sheet_names[-1]
    frame = pd.read_excel(path, sheet_name=sheet, header=None, engine="odf", dtype=str).fillna("")
    header_at = next(i for i in range(30) if frame.iloc[i].str.fullmatch(r"ONS [Cc]ode").any())
    header = [str(c) for c in frame.iloc[header_at].tolist()]
    columns = [i for i, c in enumerate(header) if "net current expenditure" in c.lower()]
    if len(columns) != len(SERVICES):
        raise ValueError(f"{path.name}: {len(columns)} net current expenditure columns, expected {len(SERVICES)}")
    for (name, word), i in zip(SERVICES, columns):
        label = re.sub(r"\s+", " ", header[i])
        if not label.lower().startswith("net current") and word.lower() not in label.lower():
            raise ValueError(f"{path.name}: column {i} is {label!r}, expected {name}")
    rows = frame[frame.iloc[:, :4].apply(lambda r: r.str.fullmatch(ONS_CODE).any(), axis=1)]
    if len(rows) != 1:
        raise ValueError(f"{path.name}: {len(rows)} rows for {ONS_CODE}")
    values = rows.iloc[0].tolist()
    year = re.search(r"(20\d\d)-(\d\d)", path.name).group(0)
    return year, {name: float(values[i]) * 1000 for (name, _), i in zip(SERVICES, columns)}


def main():
    files = sorted(FOLDER.glob("RSX_*.ods"))
    years = dict(sorted(read_year(p) for p in files)[-YEARS:])
    order = list(years)
    total = SERVICES[-1][0]
    services = [name for name, _ in SERVICES[:-1] if any(years[y][name] for y in order)]

    def row(name):
        return {"name": name, "years": [{"year": y, "value": years[y][name], "display": money(years[y][name])}
                                        for y in order]}

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Ministry of Housing, Communities and Local Government",
        "source_url": COLLECTION,
        "licence": "Open Government Licence v3.0",
        "years": order,
        "latest_year": order[-1],
        "services": [row(n) for n in services],
        "total": row(total),
    }
    for check in order:
        added = sum(years[check][n] for n in services)
        if abs(added - years[check][total]) > 2000:
            raise ValueError(f"{check}: services add to {added}, total is {years[check][total]}")
    helper.write_json(OUT, output)
    print(f"Wrote {len(services)} services for {order[0]} to {order[-1]} to {OUT}")


if __name__ == "__main__":
    main()
