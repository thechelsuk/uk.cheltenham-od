#!/usr/bin/env python3
"""Extract DWP low-income children statistics for Cheltenham wards from the
latest downloaded ODS workbook and write _data/low-income-kids.json.

Download the workbook from the DWP collection page into _data-sources/ and
update SOURCE_ODS below if its filename changes. The statistics are published
annually, so this is run by hand after a new release.

Run from the repository root:
    .venv/bin/python _python/local/process-low-income-kids.py
"""
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SOURCE_ODS = os.path.join(
    ROOT,
    "_data-sources",
    "children-in-low-income-families-local-area-statistics-2022-2025.ods",
)
OUT = os.path.join(ROOT, "_data", "low-income-kids.json")
WARD_INDEX = os.path.join(ROOT, "_data", "wards", "index.json")

SOURCE_URL = "https://www.gov.uk/government/collections/children-in-low-income-families-local-area-statistics"
SOURCE_NAME = "Children in low income families: local area statistics (Department for Work and Pensions)"
LICENCE = "Open Government Licence v3.0"
LOCAL_AUTHORITY_CODE = "E07000078"
EXPECTED_WARD_COUNT = 20

TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
TABLE_TAG = f"{{{TABLE_NS}}}table"
ROW_TAG = f"{{{TABLE_NS}}}table-row"
CELL_TAG = f"{{{TABLE_NS}}}table-cell"
COVERED_CELL_TAG = f"{{{TABLE_NS}}}covered-table-cell"
TEXT_P_TAG = f"{{{TEXT_NS}}}p"

SERIES = (
    {
        "key": "relative_ahc",
        "label": "Relative low income after housing costs",
        "description": "Children in families with income below the relative low-income threshold after housing costs are deducted.",
        "sheet": "4_AHC_Relative_Ward",
    },
    {
        "key": "relative_bhc",
        "label": "Relative low income before housing costs",
        "description": "Children in families with income below the relative low-income threshold before housing costs are deducted.",
        "sheet": "11_BHC_Relative_Ward",
    },
    {
        "key": "absolute_bhc",
        "label": "Absolute low income before housing costs",
        "description": "Children in families with income below the absolute low-income threshold before housing costs are deducted.",
        "sheet": "12_BHC_Absolute_Ward",
    },
)


def row_values(row):
    """Return displayed cell text while preserving the spreadsheet columns."""
    values = []
    for cell in row:
        if cell.tag not in (CELL_TAG, COVERED_CELL_TAG):
            continue
        repeat = int(cell.get(f"{{{TABLE_NS}}}number-columns-repeated", "1"))
        text = " ".join(
            "".join(paragraph.itertext()).strip()
            for paragraph in cell.findall(f".//{TEXT_P_TAG}")
        ).strip()
        values.extend([text] * min(repeat, 20 - len(values)))
        if len(values) >= 20:
            break
    return values


def parse_number(value, *, percentage=False):
    """Parse a published number or keep DWP's disclosure-control marker."""
    value = value.strip()
    if value == "[x]":
        return None, "Not available"
    if value == "[low]":
        return None, "Nil or negligible"
    if not value:
        raise ValueError("A required count or percentage is blank")

    numeric = value.rstrip("%").replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", numeric):
        raise ValueError(f"Unrecognised DWP value: {value!r}")
    number = float(numeric) if percentage else int(numeric)
    display = f"{number:.1f}%" if percentage else f"{number:,}"
    return number, display


def read_ward_table(content, wanted_sheet):
    """Read one named ODS sheet without loading the whole workbook into memory."""
    active_sheet = None
    header = None
    records = []

    for event, element in ElementTree.iterparse(content, events=("start", "end")):
        if event == "start" and element.tag == TABLE_TAG:
            active_sheet = element.get(f"{{{TABLE_NS}}}name")
        elif event == "end" and active_sheet == wanted_sheet and element.tag == ROW_TAG:
            values = row_values(element)
            if values and values[0] == "Local Authority [note 2]":
                header = values
            elif values and values[0] == "Cheltenham":
                if values[1] != LOCAL_AUTHORITY_CODE:
                    raise ValueError(
                        f"Unexpected Cheltenham area code in {wanted_sheet}: {values[1]!r}"
                    )
                records.append(values)
            element.clear()
        elif event == "end" and element.tag == TABLE_TAG:
            if active_sheet == wanted_sheet:
                break
            active_sheet = None

    if header is None:
        raise ValueError(f"Could not find the column headings in {wanted_sheet}")

    counts = {}
    percentages = {}
    for index, label in enumerate(header):
        count_year = re.fullmatch(r"Number of children FYE (\d{4})", label)
        percentage_year = re.fullmatch(
            r"Percentage of children FYE (\d{4}) \(%\)(?: \[note 3\])?", label
        )
        if count_year:
            counts[int(count_year.group(1))] = index
        elif percentage_year:
            percentages[int(percentage_year.group(1))] = index

    years = sorted(set(counts) & set(percentages))
    if not years or set(counts) != set(percentages):
        raise ValueError(f"Could not match count and percentage years in {wanted_sheet}")

    wards = {}
    for values in records:
        code = values[3]
        if not code or code in wards:
            raise ValueError(f"Missing or duplicate Cheltenham ward code in {wanted_sheet}")
        observations = []
        for year in years:
            count, count_display = parse_number(values[counts[year]])
            percentage, percentage_display = parse_number(
                values[percentages[year]], percentage=True
            )
            observations.append(
                {
                    "year": year,
                    "children": count,
                    "children_display": count_display,
                    "percentage": percentage,
                    "percentage_display": percentage_display,
                }
            )
        wards[code] = {
            "code": code,
            "name": values[2],
            "values": observations,
        }

    if len(wards) != EXPECTED_WARD_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_WARD_COUNT} Cheltenham wards in {wanted_sheet}, "
            f"found {len(wards)}"
        )
    return years, wards


