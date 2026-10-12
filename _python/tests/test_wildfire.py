"""Offline tests for the wildfire risk fetcher (wildfire.py) and the outdoor
fires backfill (local/process-wildfire-incidents.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib

import pytest

import helper
import wildfire

SPEC = importlib.util.spec_from_file_location(
    "process_wildfire_incidents",
    pathlib.Path(__file__).resolve().parents[1] / "local" / "process-wildfire-incidents.py",
)
assert SPEC is not None and SPEC.loader is not None
incidents = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(incidents)


def square(ref, offset, date, rating):
    return {"square_reference_pk": ref, "data_date_offset_pk": offset, "dow_date": date, "rating": rating}


# --- wildfire.py: Fire Severity Index ------------------------------------------

def test_level_labels_cover_the_five_fsi_levels():
    assert [wildfire.level_label(n) for n in range(1, 6)] == ["Low", "Moderate", "High", "Very high", "Exceptional"]
    assert wildfire.level_label(None) == "Unknown"


def test_summarise_days_takes_the_highest_square_each_day():
    features = [
        square("SO92", 0, "2026-07-20", 2),
        square("SO91", 0, "2026-07-20", 4),
        square("SP02", 0, "2026-07-20", 4),
        square("SO92", 1, "2026-07-21", 1),
        square("SO91", 1, "2026-07-21", 1),
    ]
    days = wildfire.summarise_days(features)
    assert [d["date"] for d in days] == ["2026-07-20", "2026-07-21"]
    assert days[0]["rating"] == 4
    assert days[0]["label"] == "Very high"
    assert days[0]["squares_at_max"] == ["SO91", "SP02"]
    assert days[1]["rating"] == 1


def test_upsert_history_replaces_the_same_day_and_sorts_newest_first():
    records = [
        {"date": "2026-07-19", "rating": 3, "squares": {"SO92": 3}},
        {"date": "2026-07-20", "rating": 3, "squares": {"SO92": 3}},
    ]
    updated = wildfire.upsert_history(records, {"date": "2026-07-20", "rating": 4, "squares": {"SO92": 4}})
    assert [r["date"] for r in updated] == ["2026-07-20", "2026-07-19"]
    assert updated[0]["rating"] == 4
    assert len(updated) == 2


def test_upsert_history_skips_days_below_high():
    records = [{"date": "2026-07-19", "rating": 3, "squares": {}}]
    updated = wildfire.upsert_history(records, {"date": "2026-07-20", "rating": 2, "squares": {}})
    assert [r["date"] for r in updated] == ["2026-07-19"]


def test_upsert_history_drops_a_day_revised_below_high():
    records = [{"date": "2026-07-20", "rating": 3, "squares": {}}]
    assert wildfire.upsert_history(records, {"date": "2026-07-20", "rating": 2, "squares": {}}) == []


def test_alert_is_empty_below_very_high():
    days = [{"date": "2026-07-20", "rating": 3, "label": "High"}, {"date": "2026-07-21", "rating": 3, "label": "High"}]
    assert wildfire.build_alert_html(days) == ""


def test_alert_names_today_or_tomorrow_at_very_high_or_above():
    days = [
        {"date": "2026-07-20", "rating": 2, "label": "Moderate"},
        {"date": "2026-07-21", "rating": 5, "label": "Exceptional"},
        {"date": "2026-07-22", "rating": 5, "label": "Exceptional"},
    ]
    html = wildfire.build_alert_html(days)
    assert "<h2>Wildfire Risk Alert</h2>" in html
    assert "2026-07-21" in html
    assert "Exceptional (5 of 5)" in html
    # only today and tomorrow make the homepage, not the days after
    assert "2026-07-22" not in html


def test_atom_items_only_cover_high_days_keyed_by_date():
    history = [{"date": "2026-07-19", "rating": 3, "squares": {}}, {"date": "2026-07-18", "rating": 2, "squares": {}}]
    days = [{"date": "2026-07-20", "rating": 4, "label": "Very high"}, {"date": "2026-07-21", "rating": 1, "label": "Low"}]
    items = wildfire.build_atom_items(history, days, "https://example.test/cheltenham-wildfire-risk",
                                      "2026-07-20T06:25:00Z")
    links = [i["link"] for i in items]
    assert links == [
        "https://example.test/cheltenham-wildfire-risk#2026-07-20",
        "https://example.test/cheltenham-wildfire-risk/history#2026-07-19",
    ]
    assert items[0]["title"].startswith("Forecast: Very high fire severity")


def test_rings_to_latlon_swaps_esri_x_y():
    assert wildfire.rings_to_latlon([[[-2.1, 51.9], [-2.0, 51.9]]]) == [[[51.9, -2.1], [51.9, -2.0]]]


# --- local/process-wildfire-incidents.py: outdoor fires backfill ---------------

def test_classify_area_prefers_cheltenham_postcodes_then_the_radius():
    assert incidents.classify_area("GL54", 24.0) == "cheltenham"
    assert incidents.classify_area("GL51", 3.0) == "cheltenham"
    assert incidents.classify_area("GL20", 9.5) == "surrounding"
    assert incidents.classify_area("GL2", 10.5) is None


def test_postcode_district_is_the_outward_code():
    assert incidents.postcode_district("GL54 1AA") == "GL54"
    assert incidents.postcode_district("GL5 1HH") == "GL5"
    assert incidents.postcode_district("gl20 7ab") == "GL20"


def test_nearest_postcode_picks_the_closest_point():
    postcodes = [(51.90, -2.08, "GL50 1AA"), (51.99, -2.16, "GL20 5AA")]
    assert incidents.nearest_postcode(51.98, -2.15, postcodes)[2] == "GL20 5AA"


def test_damage_bands_come_from_the_code_not_the_mangled_description():
    # The published description for code 2 reads "06-Oct" after a spreadsheet date conversion.
    assert incidents.damage_band(2) == "6 to 10 m²"
    assert incidents.damage_band(3) == "11 to 20 m²"
    assert incidents.damage_band(12) == "Over 10,000 m²"
    assert incidents.damage_band(0) == ""


def test_incident_date_is_iso():
    row = {"CALENDAR_YEAR": "2022", "MONTH_CODE": "7", "DAY": "19"}
    assert incidents.incident_date(row) == "2022-07-19"


def test_summarise_counts_by_year_month_area_and_busiest_day():
    fires = [
        {"date": "2022-07-19", "financial_year": "2022/23", "area": "cheltenham", "place": "Leckhampton",
         "district": "Cheltenham", "deliberate": False, "damage_code": 3, "damage": "51 - 100"},
        {"date": "2022-07-19", "financial_year": "2022/23", "area": "surrounding", "place": "Cleeve Hill",
         "district": "Tewkesbury", "deliberate": True, "damage_code": 9, "damage": "Over 10,000"},
        {"date": "2023-04-02", "financial_year": "2023/24", "area": "cheltenham", "place": "Leckhampton",
         "district": "Cheltenham", "deliberate": False, "damage_code": 1, "damage": "Up to 5"},
    ]
    summary = incidents.summarise(fires, ["2022/23", "2023/24"])
    assert summary["totals"]["all"] == 3
    assert summary["totals"]["cheltenham"] == 2
    assert summary["totals"]["deliberate_pct"] == 33
    assert summary["by_year"] == [
        {"year": "2022/23", "cheltenham": 1, "surrounding": 1, "total": 2},
        {"year": "2023/24", "cheltenham": 1, "surrounding": 0, "total": 1},
    ]
    july = next(m for m in summary["by_month"] if m["month"] == "July")
    assert july["total"] == 2
    assert len(summary["by_month"]) == 12
    assert summary["busiest_days"][0] == {"date": "2022-07-19", "fires": 2, "cheltenham": 1, "surrounding": 1}
    assert summary["by_place"][0]["place"] == "Leckhampton"
    assert summary["largest"][0]["place"] == "Cleeve Hill"


def test_summarise_adds_county_totals_and_flags_years_without_locations():
    fires = [{"date": "2024-07-01", "financial_year": "2024/25", "area": "cheltenham", "place": "Pittville",
              "district": "Cheltenham", "deliberate": False, "damage_code": 1, "damage": "Up to 5 m²"}]
    county = {"2024/25": 160, "2025/26": 397}
    located = {"2024/25"}
    summary = incidents.summarise(fires, ["2024/25", "2025/26"], county=county, located=located)
    assert summary["by_year"] == [
        {"year": "2024/25", "cheltenham": 1, "surrounding": 0, "total": 1, "county": 160, "located": True},
        {"year": "2025/26", "cheltenham": 0, "surrounding": 0, "total": 0, "county": 397, "located": False},
    ]
    assert summary["county_total"] == 557


def test_fires_are_counted_by_ward_with_the_last_five_years():
    lsoa_ward = {"E01000001": "Leckhampton", "E01000002": "Leckhampton", "E01000003": "Pittville"}
    fires = [
        {"lsoa": "E01000001", "financial_year": "2012/13"},
        {"lsoa": "E01000002", "financial_year": "2022/23"},
        {"lsoa": "E01000003", "financial_year": "2023/24"},
        {"lsoa": "E01999999", "financial_year": "2023/24"},   # outside Cheltenham's wards
    ]
    years = ["2012/13", "2020/21", "2021/22", "2022/23", "2023/24", "2024/25"]
    assert incidents.by_ward(fires, lsoa_ward, years) == [
        {"ward": "Leckhampton", "fires": 2, "recent": 1},
        {"ward": "Pittville", "fires": 1, "recent": 1},
    ]


# --- wildfire.py: fetching and the main run -------------------------------------


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def feature(ref, offset, date, rating, x=-2.1):
    return {"attributes": square(ref, offset, date, rating),
            "geometry": {"rings": [[[x, 51.8], [x + 0.1, 51.8], [x + 0.1, 51.9]]]}}


def fake_fsi(features, issued=None):
    """helper.get for the FSI service: layer 0 is the squares, layer 1 the issue time."""
    def get(url, params):
        if url.endswith("/0/query"):
            return FakeResponse(features if isinstance(features, dict) else {"features": features})
        return FakeResponse({"features": issued or []})
    return get


def test_fetch_squares_raises_on_a_service_error(monkeypatch):
    monkeypatch.setattr(helper, "get", fake_fsi({"error": {"code": 400}}))
    with pytest.raises(RuntimeError, match="FSI query failed"):
        wildfire.fetch_squares()


def test_fetch_issued_iso_reads_the_issue_date_and_time(monkeypatch):
    monkeypatch.setattr(helper, "get", fake_fsi([], [{"attributes": {"received_date": 1784505600000,
                                                                      "time_received": "06:30"}}]))
    assert wildfire.fetch_issued_iso() == "2026-07-20T06:30"
    monkeypatch.setattr(helper, "get", fake_fsi([], [{"attributes": {"received_date": 1784505600000}}]))
    assert wildfire.fetch_issued_iso() == "2026-07-20T00:00"
    monkeypatch.setattr(helper, "get", fake_fsi([]))
    assert wildfire.fetch_issued_iso() is None


EMPTY_ALERT = "<!-- wildfire_alert_marker starts -->\n\n<!-- wildfire_alert_marker ends -->"


@pytest.fixture
def site(tmp_path, monkeypatch):
    for folder in ("_data", "feeds", "_includes"):
        (tmp_path / folder).mkdir()
    (tmp_path / "_includes" / "wildfire-alert.html").write_text(EMPTY_ALERT)
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    return tmp_path


def test_main_writes_squares_history_feed_and_alert(site, monkeypatch):
    features = [feature("SO92", 0, "2026-07-20", 4), feature("SO91", 0, "2026-07-20", 2, x=-2.2),
                feature("SO92", 1, "2026-07-21", 3), feature("SO91", 1, "2026-07-21", 1, x=-2.2)]
    issued = [{"attributes": {"received_date": 1784505600000, "time_received": "06:30"}}]
    monkeypatch.setattr(helper, "get", fake_fsi(features, issued))
    (site / "_data" / "wildfire-history.json").write_text(json.dumps(
        {"tracking_since": "2026-06-01", "records": [{"date": "2026-07-19", "rating": 3}]}))

    wildfire.main()

    data = json.loads((site / "_data" / "wildfire.json").read_text())
    assert data["issued_iso"] == "2026-07-20T06:30"
    assert data["today"]["rating"] == 4 and [d["date"] for d in data["days"]] == ["2026-07-20", "2026-07-21"]
    so91, so92 = data["squares"]
    assert so92["ref"] == "SO92" and so92["label"] == "Very high"
    assert so92["rings"] == [[[51.8, -2.1], [51.8, -2.0], [51.9, -2.0]]]
    assert [d["rating"] for d in so92["days"]] == [4, 3]
    history = json.loads((site / "_data" / "wildfire-history.json").read_text())
    assert history["tracking_since"] == "2026-06-01"
    assert [(r["date"], r.get("squares")) for r in history["records"]] == [
        ("2026-07-20", {"SO91": 2, "SO92": 4}), ("2026-07-19", None)]
    assert "https://example.org/cheltenham-wildfire-risk#2026-07-20" in (site / "feeds" / "wildfire.xml").read_text()
    assert "Very high (4 of 5) fire severity forecast around Cheltenham on 2026-07-20" in \
        (site / "_includes" / "wildfire-alert.html").read_text()


def test_main_on_a_low_day_logs_nothing_and_clears_the_alert(site, monkeypatch):
    monkeypatch.setattr(helper, "get", fake_fsi([feature("SO92", 0, "2026-10-12", 1)]))
    wildfire.main()
    history = json.loads((site / "_data" / "wildfire-history.json").read_text())
    assert history["records"] == [] and history["tracking_since"] == "2026-10-12"
    assert (site / "_includes" / "wildfire-alert.html").read_text() == EMPTY_ALERT


def test_main_stops_when_the_service_returns_no_squares(site, monkeypatch):
    monkeypatch.setattr(helper, "get", fake_fsi([]))
    with pytest.raises(RuntimeError, match="no squares"):
        wildfire.main()
    assert not (site / "_data" / "wildfire.json").exists()
