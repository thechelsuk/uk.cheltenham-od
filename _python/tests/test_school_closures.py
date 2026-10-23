"""Offline tests for the school closures fetcher (school-closures.py). The main
run reads a small RSS file and schools list from a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import date

import pytest

import helper

SPEC = importlib.util.spec_from_file_location(
    "school_closures", pathlib.Path(__file__).resolve().parents[1] / "school-closures.py")
assert SPEC is not None and SPEC.loader is not None
sc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sc)

SCHOOLS = [
    {"name": "Springbank Primary Academy", "phase": "Primary",
     "urn_url": "https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/140000"},
    {"name": "St Mary's Church of England Infant School", "phase": "Primary",
     "urn_url": "https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/115600"},
    {"name": "Pate's Grammar School", "phase": "Secondary",
     "urn_url": "https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/137000"},
]


def item(title, description="", pub="Fri, 23 Oct 2026 07:06:54 Z"):
    return (f"<item><guid isPermaLink=\"true\">https://www.gloucestershire.gov.uk/closures/</guid>"
            f"<title>{title}</title><description>{description}</description><pubDate>{pub}</pubDate></item>")


def rss(*items):
    return "﻿<rss version=\"2.0\"><channel><title>Gloucestershire school closures</title>" + \
        "".join(items) + "</channel></rss>"


# --- name matching ---------------------------------------------------------------

def test_norm_ignores_case_punctuation_and_church_of_england_spellings():
    assert sc.norm("St Mary's Church of England Infant School") == sc.norm("ST MARYS C of E Infant School")
    assert sc.norm("Pate’s Grammar School") == sc.norm("Pates Grammar School")
    assert sc.norm("Bourton-on-the-Water Primary School") == "bourton on the water primary school"


def test_parse_title_matches_our_schools_and_reads_status_and_date():
    index = sc.school_index(SCHOOLS, {})
    school, status, day = sc.parse_title("Springbank Primary Academy closed on Friday, 23 October 2026", index)
    assert school["name"] == "Springbank Primary Academy"
    assert (status, day) == ("Closed", "2026-10-23")
    school, status, _ = sc.parse_title("St Marys CofE Infant School partially closed on Monday, 2 November 2026", index)
    assert school["name"] == "St Mary's Church of England Infant School"
    assert status == "Partially closed"


def test_parse_title_skips_schools_and_libraries_that_are_not_ours():
    index = sc.school_index(SCHOOLS, {})
    assert sc.parse_title("Matson Library closed on Friday, 23 October 2026", index) is None
    assert sc.parse_title("Dinglewell Junior School closed on Friday, 23 October 2026", index) is None
    assert sc.parse_title("Something unexpected", index) is None


def test_aliases_map_a_council_name_to_one_of_our_schools():
    index = sc.school_index(SCHOOLS, {"Pates GS": "Pate's Grammar School"})
    school, _, _ = sc.parse_title("Pates GS closed on Friday, 23 October 2026", index)
    assert school["name"] == "Pate's Grammar School"


def test_an_alias_to_a_school_we_do_not_list_is_an_error():
    with pytest.raises(ValueError, match="Nowhere School"):
        sc.school_index(SCHOOLS, {"Somewhere": "Nowhere School"})


# --- parsing the feed --------------------------------------------------------------

def test_parse_closures_builds_one_record_per_school_and_day():
    text = rss(
        item("Springbank Primary Academy closed on Friday, 23 October 2026",
             "School closed to pupils due to a burst water pipe and flooding.&#xD;&#xA;Back Monday. "),
        item("Matson Library closed on Friday, 23 October 2026", "Staff moved to Tuffley."),
    )
    closures, unmatched = sc.parse_closures(text, sc.school_index(SCHOOLS, {}))
    assert closures == [{
        "id": "140000-2026-10-23",
        "urn": "140000",
        "school": "Springbank Primary Academy",
        "phase": "Primary",
        "date": "2026-10-23",
        "status": "Closed",
        "reason": "School closed to pupils due to a burst water pipe and flooding. Back Monday.",
        "posted_iso": "2026-10-23T07:06:54Z",
    }]
    assert unmatched == ["Matson Library closed on Friday, 23 October 2026"]


def test_current_keeps_today_and_later_only():
    closures = [{"date": "2026-10-22"}, {"date": "2026-10-23"}, {"date": "2026-10-26"}]
    assert sc.current(closures, date(2026, 10, 23)) == [{"date": "2026-10-23"}, {"date": "2026-10-26"}]


# --- alert and feed -------------------------------------------------------------------

def test_alert_is_empty_with_no_closures():
    assert sc.build_alert_html([]) == ""


def test_alert_lists_each_closure_with_its_date_written_out():
    html = sc.build_alert_html([{"school": "Springbank Primary Academy", "status": "Closed", "date": "2026-10-23"}])
    assert 'latest-pill-announcements">School</span>' in html
    assert '<a href="/cheltenham-schools/closures">Springbank Primary Academy closed on Friday 23 October 2026</a>' in html


def test_feed_items_link_to_the_history_page_and_use_the_posted_time():
    items = sc.build_atom_items([{
        "id": "140000-2026-10-23", "school": "Springbank Primary Academy", "status": "Closed",
        "date": "2026-10-23", "reason": "Burst pipe.", "posted_iso": "2026-10-23T07:06:54Z",
    }], "https://example.org/cheltenham-schools/closures/history")
    assert items == [{
        "title": "Springbank Primary Academy closed on Friday 23 October 2026",
        "link": "https://example.org/cheltenham-schools/closures/history#140000-2026-10-23",
        "summary": "Burst pipe.",
        "published_iso": "2026-10-23T07:06:54Z",
        "source": "Gloucestershire County Council",
    }]


# --- the full run -----------------------------------------------------------------------

EMPTY_ALERT = "<!-- school_closures_alert_marker starts -->\n\n<!-- school_closures_alert_marker ends -->"


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.content = text.encode("utf-8")


@pytest.fixture
def site(tmp_path, monkeypatch):
    for folder in ("_data", "feeds", "_includes"):
        (tmp_path / folder).mkdir()
    (tmp_path / "_data" / "schools.json").write_text(json.dumps(SCHOOLS))
    (tmp_path / "_data" / "school-closure-aliases.json").write_text(json.dumps({"aliases": {}}))
    (tmp_path / "_includes" / "school-closures-alert.html").write_text(EMPTY_ALERT)
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    monkeypatch.setattr(sc, "today_uk", lambda: date(2026, 10, 23))
    return tmp_path


def test_main_writes_current_history_feed_and_alert(site, monkeypatch):
    monkeypatch.setattr(helper, "get", lambda *a, **k: FakeResponse(rss(
        item("Springbank Primary Academy closed on Friday, 23 October 2026", "Burst pipe."),
        item("Matson Library closed on Friday, 23 October 2026", "Staff moved."),
    )))
    (site / "_data" / "school-closures-history.json").write_text(json.dumps({"records": [{
        "id": "137000-2026-10-01", "urn": "137000", "school": "Pate's Grammar School", "date": "2026-10-01",
        "status": "Closed", "reason": "Snow.", "posted_iso": "2026-10-01T06:00:00Z",
        "first_seen_iso": "2026-10-01T06:47:00Z", "last_seen_iso": "2026-10-01T16:47:00Z",
        "resolved_iso": "2026-10-01T16:47:00Z",
    }]}))

    sc.main()

    data = json.loads((site / "_data" / "school-closures.json").read_text())
    assert [c["school"] for c in data["closures"]] == ["Springbank Primary Academy"]
    assert data["source_url"] == sc.SOURCE_URL
    history = json.loads((site / "_data" / "school-closures-history.json").read_text())
    assert [r["id"] for r in history["records"]] == ["140000-2026-10-23", "137000-2026-10-01"]
    assert history["count"] == 2
    feed = (site / "feeds" / "school-closures.xml").read_text()
    assert "https://example.org/cheltenham-schools/closures/history#140000-2026-10-23" in feed
    assert "Matson" not in feed
    assert "Springbank Primary Academy closed on Friday 23 October 2026" in \
        (site / "_includes" / "school-closures-alert.html").read_text()


def test_main_with_no_closures_keeps_history_and_clears_the_alert(site, monkeypatch):
    (site / "_includes" / "school-closures-alert.html").write_text(
        "<!-- school_closures_alert_marker starts -->\nold\n<!-- school_closures_alert_marker ends -->")
    (site / "_data" / "school-closures-history.json").write_text(json.dumps({"records": [{
        "id": "137000-2026-10-01", "school": "Pate's Grammar School", "date": "2026-10-01",
        "status": "Closed", "last_seen_iso": "2026-10-01T16:47:00Z",
    }]}))
    monkeypatch.setattr(helper, "get", lambda *a, **k: FakeResponse(rss()))

    sc.main()

    assert json.loads((site / "_data" / "school-closures.json").read_text())["closures"] == []
    history = json.loads((site / "_data" / "school-closures-history.json").read_text())
    assert [r["id"] for r in history["records"]] == ["137000-2026-10-01"]
    assert (site / "_includes" / "school-closures-alert.html").read_text() == EMPTY_ALERT


def test_main_stops_on_a_page_that_is_not_the_feed(site, monkeypatch):
    monkeypatch.setattr(helper, "get", lambda *a, **k: FakeResponse("<html>Service unavailable</html>"))
    with pytest.raises(RuntimeError, match="not the closures feed"):
        sc.main()
    assert not (site / "_data" / "school-closures.json").exists()
