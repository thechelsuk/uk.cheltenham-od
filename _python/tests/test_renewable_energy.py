"""Offline tests for the renewable energy fetcher (renewable-energy.py):
reading the council tables, grouping planning statuses and placing sites.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "renewable_energy", pathlib.Path(__file__).resolve().parents[1] / "renewable-energy.py")
assert SPEC is not None and SPEC.loader is not None
renewable = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renewable)

HEADER = ("Local Authority Code [note 1]", "Local Authority Name  [note 5]", "Region", "Country",
          "Estimated number of households  [note 2]", "Onshore Wind", "Solar PV", "Total")


def test_council_rows_are_read_by_code_with_notes_stripped_from_headings():
    rows = [("Renewable electricity: title",), (), HEADER,
            ("E07000078", "Cheltenham", "South West", "England", 52900, 0.01, 14.46, 14.47),
            ("E07000081", "Gloucester", "South West", "England", 56000, "[X]", 9.5, 9.5),
            ("Grand Total (UK)", "[y]", "[y]", "[y]")]
    table = renewable.council_table(rows)
    assert table["E07000078"]["Solar PV"] == 14.46
    assert table["E07000078"]["households"] == 52900
    assert table["E07000081"]["Onshore Wind"] is None
    assert "Grand Total (UK)" not in table


def test_statuses_fall_into_five_groups():
    group = renewable.status_group
    assert group("Operational") == "Operational"
    assert group("Under Construction") == "Under construction"
    assert group("Awaiting Construction") == "Approved"
    assert group("Application Submitted") == "In planning"
    assert group("Appeal Lodged") == "In planning"
    assert group("Revised") == "In planning"
    assert group("Application Refused") == "Refused, withdrawn or ended"
    assert group("Planning Permission Expired") == "Refused, withdrawn or ended"
    assert group("Something New") == "Refused, withdrawn or ended"


def test_sites_are_kept_within_the_radius_with_iso_dates_and_tidy_names():
    rows = [
        {"Ref ID": "1", "Site Name": "Ladies College  Pool - Solar Panels", "Technology Type": "Solar Photovoltaics",
         "Installed Capacity (MWelec)": "0.16", "Development Status": "Awaiting Construction",
         "Development Status (short)": "Awaiting Construction", "Planning Authority": "Cheltenham\t",
         "X-coordinate": "393856", "Y-coordinate": "\t222337", "Operator (or Applicant)": "",
         "Planning Application Reference": "24/00001/FUL", "Record Last Updated (dd/mm/yyyy)": "05/03/2026",
         "Operational": ""},
        {"Ref ID": "2", "Site Name": "Far Away Wind", "Technology Type": "Wind Onshore",
         "Installed Capacity (MWelec)": "20", "Development Status (short)": "Operational",
         "Planning Authority": "Highland", "X-coordinate": "250000", "Y-coordinate": "850000"},
        {"Ref ID": "3", "Site Name": "No Coordinates", "Technology Type": "Battery",
         "Installed Capacity (MWelec)": "", "Development Status (short)": "Operational",
         "Planning Authority": "Cheltenham", "X-coordinate": "", "Y-coordinate": ""},
    ]
    sites = renewable.nearby_sites(rows, 12)
    assert [s["ref"] for s in sites] == ["1"]
    site = sites[0]
    assert site["name"] == "Ladies College Pool - Solar Panels"
    assert site["technology"] == "Solar"
    assert site["capacity_mw"] == 0.16
    assert site["status"] == "Approved"
    assert site["council"] == "Cheltenham"
    assert site["updated"] == "2026-03-05"
    assert 51.8 < site["lat"] < 52.0 and -2.2 < site["lng"] < -2.0
    assert site["miles"] < 1


def test_a_run_with_the_same_source_files_is_skipped():
    old = {"files": {"council": "a.xlsx", "repd": "b.csv"}}
    assert renewable.unchanged(old, {"council": "a.xlsx", "repd": "b.csv"})
    assert not renewable.unchanged(old, {"council": "a.xlsx", "repd": "c.csv"})
    assert not renewable.unchanged(None, {"council": "a.xlsx"})
