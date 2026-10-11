"""Offline tests for the sewage spill log kept by sewage-overflows.py.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "sewage_overflows", pathlib.Path(__file__).resolve().parents[1] / "sewage-overflows.py"
)
sewage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sewage)


def overflow(**overrides):
    base = {
        "id": "SVT00527", "watercourse": "River Chelt", "discharging": False,
        "latest_event_start": "2026-08-20 14:25", "latest_event_end": "2026-08-20 16:13",
        "latest_event_hours": 1.8, "distance_miles": 1.06,
    }
    return {**base, **overrides}


def test_a_finished_spill_is_logged_once():
    spills = sewage.update_spills([], [overflow()], "2026-10-11")
    spills = sewage.update_spills(spills, [overflow()], "2026-10-11")
    assert spills == [{
        "key": "SVT00527 2026-08-20 14:25", "overflow_id": "SVT00527", "watercourse": "River Chelt",
        "start": "2026-08-20 14:25", "end": "2026-08-20 16:13", "hours": 1.8,
    }]


def test_a_spill_still_running_waits_until_it_ends():
    running = overflow(discharging=True, latest_event_start="2026-10-11 09:00", latest_event_end=None,
                       latest_event_hours=None)
    assert sewage.update_spills([], [running], "2026-10-11") == []


def test_new_spills_come_first_and_old_ones_drop_off():
    old = {"key": "SVT1 2024-01-01 10:00", "overflow_id": "SVT1", "watercourse": "Hyde Brook",
           "start": "2024-01-01 10:00", "end": "2024-01-01 12:00", "hours": 2.0}
    newer = overflow(id="SVT2", latest_event_start="2026-10-10 06:00", latest_event_end="2026-10-10 07:30",
                     latest_event_hours=1.5)
    spills = sewage.update_spills([old], [overflow(), newer], "2026-10-11")
    assert [s["start"] for s in spills] == ["2026-10-10 06:00", "2026-08-20 14:25"]


def test_summaries_by_month_and_watercourse():
    spills = [
        {"watercourse": "River Chelt", "start": "2026-10-10 06:00", "hours": 1.5},
        {"watercourse": "River Chelt", "start": "2026-10-02 06:00", "hours": 3.0},
        {"watercourse": "Hyde Brook", "start": "2026-09-30 22:00", "hours": 0.5},
    ]
    assert sewage.summarise(spills, "month") == [
        {"month": "2026-10", "spills": 2, "hours": 4.5},
        {"month": "2026-09", "spills": 1, "hours": 0.5},
    ]
    assert sewage.summarise(spills, "watercourse") == [
        {"watercourse": "River Chelt", "spills": 2, "hours": 4.5, "longest_hours": 3.0},
        {"watercourse": "Hyde Brook", "spills": 1, "hours": 0.5, "longest_hours": 0.5},
    ]
