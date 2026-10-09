"""Offline tests for the combined alerts feed (alerts_feed.py) and the security
alerts feed built by terrorism.py.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import alerts_feed
import helper
import terrorism


def feed_file(tmp_path, name, entries):
    items = [{"title": t, "link": f"https://example.test/{name}#{i}", "summary": s, "published_iso": when,
              "source": "Source"} for i, (t, s, when) in enumerate(entries)]
    path = tmp_path / f"{name}.xml"
    helper.write_items_atom(items, path, f"/feeds/{name}.xml", name, name, "https://example.test/self",
                            f"https://example.test/{name}")
    return path


def test_read_entries_strips_front_matter_and_labels_each_entry(tmp_path):
    path = feed_file(tmp_path, "power-cuts", [("Power cut near GL51 0EX", "2 properties", "2026-10-08T16:35:07+00:00")])
    entries = alerts_feed.read_entries(path, "Power cut")
    assert entries == [{
        "title": "Power cut near GL51 0EX",
        "link": "https://example.test/power-cuts#0",
        "summary": "2 properties",
        "published_iso": "2026-10-08T16:35:07+00:00",
        "source": "Source",
        "category": "Power cut",
    }]


def test_label_is_added_unless_the_title_already_starts_with_it(tmp_path):
    path = feed_file(tmp_path, "closures", [("Lane closures: M5 northbound", "", "2026-10-08T16:35:07+00:00")])
    assert alerts_feed.read_entries(path, "Road closure")[0]["title"] == "Road closure: Lane closures: M5 northbound"
    path = feed_file(tmp_path, "flood", [("Flood Alert: River Chelt", "", "2026-10-08T16:35:07+00:00")])
    assert alerts_feed.read_entries(path, "Flood")[0]["title"] == "Flood Alert: River Chelt"


def test_read_entries_skips_a_feed_that_does_not_exist(tmp_path):
    assert alerts_feed.read_entries(tmp_path / "missing.xml", "Flood") == []


def test_combine_sorts_newest_first_and_caps_the_length(tmp_path):
    flood = feed_file(tmp_path, "flood", [("Flood alert: River Chelt", "", "2026-10-01T09:00:00+00:00")])
    power = feed_file(tmp_path, "power", [
        ("Power cut A", "", "2026-10-03T09:00:00+00:00"),
        ("Power cut B", "", "2026-09-30T09:00:00+00:00"),
    ])
    items = alerts_feed.combine([(flood, "Flood"), (power, "Power cut")], limit=2)
    assert [i["title"] for i in items] == ["Power cut A", "Flood alert: River Chelt"]


def test_atom_writer_adds_a_category_when_given(tmp_path):
    path = tmp_path / "f.xml"
    helper.write_items_atom([{"title": "x", "link": "https://example.test/x", "category": "Flood"}], path,
                            "/feeds/f.xml", "f", "f", "https://example.test/self", "https://example.test/f")
    assert '<category term="Flood"/>' in path.read_text()


def test_security_feed_has_one_entry_per_level_change_dated_by_the_change():
    records = [
        {"published_iso": "2026-04-30T06:09:00+01:00", "level": "SEVERE", "level_title": "Severe",
         "northern_ireland_level": "SUBSTANTIAL", "details": "The current national threat level is SEVERE.",
         "last_seen_iso": "2026-10-08T19:26:58Z"},
        {"published_iso": "2022-02-09", "level": "SUBSTANTIAL", "level_title": "Substantial", "details": ""},
    ]
    items = terrorism.build_atom_items(records, "https://example.test/cheltenham-security-alerts")
    assert items[0]["title"] == "UK threat level: Severe"
    assert items[0]["link"] == "https://example.test/cheltenham-security-alerts#2026-04-30"
    assert items[0]["published_iso"] == "2026-04-30T06:09:00+01:00"
    assert items[0]["summary"] == "The current national threat level is SEVERE."
    assert items[1]["summary"] == "The UK national threat level was set to Substantial."
    assert items[1]["published_iso"] == "2022-02-09T00:00:00+00:00"
