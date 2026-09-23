"""_data/sources.json is the site's register of data sources. The admin page's
data freshness panel reads each source's files and schedule from it, so these
checks keep it complete and consistent. Offline; reads files only.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCES = json.loads((ROOT / "_data" / "sources.json").read_text())
SCHEDULES = {"every 5 minutes", "hourly", "every two hours", "daily", "monthly", "manual"}

# _data files that are site plumbing rather than data from a source.
NOT_SOURCE_DATA = {
    "sources.json", "sponsors.json", "social-posted.json", "newsletter-draft.json",
    "news_digests.json", "fix-my-street-categories.json", "general-election-dates.json",
    "ignore-stations.json", "fuel-stations.json", "weather-today.json", "wards/index.json",
    "newsletter-venues.json",
}


def registered_files():
    return {item["file"] for source in SOURCES for item in source.get("data", [])}


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_source_has_a_short_licence_type(source):
    assert source.get("licence_type"), "add a short licence_type, e.g. \"OGL v3.0\" or \"None stated\""
    assert len(source["licence_type"]) <= 30


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_source_files_exist_and_have_a_known_schedule(source):
    for item in source.get("data", []):
        assert (ROOT / item["file"]).exists(), f"{item['file']} does not exist"
        assert item["schedule"] in SCHEDULES, f"{item['file']}: unknown schedule {item['schedule']!r}"


def test_every_data_file_belongs_to_a_source():
    on_disk = {str(p.relative_to(ROOT / "_data")) for p in (ROOT / "_data").glob("*.json")}
    on_disk |= {"crime/index.json"}
    registered = {f.removeprefix("_data/") for f in registered_files()}
    missing = sorted(on_disk - registered - NOT_SOURCE_DATA)
    assert not missing, f"not listed under any source in sources.json: {missing}"


def test_source_ids_are_unique():
    ids = [s["id"] for s in SOURCES]
    assert len(ids) == len(set(ids))
