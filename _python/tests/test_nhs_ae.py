"""Offline tests for the NHS A&E figures fetcher (nhs-ae.py): financial year
pages, CSV parsing, and the store that skips files it has already read.
requests.get is replaced with a fake and the output goes to a temp folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import date

import requests

import helper

SPEC = importlib.util.spec_from_file_location(
    "nhs_ae", pathlib.Path(__file__).resolve().parents[1] / "nhs-ae.py"
)
assert SPEC is not None and SPEC.loader is not None
ae = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ae)

HEADER = ("Period,Org Code,Org name,A&E attendances Type 1,A&E attendances Type 3,"
          "Attendances over 4hrs Type 1,Attendances over 4hrs Type 3,"
          "Patients who have waited 12+ hrs from DTA to admission,"
          "Emergency admissions via A&E - Type 1,Other emergency admissions")


def csv_for(period, code="RTE", type1="12,000", type3="3000", over1="3,500", over3="10"):
    return (f"﻿{HEADER}\n"
            f"{period},RAA,Other trust,1,1,1,1,1,1,1\n"
            f'{period},{code},Gloucestershire,"{type1}",{type3},"{over1}",{over3},250,"4,000",500\n')


def test_financial_year_labels_cover_three_years_back():
    assert ae.financial_year_labels(date(2026, 10, 12)) == ["2026-27", "2025-26", "2024-25", "2023-24"]
    assert ae.financial_year_labels(date(2026, 3, 31))[0] == "2025-26"


def test_number_helpers():
    assert ae.to_int("1,234") == 1234
    assert ae.to_int("-") == 0 and ae.to_int(None) == 0
    assert ae.total({"A&E attendances Type 1": "5", " a&e attendances other": "2", "Other": "9", None: "1"},
                    "a&e attendances") == 7
    assert ae.display(12345) == "12,345"
    assert ae.period_display("2026-08") == "August 2026"


def test_parse_month_reads_the_trusts_row():
    assert ae.parse_month(csv_for("MSitAE-AUGUST-2026")) == {
        "period": "2026-08",
        "attendances": 15000,
        "attendances_display": "15,000",
        "over_4hrs": 3510,
        "over_4hrs_display": "3,510",
        "within_4hrs_pct": 76.6,
        "within_4hrs_display": "76.6%",
        "dta_12hrs": 250,
        "dta_12hrs_display": "250",
        "emergency_admissions": 4500,
        "emergency_admissions_display": "4,500",
    }


def test_parse_month_rejects_other_files_and_bad_periods():
    assert ae.parse_month("Region,Total\nSouth West,1\n") is None
    assert ae.parse_month(csv_for("MSitAE-AUGUST-2026", code="RXX")) is None
    assert ae.parse_month(csv_for("MSitAE-SOMEMONTH-2026")) is None
    zero = ae.parse_month(csv_for("MSitAE-MAY-2026", type1="0", type3="0", over1="0", over3="0"))
    assert zero is not None and zero["within_4hrs_pct"] is None and zero["within_4hrs_display"] == ""


class FakeResponse:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_fetch_text_treats_404_as_no_page(monkeypatch):
    monkeypatch.setattr(ae.requests, "get", lambda url, headers, timeout: FakeResponse(status=404))
    assert ae.fetch_text("https://example.org") is None
    monkeypatch.setattr(ae.requests, "get", lambda url, headers, timeout: FakeResponse("<html>"))
    assert ae.fetch_text("https://example.org") == "<html>"


def fake_site(pages, files, downloads):
    """requests.get for the year pages (by financial year) and the CSV files (by URL)."""
    def get(url, headers, timeout):
        for fy, html in pages.items():
            if url == ae.PAGE_URL.format(fy=fy):
                return FakeResponse(html)
        if url in files:
            downloads.append(url)
            return FakeResponse(files[url])
        return FakeResponse(status=404)
    return get


def test_main_downloads_new_files_once_and_keeps_newest_first(tmp_path, monkeypatch):
    out = tmp_path / "nhs-ae.json"
    monkeypatch.setattr(ae, "OUT", str(out))
    fy = ae.financial_year_labels(date.today())[0]
    base = ae.PAGE_URL.format(fy=fy)
    pages = {fy: '<a href="aug.csv">Aug</a> <a href="jul.csv">Jul</a> <a href="aug.csv">again</a>'
                 ' <a href="summary.csv">Summary</a>'}
    files = {base + "aug.csv": csv_for("MSitAE-AUGUST-2026"), base + "jul.csv": csv_for("MSitAE-JULY-2026"),
             base + "summary.csv": "Region,Total\n"}
    downloads = []
    monkeypatch.setattr(ae.requests, "get", fake_site(pages, files, downloads))

    ae.main()

    data = json.loads(out.read_text())
    assert [m["period"] for m in data["months"]] == ["2026-08", "2026-07"]
    assert data["months"][0]["period_display"] == "August 2026"
    assert data["months"][0]["source_file"] == base + "aug.csv"
    assert {f["url"]: f["period"] for f in data["files"]}[base + "summary.csv"] is None
    assert len(downloads) == 3

    downloads.clear()
    written = []
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.append(payload))
    ae.main()
    assert downloads == [] and written == []


def test_main_keeps_the_first_record_seen_for_a_month(tmp_path, monkeypatch):
    """A month already in the store is not replaced by a later file for the
    same month (months.setdefault): current behaviour, see the PR notes."""
    out = tmp_path / "nhs-ae.json"
    out.write_text(json.dumps({"files": [{"url": "old.csv", "period": "2026-08"}],
                               "months": [{"period": "2026-08", "attendances": 1, "period_display": "August 2026"}]}))
    monkeypatch.setattr(ae, "OUT", str(out))
    fy = ae.financial_year_labels(date.today())[0]
    base = ae.PAGE_URL.format(fy=fy)
    monkeypatch.setattr(ae.requests, "get", fake_site({fy: '<a href="revised.csv">'},
                                                      {base + "revised.csv": csv_for("MSitAE-AUGUST-2026")}, []))
    ae.main()
    data = json.loads(out.read_text())
    assert data["months"][0]["attendances"] == 1
    assert base + "revised.csv" in [f["url"] for f in data["files"]]
