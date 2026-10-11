"""Offline tests for the crime backfill check (crime-backfill-check.py),
with police.uk replaced by a stub.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "crime_backfill_check", pathlib.Path(__file__).resolve().parents[1] / "crime-backfill-check.py"
)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def index(totals):
    """An index.json with a town centre and one other neighbourhood per month,
    the town centre holding half of each month's total."""
    return {
        "months": [
            {
                "month": month,
                "neighbourhoods": [
                    {"id": "AB2", "name": "Cheltenham Town Centre", "crime_count": total // 2, "file": f"{month}/AB2.json"},
                    {"id": "AA1", "name": "Hesters Way", "crime_count": total - total // 2, "file": f"{month}/AA1.json"},
                ],
            }
            for month, total in totals.items()
        ]
    }


def saved_files(tmp_path, months):
    for month in months:
        (tmp_path / month).mkdir()
        (tmp_path / month / "AB2.json").write_text(json.dumps({"neighbourhood": {"id": "AB2"}, "boundary": []}))


def test_short_months_are_those_far_below_the_usual_total():
    totals = {"2026-01": 1000, "2025-12": 980, "2025-11": 1020, "2026-02": 6, "2026-03": 300}
    assert check.short_months(totals) == ["2026-02"]


def test_no_api_calls_when_nothing_is_short(monkeypatch):
    def fail(*args):
        raise AssertionError("police.uk should not be called")
    monkeypatch.setattr(check.crime, "fetch_neighbourhood_data", fail)
    assert check.backfilled_months(index({"2026-01": 1000, "2025-12": 990, "2025-11": 1010})) == []


def test_lists_only_months_police_uk_has_filled_in(monkeypatch, tmp_path):
    monkeypatch.setattr(check.crime, "OUTPUT_DIR", tmp_path)
    saved_files(tmp_path, ["2026-02", "2026-03"])
    upstream = {"2026-02": 480, "2026-03": 2}
    monkeypatch.setattr(check.crime, "fetch_neighbourhood_data",
                        lambda neighbourhood, boundary, month: {"crime_count": upstream[month]})
    totals = {"2025-11": 1000, "2025-12": 1000, "2026-01": 1000, "2026-02": 6, "2026-03": 4}
    assert check.backfilled_months(index(totals)) == ["2026-02"]
