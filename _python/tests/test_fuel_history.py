"""Offline tests for the fuel price history: the daily summary shared by
pi/fuel.py and the git backfill (fuel_history.py), and the UK weekly average
fetcher (fuel-uk-weekly.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import fuel_history

SPEC = importlib.util.spec_from_file_location(
    "fuel_uk_weekly", pathlib.Path(__file__).resolve().parents[1] / "fuel-uk-weekly.py"
)
uk_weekly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(uk_weekly)


def cell(val):
    return {"display": f"{val}p", "val": str(val), "cheapest": False}


NONE = {"display": "–", "val": "9999", "cheapest": False}


def snapshot():
    return {
        "updated_iso": "2026-09-07",
        "columns": ["Unleaded", "Prem Unleaded", "Diesel", "Prem Diesel", "B10"],
        "stations": [
            {"stale": False, "cells": [cell(140.9), cell(160.9), cell(150.9), NONE, cell(149.9)]},
            {"stale": False, "cells": [cell(145.1), NONE, cell(152.9), cell(170.9), NONE]},
            {"stale": True, "cells": [cell(120.0), cell(120.0), cell(120.0), cell(120.0), NONE]},
            {"stale": False, "cells": [NONE, NONE, NONE, NONE, NONE]},
        ],
    }


def test_summary_counts_only_current_prices_and_drops_b10():
    row = fuel_history.summarise_snapshot(snapshot())
    assert row["date"] == "2026-09-07"
    assert row["forecourts"] == 2
    assert list(row["fuels"]) == ["Unleaded", "Prem Unleaded", "Diesel", "Prem Diesel"]
    assert row["fuels"]["Unleaded"] == {"cheapest": 140.9, "average": 143.0, "highest": 145.1, "forecourts": 2}
    assert row["fuels"]["Prem Diesel"] == {"cheapest": 170.9, "average": 170.9, "highest": 170.9, "forecourts": 1}


def test_summary_leaves_out_a_fuel_nobody_sells():
    snap = snapshot()
    for s in snap["stations"]:
        s["cells"][3] = NONE
    assert "Prem Diesel" not in fuel_history.summarise_snapshot(snap)["fuels"]


def test_upsert_day_overwrites_today_and_keeps_date_order():
    records = [{"date": "2026-09-08", "forecourts": 1}, {"date": "2026-09-07", "forecourts": 1}]
    updated = fuel_history.upsert_day(records, {"date": "2026-09-08", "forecourts": 5})
    assert [(r["date"], r["forecourts"]) for r in updated] == [("2026-09-07", 1), ("2026-09-08", 5)]


def test_last_snapshot_per_day_keeps_the_latest_commit_each_day():
    # git log lists newest first
    commits = [("c4", "2026-09-08"), ("c3", "2026-09-08"), ("c2", "2026-09-07"), ("c1", "2026-09-07")]
    assert fuel_history.last_snapshot_per_day(commits) == {"2026-09-08": "c4", "2026-09-07": "c2"}


CSV = (
    "﻿Date,ULSP (Ultra low sulphur unleaded petrol) Pump price in pence/litre,"
    "ULSD (Ultra low sulphur diesel) Pump price in pence/litre,ULSP Duty,ULSD Duty,ULSP VAT,ULSD VAT\n"
    "24/08/2026,170.10,193.20,52.95,52.95,20,20\n"
    "31/08/2026,171.00,194.00,52.95,52.95,20,20\n"
    "07/09/2026,171.50,194.60,52.95,52.95,20,20\n"
)


def test_weekly_csv_parses_iso_dates_and_keeps_weeks_covering_local_data():
    weeks = uk_weekly.parse_weekly_csv(CSV, since="2026-09-07")
    assert weeks == [
        {"week": "2026-08-31", "unleaded": 171.0, "diesel": 194.0},
        {"week": "2026-09-07", "unleaded": 171.5, "diesel": 194.6},
    ]
