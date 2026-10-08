#!/usr/bin/env python3
"""Rebuild past days of _data/fuel-prices-history.json from the git history of
_data/fuel-prices.json, which has been committed every couple of hours since
7 September 2026.

Run manually, once — pi/fuel.py adds a row for each new day from then on.
Running it again is safe: it takes the last snapshot of each day and replaces
the row for that day, leaving days with no snapshot in git untouched.

  python _python/local/fuel-history-backfill.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fuel_history  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PRICES = "_data/fuel-prices.json"
HISTORY = ROOT / "_data" / "fuel-prices-history.json"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main():
    snapshots = {}
    commits = []
    for commit in git("log", "--format=%H", "--", PRICES).split():
        payload = json.loads(git("show", f"{commit}:{PRICES}"))
        snapshots[commit] = payload
        commits.append((commit, payload["updated_iso"]))

    records = json.loads(HISTORY.read_text()).get("records", []) if HISTORY.exists() else []
    for day, commit in sorted(fuel_history.last_snapshot_per_day(commits).items()):
        row = fuel_history.summarise_snapshot(snapshots[commit])
        records = fuel_history.upsert_day(records, row)
        prem = row["fuels"].get("Prem Diesel", {}).get("forecourts", 0)
        print(f"{day}: {row['forecourts']} forecourts, premium diesel at {prem}")
    fuel_history.write_history(HISTORY, records)
    print(f"Wrote {len(records)} days to {HISTORY}")


if __name__ == "__main__":
    main()
