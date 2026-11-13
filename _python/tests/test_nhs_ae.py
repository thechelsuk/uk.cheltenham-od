"""Offline tests for the NHS A&E figures fetcher (pi/nhs-ae.py): financial year
pages, CSV parsing, the store that skips files it has already read, and the
check that fails when a published month is missing. requests.get is replaced
with a fake and the output goes to a temp folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import date

import pytest
import requests

import helper

SPEC = importlib.util.spec_from_file_location(
    "nhs_ae", pathlib.Path(__file__).resolve().parents[1] / "pi" / "nhs-ae.py"
)
assert SPEC is not None and SPEC.loader is not None
ae = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ae)



def test_writes_to_the_repository_data_folder():
    # The script runs from _python/pi/ but writes the site's _data/nhs-ae.json.
    root = pathlib.Path(__file__).resolve().parents[2]
    assert pathlib.Path(ae.OUT).resolve() == root / "_data" / "nhs-ae.json"


HEADER = ("Period,Org Code,Org name,A&E attendances Type 1,A&E attendances Type 3,"
          "Attendances over 4hrs Type 1,Attendances over 4hrs Type 3,"
          "Patients who have waited 12+ hrs from DTA to admission,"
          "Emergency admissions via A&E - Type 1,Other emergency admissions")


def csv_for(period, code="RTE", type1="12,000", type3="3000", over1="3,500", over3="10"):
    return (f"﻿{HEADER}\n"
            f"{period},RAA,Other trust,1,1,1,1,1,1,1\n"
            f'{period},{code},Gloucestershire,"{type1}",{type3},"{over1}",{over3},250,"4,000",500\n')


SEPT_20 = date(2026, 9, 20)     # August 2026 (published 10 September) is the latest month
NOV_13 = date(2026, 11, 13)     # October 2026 (published 12 November) is the latest month


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


def test_fetch_text_refuses_a_bot_challenge(monkeypatch):
    """A bot challenge answers 202 with a page that has no links:
    raise_for_status() lets it through, so it would read as "nothing new"."""
    monkeypatch.setattr(ae.requests, "get", lambda url, headers, timeout: FakeResponse("<script>", status=202))
    with pytest.raises(RuntimeError, match="HTTP 202"):
        ae.fetch_text("https://example.org")


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
    fy = ae.financial_year_labels(SEPT_20)[0]
    base = ae.PAGE_URL.format(fy=fy)
    pages = {fy: '<a href="aug.csv">Aug</a> <a href="jul.csv">Jul</a> <a href="aug.csv">again</a>'
                 ' <a href="summary.csv">Summary</a>'}
    files = {base + "aug.csv": csv_for("MSitAE-AUGUST-2026"), base + "jul.csv": csv_for("MSitAE-JULY-2026"),
             base + "summary.csv": "Region,Total\n"}
    downloads = []
    monkeypatch.setattr(ae.requests, "get", fake_site(pages, files, downloads))

    ae.main(SEPT_20)

    data = json.loads(out.read_text())
    assert [m["period"] for m in data["months"]] == ["2026-08", "2026-07"]
    assert data["months"][0]["period_display"] == "August 2026"
    assert data["months"][0]["source_file"] == base + "aug.csv"
    assert {f["url"]: f["period"] for f in data["files"]}[base + "summary.csv"] is None
    assert len(downloads) == 3

    downloads.clear()
    written = []
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.append(payload))
    ae.main(SEPT_20)
    assert downloads == [] and written == []


def test_main_keeps_the_first_record_seen_for_a_month(tmp_path, monkeypatch):
    """A month already in the store is not replaced by a later file for the
    same month (months.setdefault): current behaviour, see the PR notes."""
    out = tmp_path / "nhs-ae.json"
    out.write_text(json.dumps({"files": [{"url": "old.csv", "period": "2026-08"}],
                               "months": [{"period": "2026-08", "attendances": 1, "period_display": "August 2026"}]}))
    monkeypatch.setattr(ae, "OUT", str(out))
    fy = ae.financial_year_labels(SEPT_20)[0]
    base = ae.PAGE_URL.format(fy=fy)
    monkeypatch.setattr(ae.requests, "get", fake_site({fy: '<a href="revised.csv">'},
                                                      {base + "revised.csv": csv_for("MSitAE-AUGUST-2026")}, []))
    ae.main(SEPT_20)
    data = json.loads(out.read_text())
    assert data["months"][0]["attendances"] == 1
    assert base + "revised.csv" in [f["url"] for f in data["files"]]


# The October and September 2026 entries of the real 2026-27 year page, as
# published on 12 November 2026 (trimmed; the links are unchanged).
UPLOADS = "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/"
PAGE_2026_27 = f"""<title>Statistics &raquo; A&amp;E Attendances and Emergency Admissions 2026-27</title>
<h2>Latest publication</h2>
<p>October 2026 published 12 November 2026</p>
<h3>October 2026</h3>
<ul>
<li><a href="{UPLOADS}11/October-26-AE-by-provider-00Qp3.xls">Monthly A&amp;E October 2026 (XLS, 421KB)</a></li>
<li><a href="{UPLOADS}11/October-2026-CSV-WD35qg.csv">Monthly A&amp;E October 2026 (CSV, 28KB)</a></li>
<li><a href="{UPLOADS}11/Statistical-commentary-October-2026-DW43tf.pdf">Statistical commentary October 2026 (PDF, 238KB)</a></li>
</ul>
<h3>September 2026</h3>
<ul>
<li><a href="{UPLOADS}10/September-26-AE-by-provider-B5lUR.xls">Monthly A&amp;E September 2026 (XLS, 423KB)</a></li>
<li><a href="{UPLOADS}10/September-2026-CSV-Re72Eh.csv">Monthly A&amp;E September 2026 (CSV, 28KB)</a></li>
</ul>
"""
OCTOBER_CSV = UPLOADS + "11/October-2026-CSV-WD35qg.csv"
SEPTEMBER_CSV = UPLOADS + "10/September-2026-CSV-Re72Eh.csv"


def store_up_to_september(out):
    """The store as it stood after the hand run on 9 October 2026."""
    out.write_text(json.dumps({
        "files": [{"url": SEPTEMBER_CSV, "period": "2026-09"}],
        "months": [{"period": "2026-09", "attendances": 14773, "period_display": "September 2026"}],
    }))


@pytest.mark.parametrize("today, expected", [
    (date(2026, 11, 12), "2026-09"),    # publication day: allowed until the next day
    (date(2026, 11, 13), "2026-10"),
    (date(2026, 11, 30), "2026-10"),
    (date(2026, 12, 1), "2026-10"),
    (date(2026, 12, 11), "2026-11"),    # 10 December 2026 is the 2nd Thursday
    (date(2027, 1, 14), "2026-11"),
    (date(2027, 1, 15), "2026-12"),     # across the year end
])
def test_expected_latest_period_follows_the_second_thursday(today, expected):
    assert ae.expected_latest_period(today) == expected


def test_check_up_to_date_fails_when_a_published_month_is_missing():
    ae.check_up_to_date({"2026-10": {}, "2026-09": {}}, NOV_13)
    with pytest.raises(RuntimeError, match="newest month is 2026-09.*2026-10 was due"):
        ae.check_up_to_date({"2026-09": {}}, NOV_13)
    with pytest.raises(RuntimeError, match="no months"):
        ae.check_up_to_date({}, NOV_13)


def test_main_picks_up_october_from_the_real_year_page(tmp_path, monkeypatch):
    out = tmp_path / "nhs-ae.json"
    store_up_to_september(out)
    monkeypatch.setattr(ae, "OUT", str(out))
    downloads = []
    monkeypatch.setattr(ae.requests, "get", fake_site(
        {"2026-27": PAGE_2026_27}, {OCTOBER_CSV: csv_for("MSitAE-OCTOBER-2026")}, downloads))

    ae.main(NOV_13)

    assert downloads == [OCTOBER_CSV]
    data = json.loads(out.read_text())
    assert [m["period"] for m in data["months"]] == ["2026-10", "2026-09"]
    assert data["months"][0]["source_file"] == OCTOBER_CSV


def test_main_fails_loudly_when_the_page_hides_october(tmp_path, monkeypatch):
    """The 13 November 2026 run: every page answered, nothing new was found,
    and it reported success. Now it fails, naming the month that's missing."""
    out = tmp_path / "nhs-ae.json"
    store_up_to_september(out)
    monkeypatch.setattr(ae, "OUT", str(out))
    monkeypatch.setattr(ae.requests, "get", fake_site({"2026-27": "<html>no links</html>"}, {}, []))
    with pytest.raises(RuntimeError, match="2026-10 was due"):
        ae.main(NOV_13)
