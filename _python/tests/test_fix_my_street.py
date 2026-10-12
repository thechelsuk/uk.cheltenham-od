"""Offline tests for the Fix My Street fetcher (fix-my-street.py). The main
run reads a small RSS file and category list from a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import re
import runpy

import helper


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fms = _load("fix_my_street", "fix-my-street.py")


def test_titles_lose_the_date_and_highways_jargon():
    assert fms.clean_title("Pothole problem, 18th September") == "Pothole"
    assert fms.clean_title("TMC - Defects - CW12 Pothole in road") == "Highways defect: Pothole in road"


def test_descriptions_redact_emails_and_phone_numbers():
    text = fms.clean_description("<p>Call me on 01242 123456 or a.person@example.com</p>")
    assert "[phone removed]" in text and "[email removed]" in text
    assert "<" not in text


def test_long_descriptions_are_cut_at_a_word():
    text = fms.clean_description("word " * 100)
    assert len(text) <= fms.DESCRIPTION_MAX_CHARS + 1 and text.endswith("…")


def test_categories_are_grouped_by_keyword():
    rules = [("Potholes & road surface", re.compile(r"\bpotholes?\b", re.I))]
    assert fms.categorise("Potholes", "Other", rules) == "Potholes & road surface"
    assert fms.categorise("Dog fouling", "Other", rules) == "Other"


def test_history_keeps_old_reports_and_updates_seen_ones():
    existing = [{"id": "1", "published_iso": "2026-10-01", "first_seen_iso": "a"}]
    merged = fms.merge_history(existing, [{"id": "1", "published_iso": "2026-10-01"}, {"id": "2", "published_iso": "2026-10-02"}], "b")
    assert [r["id"] for r in merged] == ["2", "1"]
    assert merged[1]["first_seen_iso"] == "a" and merged[1]["last_seen_iso"] == "b"


RULES = {"default": "Other", "rules": [{"group": "Roads", "keywords": ["pothole", "road surface"]},
                                       {"group": "Litter", "keywords": ["litter", "fly tipping"]}]}

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:georss="http://www.georss.org/georss"><channel>
<item><title>Potholes problem, 3rd October</title><link>https://www.fixmystreet.com/report/7001</link>
<pubDate>Fri, 03 Oct 2026 09:15:00 +0100</pubDate><category>Potholes</category>
<description>&lt;p&gt;Deep hole. Call 01242 123456&lt;/p&gt;</description>
<georss:point>51.9 -2.08</georss:point></item>
<item><title>Bench broken</title><link>https://www.fixmystreet.com/report/7002/</link>
<pubDate>not a date</pubDate><category>Parks</category></item>
<item><title>Fly tipping</title><link>https://www.fixmystreet.com/report/7003</link>
<pubDate>Wed, 17 Sep 2026 18:00:00 +0100</pubDate><category>Fly Tipping</category></item>
</channel></rss>"""


def test_category_rules_match_whole_words_and_plurals(tmp_path):
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(RULES))
    default, rules = fms.load_category_rules(rules_path)
    assert default == "Other"
    assert fms.categorise("Potholes", default, rules) == "Roads"
    assert fms.categorise("Road Surfaces", default, rules) == "Roads"
    assert fms.categorise("Litterbins", default, rules) == "Other"


def test_parse_feed_reads_each_report(tmp_path):
    rules_path, feed_path = tmp_path / "rules.json", tmp_path / "feed.xml"
    rules_path.write_text(json.dumps(RULES))
    feed_path.write_text(FEED)
    items = fms.parse_feed(feed_path, *fms.load_category_rules(rules_path))
    assert items[0] == {"id": "7001", "title": "Potholes", "url": "https://www.fixmystreet.com/report/7001",
                        "category": "Potholes", "group": "Roads", "description": "Deep hole. Call [phone removed]",
                        "lat": 51.9, "lon": -2.08, "published_iso": "2026-10-03T09:15:00+01:00"}
    assert items[1]["id"] == "7002" and items[1]["published_iso"] == "" and items[1]["lat"] is None
    assert items[1]["group"] == "Other"


def test_counts_by_group_and_month():
    items = [{"group": "Roads", "published_iso": "2026-10-03"}, {"group": "Litter", "published_iso": "2026-09-17"},
             {"group": "Roads", "published_iso": ""}]
    assert fms.group_counts(items) == [{"name": "Roads", "count": 2}, {"name": "Litter", "count": 1}]
    assert fms.month_counts(items) == [{"month": "2026-09", "count": 1}, {"month": "2026-10", "count": 1}]


def test_main_run_writes_latest_reports_and_grows_the_history(tmp_path, monkeypatch):
    data = tmp_path / "_data"
    data.mkdir()
    (data / "fix-my-street-categories.json").write_text(json.dumps(RULES))
    (data / "fix-my-street.xml").write_text(FEED)
    (data / "fix-my-street-history.json").write_text(json.dumps({"records": [
        {"id": "6000", "group": "Roads", "published_iso": "2026-08-01T10:00:00+01:00"}]}))
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)

    runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "fix-my-street.py"), run_name="__main__")

    latest = json.loads((data / "fix-my-street.json").read_text())
    assert latest["count"] == 3 and latest["refresh"] == "every two hours"
    assert latest["groups"] == [{"name": "Litter", "count": 1}, {"name": "Other", "count": 1},
                                {"name": "Roads", "count": 1}]
    history = json.loads((data / "fix-my-street-history.json").read_text())
    assert [r["id"] for r in history["records"]] == ["7001", "7003", "6000", "7002"]
    assert history["count_display"] == "4"
    assert history["by_month"] == [{"month": "2026-08", "count": 1}, {"month": "2026-09", "count": 1},
                                   {"month": "2026-10", "count": 1}]
