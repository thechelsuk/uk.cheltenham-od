"""Offline tests for choosing which pages to send to IndexNow (indexnow-urls.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]

SPEC = importlib.util.spec_from_file_location(
    "indexnow_urls", ROOT / "_python" / "indexnow-urls.py"
)
assert SPEC is not None and SPEC.loader is not None
indexnow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(indexnow)

SITE = "https://cheltenham-od.uk"
SINCE = datetime(2026, 11, 10, 14, 0, 10, tzinfo=timezone.utc)


def sitemap(*entries):
    """A sitemap of (path, lastmod) pairs; a lastmod of None leaves the tag out."""
    urls = "".join(
        f"<url><loc>{SITE}{path}</loc>"
        + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
        + "</url>"
        for path, lastmod in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<!-- pages -->{urls}</urlset>"
    )


def test_only_pages_changed_after_the_last_deploy_are_chosen():
    xml = sitemap(
        ("/cheltenham-power-cuts", "2026-11-10T14:05:11+00:00"),
        ("/about-cheltenham", "2026-10-22T21:07:50+01:00"),
    )
    assert indexnow.changed_urls(xml, SINCE) == [f"{SITE}/cheltenham-power-cuts"]


def test_a_page_last_changed_in_the_deployed_commit_is_not_sent_again():
    xml = sitemap(("/cheltenham-power-cuts", "2026-11-10T14:00:10+00:00"))
    assert indexnow.changed_urls(xml, SINCE) == []


def test_times_are_compared_across_time_zones():
    # 15:00:05 BST-style offset is 14:00:05 UTC, before the last deploy;
    # 15:00:15 is after it.
    xml = sitemap(
        ("/before", "2026-11-10T15:00:05+01:00"),
        ("/after", "2026-11-10T15:00:15+01:00"),
        ("/zulu", "2026-11-10T14:30:00Z"),
    )
    assert indexnow.changed_urls(xml, SINCE) == [f"{SITE}/after", f"{SITE}/zulu"]


def test_a_page_with_no_date_is_left_out():
    xml = sitemap(("/undated", None))
    assert indexnow.changed_urls(xml, SINCE) == []


def test_excluded_pages_are_left_out_however_recent():
    xml = sitemap(
        ("", "2026-11-10T14:05:11+00:00"),  # the home page: <loc> is the bare site URL
        ("/cheltenham-train-times", "2026-11-10T14:05:11+00:00"),
        ("/cheltenham-train-times/history", "2026-11-10T14:05:11+00:00"),
        ("/cheltenham-power-cuts", "2026-11-10T14:05:11+00:00"),
    )
    exclude = ["/", "/cheltenham-train-times", "/cheltenham-train-times/history"]
    assert indexnow.changed_urls(xml, SINCE, exclude) == [f"{SITE}/cheltenham-power-cuts"]


def test_the_exclusion_list_covers_the_pages_that_change_on_every_deploy():
    # The home page's lastmod is the build time, and the train times change
    # on almost every 5-minute run; neither is a change worth a crawl.
    exclude = json.loads((ROOT / "_data" / "indexnow.json").read_text())["exclude"]
    assert {"/", "/cheltenham-train-times", "/cheltenham-train-times/history"} <= set(exclude)
