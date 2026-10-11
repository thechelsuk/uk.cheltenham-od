"""The published site is built with _config.yml plus _config.production.yml,
which leaves the local admin page and site guide out. Jekyll replaces a list setting rather
than merging it, so the production exclude list must repeat the main one;
these checks keep the two in step. Offline; reads files only.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import json
import pathlib
import re

import yaml

import config

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = yaml.safe_load((ROOT / "_config.yml").read_text())
PRODUCTION = yaml.safe_load((ROOT / "_config.production.yml").read_text())


def test_production_excludes_everything_the_main_config_does_plus_admin():
    assert PRODUCTION["exclude"] == BASE["exclude"] + ["admin.md", "admin/"]


def test_production_config_only_changes_exclude():
    assert set(PRODUCTION) == {"exclude"}


def test_admin_page_is_tracked_not_ignored():
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert "admin" not in ignored and "admin/" not in ignored
    assert (ROOT / "admin" / "admin.md").exists()
    assert (ROOT / "admin" / "guide" / "index.md").exists()


def test_site_builds_use_the_production_config():
    for workflow in ("deploy-pages.yml", "link-checker.yml"):
        text = (ROOT / ".github" / "workflows" / workflow).read_text()
        builds = re.findall(r"jekyll build[^\n]*", text)
        assert builds, workflow
        for build in builds:
            assert "--config _config.yml,_config.production.yml" in build, f"{workflow}: {build}"


BANDS = json.loads((ROOT / "_data" / "distance-bands.json").read_text())


def permalinks():
    found = set()
    for page in (ROOT / "_pages").rglob("*.md"):
        match = re.search(r"^permalink:\s*(\S+)", page.read_text(encoding="utf-8"), re.M)
        if match:
            found.add(match.group(1).strip("\"'"))
    return found


def test_distance_bands_are_the_four_named_bands_in_order():
    bands = BANDS["bands"]
    assert [b["id"] for b in bands] == ["town", "local", "area", "drive"]
    miles = [b["miles"] for b in bands]
    assert miles == sorted(miles)


def test_distance_band_pages_exist():
    existing = permalinks()
    missing = [p["url"] for b in BANDS["bands"] for p in b["pages"] if p["url"] not in existing]
    assert not missing, f"distance-bands.json lists pages that don't exist: {missing}"


def test_config_radii_follow_their_band():
    assert config.CAR_PARKS_RADIUS_M == round(config.LOCAL_MILES * config.METRES_PER_MILE)
    assert config.PARKRUN_MAX_MILES == config.FUEL_RADIUS_MILES == config.DRIVE_MILES
    assert config.SEWAGE_RADIUS_MILES == config.TOWN_MILES
