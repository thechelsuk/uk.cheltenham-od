"""Offline tests for the business rates fetcher (business-rates.py): finding
the council's releases, reading its spreadsheets in each of their formats,
leaving out ratepayer names and holiday lets, and refusing a release whose
addresses aren't the properties' own.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime
import importlib.util
import io
import json
import pathlib

import openpyxl
import pytest

SPEC = importlib.util.spec_from_file_location(
    "business_rates", pathlib.Path(__file__).resolve().parents[1] / "business-rates.py")
assert SPEC is not None and SPEC.loader is not None
br = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(br)

EMPTY_HEAD = ["PropertyRef", "AccountName", "PropAddress1", "PropAddress2", "PropAddress3", "PropAddress4",
              "PropAddress5", "PropPostCode", "PropertyDescription", "ExempCode", "ExempDesc",
              "VO-Analysis-Code", "VO-Analysis-Desc", "RV", "StartDate"]
OCC_HEAD = ["PropertyRef", "AccountName", "PropAddress1", "PropAddress2", "PropAddress3", "PropAddress4",
            "PropAddress5", "PropPostCode", "VO-Analysis-Code", "VO-Analysis-Desc", "ReliefCode", "ReliefDesc",
            "RV", "SBRRelief", "StartDate"]


def workbook(head, rows, sheet="Sheet", trailing_blank_columns=0):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(head + [None] * trailing_blank_columns)
    for row in rows:
        ws.append(row)
    wb.create_sheet("Reliefs").append(["Place Ref", "Address"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def empty_row(ref, address="1 High Street", postcode="GL50 1AA", vo="Shop and Premises", rv="12,750",
              start="21/03/2025", reason="Empty for less than 3 months", name="Some Owner Ltd"):
    return [ref, name, address, "Cheltenham", None, None, None, postcode, "SHOP AND PREMISES", "X",
            reason, "CS", vo, rv, start]


def occ_row(ref, address="2 High Street", postcode="GL50 1AB", vo="Offices and Premises", rv=8200,
            relief=None, sbr="no", start=datetime.datetime(2020, 1, 1), name="Jane Smith"):
    return [ref, name, address, "Cheltenham", None, None, None, postcode, "CO", vo, None, relief, rv, sbr, start]


PAGE = """
<a href="/media/aaa/october-2026-empty-properties.xlsx">October 2026 Empty Properties - xlsx - 54 Kb</a>
<a href="/media/bbb/october-2026-occupied-properties.xlsx">October 2026 Occupied Properties - xlsx - 483 Kb</a>
<a href="/media/ccc/june-2026-empty-properties.xlsx">June 2026 Empty Properties</a>
<a href="/media/ddd/january-2026-occupied-properties.xlsx">January 2026 Occupied Properties</a>
<a href="/media/eee/june-2026-occupied-properties.xlsx">June 2026 Occupied Properties</a>
"""


def test_finds_complete_releases_newest_first():
    releases = br.find_releases(PAGE)
    assert [r["key"] for r in releases] == ["2026-10", "2026-06"]
    assert releases[0]["name"] == "October 2026"
    assert releases[0]["empty_url"] == "https://www.cheltenham.gov.uk/media/aaa/october-2026-empty-properties.xlsx"
    assert releases[0]["occupied_url"].endswith("/bbb/october-2026-occupied-properties.xlsx")


@pytest.mark.parametrize("raw, expected", [
    ("12,750", 12750), (4250, 4250), (4250.0, 4250), ("0", 0), (None, 0), ("", 0),
])
def test_reads_rateable_values_as_numbers_or_text(raw, expected):
    assert br.parse_rv(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("21/03/2025", "2025-03-21"), (datetime.datetime(2024, 12, 10), "2024-12-10"), (None, None), ("", None),
])
def test_reads_start_dates_as_text_or_dates(raw, expected):
    assert br.parse_date(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("GL50 4NX", "GL50 4NX"), ("gl519pj", "GL51 9PJ"), ("GL51 OTD", "GL51 0TD"), (" GL53  OQJ ", "GL53 0QJ"),
    ("GL51", None), (None, None),
])
def test_tidies_postcodes(raw, expected):
    assert br.clean_postcode(raw) == expected


def test_reads_both_layouts_and_never_keeps_names():
    empty = br.read_sheet(workbook(EMPTY_HEAD, [empty_row("01"), empty_row("01")], sheet="Empty Properties April 2026"))
    occupied = br.read_sheet(workbook(OCC_HEAD, [occ_row("02")], trailing_blank_columns=40))
    assert [p["ref"] for p in empty] == ["01"]  # repeated rows count once
    assert empty[0] == {
        "ref": "01", "address": "1 High Street, Cheltenham", "postcode": "GL50 1AA", "type": "Shop and Premises",
        "rv": 12750, "since": "2025-03-21", "reason": "Empty for less than 3 months", "relief": None, "sbr": False,
    }
    assert occupied[0]["since"] == "2020-01-01"
    assert "Jane Smith" not in json.dumps(occupied) and "Some Owner" not in json.dumps(empty)


def test_rejects_a_sheet_missing_a_column():
    with pytest.raises(SystemExit):
        br.read_sheet(workbook([h for h in OCC_HEAD if h != "RV"], [occ_row("02")[:12]]))


def test_flags_a_release_whose_addresses_are_billing_addresses():
    good = [{"postcode": "GL50 1AA"}] * 95 + [{"postcode": "GL55 5JA"}] * 5
    bad = [{"postcode": "GL50 1AA"}] * 70 + [{"postcode": "OX2 9DT"}] * 30
    assert br.addresses_look_local(good)
    assert not br.addresses_look_local(bad)


@pytest.mark.parametrize("rv, band", [(0, None), (12000, 0), (12001, 1), (15000, 1), (50999, 2), (51000, 3),
                                      (99999, 3), (100000, 4), (499999, 4), (500000, 5)])
def test_places_values_in_bands(rv, band):
    assert br.band_of(rv) == band


def prop(ref, rv=10000, type_="Shop and Premises", postcode="GL50 1AA", since="2025-01-01", **extra):
    return {"ref": ref, "address": f"{ref} High Street", "postcode": postcode, "type": type_, "rv": rv,
            "since": since, "reason": None, "relief": None, "sbr": False, **extra}


def test_summarises_a_release_without_holiday_lets():
    occupied = [prop("o1", rv=20000), prop("o2", rv=0, type_="Awaiting RV"), prop("h1", type_="Holiday Unit"),
                prop("o3", relief="Mandatory - Registered Charity", sbr=True)]
    empty = [prop("e1", rv=60000, reason="Listed Building/Preservation Order"), prop("h2", type_="Holiday Unit")]
    history = [{"key": "2026-06", "name": "June 2026", "empty_refs": ["e1"]}]
    out = br.build(occupied, empty, {"key": "2026-10", "name": "October 2026"}, history,
                   coords={"GL50 1AA": (51.9, -2.07)})
    s = out["summary"]
    assert (s["occupied"], s["empty"], s["holiday_lets"], s["awaiting_rv"]) == (3, 1, 2, 1)
    assert s["empty_pct"] == 25.0 and s["empty_pct_display"] == "25.0%"
    assert [e["ref"] for e in out["empty"]] == ["e1"]
    assert out["empty"][0]["releases_empty"] == 2 and out["empty"][0]["lat"] == 51.9
    assert (s["release_count"], s["empty_every_release"]) == (2, 1)
    assert "Holiday Unit" not in out["map_types"]
    points = out["postcodes"][0]["p"]
    assert len(points) == 4 and [rv for rv, _, e in points if e is not None] == [60000]
    assert out["map_types"][points[0][1]] == "Shop and Premises"
    assert out["reliefs"] == [{"name": "Mandatory - Registered Charity", "count": 1, "count_display": "1"}]
    assert out["small_business_relief"] == 1
    assert out["exemptions"][0]["name"] == "Listed Building/Preservation Order"
    assert [r["key"] for r in out["releases"]] == ["2026-06", "2026-10"]


def test_refuses_output_that_cannot_be_right():
    occupied = [prop(f"o{i}") for i in range(10)]
    with pytest.raises(SystemExit):
        br.check(occupied, [prop("o1")])  # a property can't be empty and occupied at once
    with pytest.raises(SystemExit):
        br.check(occupied, [])  # far too few properties for Cheltenham
