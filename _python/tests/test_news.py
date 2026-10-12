"""Offline tests for the news aggregator (news.py): relative times, summary
clean-up, RSS and _posts items, the archive store and paginated pages.
feedparser is replaced with a fake, so no feed is fetched.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime as dt
import importlib.util
import json
import pathlib

import yaml

SPEC = importlib.util.spec_from_file_location(
    "news", pathlib.Path(__file__).resolve().parents[1] / "news.py"
)
assert SPEC is not None and SPEC.loader is not None
news = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(news)


def ago(**delta):
    return dt.datetime.now() - dt.timedelta(**delta)


def test_time_ago_picks_the_largest_whole_unit():
    assert news.time_ago(ago(days=1, hours=3)) == "1 day ago"
    assert news.time_ago(ago(days=3)) == "3 days ago"
    assert news.time_ago(ago(hours=2, minutes=5)) == "2 hours ago"
    assert news.time_ago(ago(hours=1, minutes=5)) == "1 hour ago"
    assert news.time_ago(ago(minutes=5, seconds=10)) == "5 minutes ago"
    assert news.time_ago(ago(minutes=1, seconds=10)) == "1 minute ago"
    assert news.time_ago(ago(seconds=20)) == "just now"


def test_clean_summary_strips_tags_and_shortens_on_a_word():
    assert news.clean_summary(None) == ""
    assert news.clean_summary("<p>Roadworks  on <b>Bath Road</b></p>\n") == "Roadworks on Bath Road"
    assert news.clean_summary("one two three four", max_len=10) == "one two…"


def test_fetch_rss_items_skips_undated_entries_and_keeps_25(monkeypatch):
    entries = [{"title": " Dated ", "link": "https://example.org/a", "summary": "<p>Hi</p>",
                "published_parsed": (2026, 10, 1, 9, 30, 0, 0, 0, 0)},
               {"title": "Undated", "link": "https://example.org/b"}]
    entries += [{"title": f"n{i}", "published_parsed": (2026, 9, 1, 0, 0, 0, 0, 0, 0)} for i in range(30)]
    monkeypatch.setattr(news.feedparser, "parse", lambda url: {"items": entries})

    items = news.fetch_rss_items({"url": "https://example.org/feed", "title": "Echo", "color": "#123456"})

    assert len(items) == 24  # only the first 25 entries are read, and one of those is undated
    assert items[0] == {
        "title": "Dated",
        "link": "https://example.org/a",
        "source": "Echo",
        "source_color": "#123456",
        "published_iso": "2026-10-01T09:30:00",
        "summary": "Hi",
    }
    assert items[1]["source_color"] == "#123456" and items[1]["link"] == ""


def test_slug_from_filename_drops_the_date():
    assert news.slug_from_filename(pathlib.Path("2026-09-14-council-tax-added.md")) == "council-tax-added"
    assert news.slug_from_filename(pathlib.Path("about.md")) == "about"


def test_as_datetime_accepts_dates_datetimes_and_strings():
    assert news.as_datetime(dt.date(2026, 9, 14)) == dt.datetime(2026, 9, 14)
    stamp = dt.datetime(2026, 9, 14, 8, 0)
    assert news.as_datetime(stamp) is stamp
    assert news.as_datetime("2026-09-14 08:15:00") == dt.datetime(2026, 9, 14, 8, 15)


def test_fetch_local_items_reads_dated_posts(tmp_path):
    posts = tmp_path / "_posts"
    posts.mkdir()
    (posts / "2026-09-14-council-tax-added.md").write_text(
        "---\ntitle: Council tax added \ndate: 2026-09-14 08:00:00\ndescription: New bands page\n---\nBody\n")
    (posts / "2026-09-15-draft.md").write_text("---\ntitle: No date\n---\n")
    (posts / "notes.md").write_text("No front matter at all\n")

    items = news.fetch_local_items({"title": "Cheltenham OD"}, tmp_path)

    assert items == [{
        "title": "Council tax added",
        "link": "/news/council-tax-added.html",
        "source": "Cheltenham OD",
        "source_color": "#7a7973",
        "published_iso": "2026-09-14T08:00:00",
        "summary": "New bands page",
    }]


def test_load_archive_keys_items_by_link_and_tolerates_bad_files(tmp_path):
    archive = tmp_path / "news_archive.json"
    assert news.load_archive(archive) == {}
    archive.write_text("{not json")
    assert news.load_archive(archive) == {}
    archive.write_text(json.dumps({"items": [{"link": "/a", "title": "A"}, {"title": "no link"}]}))
    assert news.load_archive(archive) == {"/a": {"link": "/a", "title": "A"}}


def test_write_paginated_page_writes_front_matter_and_sponsor_include(tmp_path):
    page = tmp_path / "page-3.md"
    news.write_paginated_page(page, 3)
    _, front, body = page.read_text().split("---\n", 2)
    meta = yaml.safe_load(front)
    assert meta["permalink"] == "/cheltenham-news/page/3/"
    assert meta["page_num"] == 3 and meta["robots"] == "noindex,follow"
    assert body.strip() == "{% include sponsor.html %}"
