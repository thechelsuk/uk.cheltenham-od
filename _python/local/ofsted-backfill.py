#!/usr/bin/env python3
"""Fill in blank Ofsted outcomes in _data/ofsted.json from Ofsted's older
management information (MI) spreadsheets.

Once a school has a report card, Ofsted's reports site stops showing grades
against its older reports, and it never showed the outcome of a short
inspection. The MI spreadsheets for 2005 to 2018 have both:

- every graded (section 5) inspection from September 2005 to August 2015;
- each school's latest full and short inspection at 31 August 2016 and 2017;
- every full and short inspection in the 2017/18 and 2018/19 school years,
  plus each school's latest at 31 August and 31 October 2018.

A short inspection that didn't convert to a full one confirmed the school's
previous grade, so it is recorded as "Remains <grade>" (the 2018/19 file
words this itself, which ofsted.ungraded_outcome() tidies).

Run by hand once; not part of a scheduled workflow. The spreadsheets are
downloaded into _data-sources/ofsted-mi/ (gitignored) on the first run.
_python/ofsted.py keeps any outcome already in _data/ofsted.json, so the
filled-in grades survive its monthly runs. Inspections before September 2005
had no single overall grade and stay blank.

Needs openpyxl: uv run --with openpyxl python _python/local/ofsted-backfill.py
"""
import csv
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helper  # noqa: E402  pylint: disable=wrong-import-position
import ofsted  # noqa: E402  pylint: disable=wrong-import-position

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "_data" / "ofsted.json"
CACHE = ROOT / "_data-sources" / "ofsted-mi"

ASSETS = "https://assets.publishing.service.gov.uk/media/"
FILES = {
    "2005-2015.xlsx": ASSETS + "5a757ca240f0b6397f35ece5/Management_information_-_schools_-_1_Sept_2005_to_31_August_2015.xlsx",
    "2016.xlsx": ASSETS + "5a80afde40f0b62305b8c945/External_MI_-_Schools_-_31_Aug_16.xlsx",
    "2017.xlsx": ASSETS + "5a81dfd340f0b62305b9145d/Management_information_-_schools_-_31_Aug_2017.xlsx",
    "2018-full.csv": ASSETS + "5b991910e5274a13a7fd95d3/Management_information_-_schools_-_Table2_31_Aug_2018.csv",
    "2018-short.csv": ASSETS + "5b99192fed915d666f681e00/Management_information_-_schools_-_Table3_31_Aug_2018.csv",
    "2018-latest.csv": ASSETS + "5b9918eced915d6660adb9f9/Management_information_-_schools_-_Table1_31_Aug_2018.csv",
    "2018-oct-latest.csv": ASSETS + "5bf5772de5274a2b05d2ea91/Management_information_-_schools_-_table1_31_Oct_2018.csv",
    "2019.csv": ASSETS + "5d7777bce5274a27c977e4ad/Management_information_-_schools_Tables2_3_-_31_August_2019.csv",
}

GRADES = {"1": "Outstanding", "2": "Good", "3": "Requires improvement", "4": "Inadequate"}
# Before September 2012 the third grade was Satisfactory.
SATISFACTORY_UNTIL = "2012-09-01"
MATCH_DAYS = 3


def fetch(name):
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(helper.get(FILES[name], timeout=300).content)
    return path


def iso(value):
    """A spreadsheet date (datetime, or text like 13/03/2013) as YYYY-MM-DD."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def grade(value, when):
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    word = GRADES.get(text)
    if word == "Requires improvement" and when and when < SATISFACTORY_UNTIL:
        return "Satisfactory"
    return word


def sheet_rows(name, sheet):
    """Rows of a workbook sheet as dicts, keyed by the header on row 2."""
    rows = openpyxl.load_workbook(fetch(name), read_only=True)[sheet].iter_rows(values_only=True)
    next(rows)
    header = [str(h).strip() if h else "" for h in next(rows)]
    for row in rows:
        yield dict(zip(header, row))


def csv_rows(name):
    lines = fetch(name).read_bytes().decode("latin-1").splitlines()[1:]   # skip the title line
    yield from csv.DictReader(io.StringIO("\n".join(lines)))


def known_outcomes(urns):
    """(urn, date, outcome) for every inspection the spreadsheets grade."""
    found = []

    def add(urn, when, outcome):
        urn = str(urn or "").strip().removesuffix(".0")
        if urn in urns and when and outcome:
            found.append((urn, when, outcome))

    for row in sheet_rows("2005-2015.xlsx", "2005-2015 Inspections"):
        when = iso(row.get("Inspection start date"))
        add(row.get("URN"), when, grade(row.get("Overall effectiveness"), when))

    # Snapshots of each school's latest full and short inspection.
    snapshots = [sheet_rows(name, "School level data") for name in ("2016.xlsx", "2017.xlsx")]
    snapshots += [csv_rows("2018-latest.csv"), csv_rows("2018-oct-latest.csv")]
    for rows in snapshots:
        for row in rows:
            full_date = iso(row.get("Inspection date"))
            full = grade(row.get("Overall effectiveness"), full_date)
            add(row.get("URN"), full_date, full)
            short_date = iso(row.get("Date of latest short inspection"))
            converted = str(row.get("Did the latest short inspection convert to a full inspection?") or "").startswith("Y")
            if full and short_date and not converted and (not full_date or short_date > full_date):
                add(row.get("URN"), short_date, f"Remains {full}")

    for row in csv_rows("2018-full.csv"):
        when = iso(row.get("Inspection date"))
        add(row.get("URN"), when, grade(row.get("Overall effectiveness"), when))
    for row in csv_rows("2018-short.csv"):
        if row.get("Did the short inspection convert to a full inspection?", "").startswith("N"):
            previous = grade(row.get("Previous full inspection overall effectiveness"), None)
            add(row.get("URN"), iso(row.get("Inspection date")), previous and f"Remains {previous}")

    # From 2018/19 the outcome of a short inspection is given in words.
    for row in csv_rows("2019.csv"):
        when = iso(row.get("Inspection start date"))
        words = (row.get("Outcomes for section 8 inspections and short inspections that did not convert") or "").strip()
        if words and words != "NULL":
            add(row.get("URN"), when, ofsted.ungraded_outcome(words))
        else:
            add(row.get("URN"), when, grade(row.get("Overall effectiveness"), when))
    return found


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    reports = [r for school in data["schools"].values() for r in school["inspections"]]
    urns = {r["urn"] for r in reports}

    filled = 0
    for urn, when, outcome in known_outcomes(urns):
        for report in reports:
            if (report["urn"] == urn and not report["outcome"]
                    and abs((date.fromisoformat(report["date"]) - date.fromisoformat(when)).days) <= MATCH_DAYS):
                report["outcome"] = outcome
                filled += 1
                break

    data["schools"] = {urn: ofsted.summarise(school) for urn, school in data["schools"].items()}

    helper.write_json(DATA, data)
    blank = sum(1 for r in reports if not r["outcome"])
    print(f"Filled {filled} outcomes; {blank} reports still have none")


if __name__ == "__main__":
    main()
