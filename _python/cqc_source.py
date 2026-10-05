"""Where the Care Quality Commission (CQC) data comes from, kept apart from
cqc.py so the source can be swapped without touching anything else.

For now it reads the two files the CQC publishes each month on its "Using
CQC data" page, which need no key:

- the care directory CSV: every registered location with its service types
  and specialisms;
- the latest ratings spreadsheet (ODS): each location's latest rating,
  overall and for each key question. The file is about 30MB zipped but holds
  over 1GB of XML, so it is read as a stream rather than with a spreadsheet
  library, which takes over ten minutes.

The CQC's API (https://api.service.cqc.org.uk) has the same information but
needs a subscription key. To switch to it, replace load_locations() with a
version that calls the API and returns records in the same shape.

load_locations(postcode_districts) returns one dict per location:
    id, ods_code, name, address, postcode, website, url,
    service_types (list), specialisms (list), category, care_home (bool),
    overall, published (YYYY-MM-DD or None),
    ratings: {"safe", "effective", "caring", "responsive", "well_led"}
"""
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

import helper

DATA_PAGE = "https://www.cqc.org.uk/about-us/transparency/using-cqc-data"
SOURCE_NAME = "CQC care directory and latest ratings"

_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
KEY_QUESTIONS = {"Safe": "safe", "Effective": "effective", "Caring": "caring",
                 "Responsive": "responsive", "Well-led": "well_led"}


def _links():
    """The current directory CSV and ratings ODS, found on the data page."""
    html = helper.get(DATA_PAGE).text
    directory = re.search(r'href="([^"]+_CQC_directory\.csv)"', html)
    ratings = re.search(r'href="([^"]+_Latest_ratings\.ods)"', html)
    if not directory or not ratings:
        raise RuntimeError("Couldn't find the CQC directory or ratings file on the data page")
    return directory.group(1), ratings.group(1)


def _postcode_ok(postcode, districts):
    return (postcode or "").strip().upper().split(" ")[0] in districts


def _directory(url, districts):
    text = helper.get(url, timeout=180).content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("Name,"))
    found = {}
    for row in csv.DictReader(io.StringIO("\n".join(lines[header:]))):
        if not _postcode_ok(row["Postcode"], districts):
            continue
        found[row["CQC Location ID (for office use only)"]] = row
    return found


def _ods_rows(data, sheet):
    """Rows of one sheet of an ODS file, as lists of cell text, streamed."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive, archive.open("content.xml") as f:
        inside = False
        for event, el in ET.iterparse(f, events=("start", "end")):
            if el.tag == _TABLE + "table":
                if event == "start":
                    inside = el.get(_TABLE + "name") == sheet
                elif inside:
                    return
            elif event == "end" and el.tag == _TABLE + "table-row" and inside:
                cells = []
                for cell in el:
                    if cell.tag != _TABLE + "table-cell":
                        continue
                    repeat = min(int(cell.get(_TABLE + "number-columns-repeated", "1")), 50)
                    cells.extend([" ".join("".join(p.itertext()) for p in cell.findall(_TEXT + "p"))] * repeat)
                yield cells
                el.clear()


def _ratings(url, districts):
    """{location id: {"overall", "published", "ratings", "row"}} for locations in the districts."""
    rows = _ods_rows(helper.get(url, timeout=300).content, "Locations")
    header = next(rows)
    found = {}
    for cells in rows:
        row = dict(zip(header, cells))
        if not _postcode_ok(row.get("Location Post Code"), districts):
            continue
        if row["Service / Population Group"] != "Overall":
            continue
        entry = found.setdefault(row["Location ID"], {"overall": None, "published": None, "ratings": {}, "row": row})
        rating = row["Latest Rating"] if row["Latest Rating"] not in ("", "Not applicable", "Not Rated") else None
        if row["Domain"] == "Overall":
            entry["overall"] = rating
            entry["published"] = datetime.strptime(row["Publication Date"], "%d/%m/%Y").date().isoformat() \
                if row["Publication Date"] else None
        elif row["Domain"] in KEY_QUESTIONS:
            entry["ratings"][KEY_QUESTIONS[row["Domain"]]] = rating
    return found


def _website(url):
    url = (url or "").strip()
    if not url:
        return None
    return url if re.match(r"^https?://", url, re.I) else "https://" + url


def load_locations(postcode_districts):
    directory_url, ratings_url = _links()
    directory = _directory(directory_url, postcode_districts)
    ratings = _ratings(ratings_url, postcode_districts)

    locations = []
    for location_id in sorted(set(directory) | set(ratings)):
        d = directory.get(location_id, {})
        r = ratings.get(location_id, {})
        row = r.get("row", {})
        types = [t.strip() for t in d.get("Service types", "").split("|") if t.strip()]
        locations.append({
            "id": location_id,
            "ods_code": row.get("Location ODS Code") or None,
            "name": d.get("Name") or row.get("Location Name"),
            "address": ", ".join(p.strip() for p in (d.get("Address") or "").split(",") if p.strip())
                       or ", ".join(p for p in (row.get("Location Street Address"), row.get("Location Address Line 2"),
                                                row.get("Location City")) if p),
            "postcode": (d.get("Postcode") or row.get("Location Post Code") or "").strip().upper(),
            "website": _website(d.get("Service's website (if available)")),
            "url": d.get("Location URL") or row.get("URL", "").replace("http://", "https://"),
            "service_types": types,
            "specialisms": [s.strip() for s in d.get("Specialisms/services", "").split("|") if s.strip()],
            "category": row.get("Location Primary Inspection Category") or None,
            "care_home": row.get("Care Home?") == "Y" or any(t in ("Residential homes", "Nursing homes") for t in types),
            "overall": r.get("overall"),
            "published": r.get("published"),
            "ratings": r.get("ratings", {}),
        })
    return locations
