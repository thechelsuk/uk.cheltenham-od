"""The published site is built with _config.yml plus _config.production.yml,
which leaves the local admin page out. Jekyll replaces a list setting rather
than merging it, so the production exclude list must repeat the main one;
these checks keep the two in step. Offline; reads files only.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = yaml.safe_load((ROOT / "_config.yml").read_text())
PRODUCTION = yaml.safe_load((ROOT / "_config.production.yml").read_text())


def test_production_excludes_everything_the_main_config_does_plus_admin():
    assert PRODUCTION["exclude"] == BASE["exclude"] + ["admin.md"]


def test_production_config_only_changes_exclude():
    assert set(PRODUCTION) == {"exclude"}


def test_admin_page_is_tracked_not_ignored():
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert "admin.md" not in ignored
    assert (ROOT / "admin.md").exists()


def test_site_builds_use_the_production_config():
    for workflow in ("deploy-pages.yml", "link-checker.yml"):
        text = (ROOT / ".github" / "workflows" / workflow).read_text()
        builds = re.findall(r"jekyll build[^\n]*", text)
        assert builds, workflow
        for build in builds:
            assert "--config _config.yml,_config.production.yml" in build, f"{workflow}: {build}"
