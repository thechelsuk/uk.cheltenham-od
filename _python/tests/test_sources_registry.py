"""_data/sources.json is the site's register of data sources. The studio app's
data freshness tab reads each source's files and schedule from it, so these
checks keep it complete and consistent. Offline; reads files only.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCES = json.loads((ROOT / "_data" / "sources.json").read_text())
SCHEDULES = {"every 5 minutes", "hourly", "every two hours", "daily", "weekly", "monthly", "manual"}

# _data files that are site plumbing rather than data from a source.
NOT_SOURCE_DATA = {
    "sources.json", "sponsors.json", "social-posted.json", "newsletter-draft.json", "distance-bands.json",
    "news-digests.json", "fix-my-street-categories.json", "general-election-dates.json",
    "ignore-stations.json", "fuel-stations.json", "weather-today.json", "wards/index.json",
    "newsletter-venues.json",
    # Deploy settings: pages indexnow-urls.py never sends to IndexNow.
    "indexnow.json",
    # Fetcher settings: the indicators public-health.py fetches.
    "public-health-indicators.json",
    # Fetcher settings for ctfc-results.py: club names, referee name fixes and table corrections.
    "ctfc-clubs.json", "ctfc-referee-names.json", "ctfc-corrections.json",
    # Built only from other _data files, each registered under its own source.
    "cheltenham-numbers.json",
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


# Scheduled files with no script of their own: hand-checked lists whose pages
# say "checked monthly" (see data-refresh-reminder.yml), and holidays.json,
# which refresh-monthly.yml fetches with curl.
NO_SCRIPT = {
    "_data/holidays.json", "_data/bin-collections.json", "_data/clubs.json", "_data/third-spaces.json",
    "_data/helpful-contacts.json", "_data/local-support.json", "_data/festivals.json",
    "_data/gloucestershire-cricket.json", "_data/cycle-venues.json", "_data/awareness-dates.json",
    "_data/ev-charging-additions.json", "_data/candidate-events.json",
}


def scheduled_scripts():
    """Every script a runner starts: the refresh workflows and the Pi's manifests."""
    text = "".join(p.read_text() for p in (ROOT / ".github" / "workflows").glob("refresh-*.yml"))
    for name in ("every-5-minutes", "hourly"):
        text += (ROOT / "_python" / "pi" / f"{name}.txt").read_text()
    return set(re.findall(r"_python/[\w/-]+\.py", text)) - {"_python/fetch_status.py"}


def test_each_scheduled_file_names_the_script_that_writes_it():
    # The studio matches a file to its script's run status (_data/fetch-status/)
    # through this field.
    runs = scheduled_scripts()
    for source in SOURCES:
        for item in source.get("data", []):
            script = item.get("script")
            if item["schedule"] == "manual" or item["file"] in NO_SCRIPT:
                assert script is None, f"{item['file']} has a script but nothing runs it on a schedule"
                continue
            assert script, f"{item['file']}: add the \"script\" that writes it"
            assert script in runs, f"{item['file']}: {script} is not run by any workflow or Pi manifest"


# Manual files the monthly reminder doesn't cover yet. Don't add to this list:
# a new manual file goes in the reminder's checklist instead.
NOT_IN_REMINDER_YET = {
    "_data/university.json", "_data/taxi-ranks-curated.json", "_data/council-land-and-assets.json",
    "_data/permit-zone-streets.json", "_data/cheltenham-house-price-history.json", "_data/deprivation.json",
    "_data/event-sources.yml", "_data/covid-timeline.json", "_data/corrections.json", "_data/covid.json",
    "_data/school-closure-aliases.json", "_data/community-risk-register.json",
    "_data/cyber-breaches-survey.json", "_data/town-growth.json",
}


def test_each_manual_file_is_in_the_monthly_reminder():
    # Nothing refreshes a manual file, so data-refresh-reminder.yml's issue must
    # name it, or the _python/local/ script that writes it.
    body = (ROOT / ".github" / "workflows" / "data-refresh-reminder.yml").read_text()
    local = list((ROOT / "_python" / "local").glob("*.py"))
    missing = []
    for source in SOURCES:
        for item in source.get("data", []):
            if item["schedule"] != "manual" or item["file"] in NOT_IN_REMINDER_YET:
                continue
            name = item["file"].removeprefix("_data/")
            writers = [p.name for p in local if name in p.read_text()]
            if name not in body and not any(w in body for w in writers):
                missing.append(item["file"])
    assert not missing, f"add these manual files to data-refresh-reminder.yml: {missing}"


def test_the_not_in_reminder_list_only_shrinks():
    body = (ROOT / ".github" / "workflows" / "data-refresh-reminder.yml").read_text()
    manual = {i["file"] for s in SOURCES for i in s.get("data", []) if i["schedule"] == "manual"}
    stale = sorted(f for f in NOT_IN_REMINDER_YET if f not in manual or f.removeprefix("_data/") in body)
    assert not stale, f"remove from NOT_IN_REMINDER_YET: {stale}"