def extremes(wards, year):
    observations = []
    for ward in wards:
        value = next(item for item in ward["values"] if item["year"] == year)
        if value["percentage"] is not None:
            observations.append((ward, value))
    if not observations:
        raise ValueError(f"No published percentages found for FYE {year}")

    highest = max(observations, key=lambda pair: pair[1]["percentage"])
    lowest = min(observations, key=lambda pair: pair[1]["percentage"])

    def compact(pair):
        ward, value = pair
        return {
            "ward": ward["name"],
            "percentage": value["percentage"],
            "percentage_display": value["percentage_display"],
            "children": value["children"],
            "children_display": value["children_display"],
        }

    return {"highest": compact(highest), "lowest": compact(lowest)}


def main():
    if not os.path.exists(SOURCE_ODS):
        raise FileNotFoundError(
            f"Input workbook not found: {SOURCE_ODS}. Download the latest workbook "
            "from the DWP collection page and save it in _data-sources/."
        )
    if not os.path.exists(WARD_INDEX):
        raise FileNotFoundError(
            f"Ward boundaries not found: {WARD_INDEX}. Run the ward data builder first."
        )

    with open(WARD_INDEX, encoding="utf-8") as f:
        ward_index = json.load(f)["wards"]
    ward_index_by_code = {ward["code"]: ward for ward in ward_index}

    series = []
    for definition in SERIES:
        with zipfile.ZipFile(SOURCE_ODS) as workbook:
            with workbook.open("content.xml") as content:
                years, ward_map = read_ward_table(content, definition["sheet"])
        wards = sorted(ward_map.values(), key=lambda ward: ward["name"].casefold())
        for ward in wards:
            boundary = ward_index_by_code.get(ward["code"])
            if boundary is None:
                raise ValueError(
                    f"No ward boundary found for {ward['name']} ({ward['code']})"
                )
            ward["slug"] = boundary["slug"]
        wards_by_latest = sorted(
            wards,
            key=lambda ward: next(
                (
                    value["percentage"]
                    for value in ward["values"]
                    if value["year"] == years[-1]
                ),
                -1,
            ),
            reverse=True,
        )
        series.append(
            {
                "key": definition["key"],
                "label": definition["label"],
                "description": definition["description"],
                "years": years,
                "latest_year": years[-1],
                "wards": wards_by_latest,
                "summary": extremes(wards, years[-1]),
            }
        )

    source_codes = {ward["code"] for ward in series[0]["wards"]}
    boundary_codes = set(ward_index_by_code)
    if source_codes != boundary_codes:
        raise ValueError(
            "The DWP ward codes do not match _data/wards/index.json: "
            f"missing boundaries {sorted(source_codes - boundary_codes)}, "
            f"missing source rows {sorted(boundary_codes - source_codes)}"
        )
    for metric in series[1:]:
        metric_codes = {ward["code"] for ward in metric["wards"]}
        if metric_codes != source_codes:
            raise ValueError(
                f"The ward codes in {metric['key']} do not match the other series: "
                f"missing {sorted(source_codes - metric_codes)}, "
                f"unexpected {sorted(metric_codes - source_codes)}"
            )
    series_wards = [
        {ward["code"]: ward for ward in metric["wards"]}
        for metric in series
    ]
    map_wards = []
    for ward in series[0]["wards"]:
        boundary = ward_index_by_code[ward["code"]]
        map_ward = {
            "code": ward["code"],
            "name": ward["name"],
            "slug": boundary["slug"],
            "boundary": boundary["boundary"],
            "values": {},
        }
        for metric, metric_wards in zip(series, series_wards):
            value = metric_wards[ward["code"]]["values"][-1]
            map_ward["values"][metric["key"]] = {
                "year": value["year"],
                "children": value["children"],
                "children_display": value["children_display"],
                "percentage": value["percentage"],
                "percentage_display": value["percentage_display"],
            }
        map_wards.append(map_ward)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "geography": "Cheltenham local authority wards",
        "age_range": "0 to 15",
        "series": series,
        "map_wards": map_wards,
        "notes": [
            "Figures are provisional and may be revised in a later release.",
            "Counts are subject to rounding and statistical disclosure control; totals may not sum.",
            "Percentages are rounded to one decimal place and use the latest available mid-year child population estimates.",
        ],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote low-income children statistics for {EXPECTED_WARD_COUNT} wards to {OUT}")


if __name__ == "__main__":
    main()
