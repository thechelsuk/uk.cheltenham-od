"""Offline tests for the childcare fetcher (childcare.py): the Ofsted report link.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import helper

SPEC = importlib.util.spec_from_file_location(
    "childcare", pathlib.Path(__file__).resolve().parents[1] / "childcare.py"
)
assert SPEC is not None and SPEC.loader is not None
childcare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(childcare)


def test_report_url_points_at_the_providers_ofsted_page():
    assert childcare.report_url("2639045") == "https://reports.ofsted.gov.uk/provider/16/2639045"


def test_report_url_is_none_when_ofsted_has_no_page_for_the_provider(monkeypatch):
    url = "https://reports.ofsted.gov.uk/provider/16/2897017"
    monkeypatch.setattr(helper, "dead_websites", lambda: {helper._website_key(url): "Ofsted has no page for this provider"})
    assert childcare.report_url("2897017") is None
