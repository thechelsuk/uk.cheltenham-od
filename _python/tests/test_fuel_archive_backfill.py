"""Offline tests for local/fuel-archive-backfill.py, which rebuilds days of the
fuel price history from copies of the official Fuel Finder CSV kept in
matthewgall/fuelfinder-archive.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import csv
import importlib.util
import io
import pathlib
from datetime import date

SPEC = importlib.util.spec_from_file_location(
    "fuel_archive_backfill",
    pathlib.Path(__file__).resolve().parents[1] / "local" / "fuel-archive-backfill.py",
)
assert SPEC is not None and SPEC.loader is not None
backfill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backfill)

STAMP = "Thu Oct 15 2026 14:12:18 GMT+0000 (Coordinated Universal Time)"


def row(node_id, **prices):
    """An archive CSV row; prices as code=(price, effective stamp)."""
    out = {"forecourts.node_id": node_id}
    for code in ("E5", "E10", "B7S", "B7P", "B10", "HVO"):
        price, stamp = prices.get(code, ("", ""))
        out[f"forecourts.fuel_price.{code}"] = price
        out[f"forecourts.price_change_effective_timestamp.{code}"] = stamp
    return out


def test_archive_timestamps_become_iso():
    assert backfill.iso_stamp(STAMP) == "2026-10-15T14:12:18Z"
    assert backfill.iso_stamp("") is None


def test_a_row_becomes_fuel_prices_in_the_feeds_codes():
    prices = backfill.fuel_prices(row("A", E10=("169.9000", STAMP), B7S=("195.9", STAMP), HVO=("210.0", STAMP)))
    assert prices == [
        {"fuel_type": "E10", "price": 169.9, "price_change_effective_timestamp": "2026-10-15T14:12:18Z"},
        {"fuel_type": "B7_STANDARD", "price": 195.9, "price_change_effective_timestamp": "2026-10-15T14:12:18Z"},
    ]


def test_each_day_uses_its_last_copy_within_the_range():
    commits = [  # newest first, as the GitHub API lists them
        ("c4", "2026-10-14T15:00:00Z"), ("c3", "2026-10-14T09:00:00Z"),
        ("c2", "2026-10-13T15:00:00Z"), ("c1", "2026-10-12T15:00:00Z"),
    ]
    assert backfill.last_copy_per_day(commits, date(2026, 10, 13), date(2026, 10, 14)) == {
        "2026-10-13": "c2", "2026-10-14": "c4"}


def test_a_day_is_priced_from_its_copy_for_our_forecourts_only():
    cache = {
        "A": {"trading_name": "SHELL A", "distance_miles": 1.0, "fuel_prices": [{"fuel_type": "E10", "price": 150.0}]},
        "B": {"trading_name": "BP B", "distance_miles": 2.0, "fuel_prices": []},
    }
    text = io.StringIO()
    rows = [row("A", E10=("169.9", STAMP)), row("Z", E10=("120.0", STAMP))]
    writer = csv.DictWriter(text, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    priced = backfill.cache_for_day(cache, text.getvalue())
    assert priced["A"]["fuel_prices"][0]["price"] == 169.9
    assert priced["B"]["fuel_prices"] == []
    assert "Z" not in priced
    assert cache["A"]["fuel_prices"][0]["price"] == 150.0  # the real cache is left alone
