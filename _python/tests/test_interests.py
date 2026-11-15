"""Offline tests for the points-of-interest fetcher's web address clean-up.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import interests


def test_normalize_url():
    assert interests.normalize_url(" www.example.org ") == "http://www.example.org"
    assert interests.normalize_url("https://example.org") == "https://example.org"
    assert interests.normalize_url("") == ""
