"""Offline tests for the Fix My Street fetcher (fix-my-street.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import re

import importlib.util
import pathlib


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
