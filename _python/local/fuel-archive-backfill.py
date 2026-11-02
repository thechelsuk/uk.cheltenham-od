#!/usr/bin/env python3
"""Rebuild days of _data/fuel-prices-history.json from the official Fuel
Finder CSV as archived by https://github.com/matthewgall/fuelfinder-archive.

That repository commits the government's Fuel Finder CSV (Open Government
Licence v3.0) whenever it changes, about twice a day, so its git history is a
record of past prices. This was used once to fill 13 October to 1 November
2026, when a bug in pi/fuel.py stopped our own prices updating.

For each day it takes the day's last copy, puts its prices on our forecourts
(_data/fuel-stations.json, which it doesn't change) and summarises the day
exactly as pi/fuel.py does, through fuel.build_payload and
fuel_history.summarise_snapshot. Running it again is safe: it replaces the
same days' rows.

  python _python/local/fuel-archive-backfill.py SNAPSHOT_DIR --from 2026-10-13 --to 2026-11-01

SNAPSHOT_DIR holds the downloaded copies, one <commit>.csv each, so a rerun
doesn't download them again. Keep it outside the repository.
"""
import argparse
import copy
import csv
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi"))
import fuel  # noqa: E402
import fuel_history  # noqa: E402
import helper  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "_data" / "fuel-stations.json"
HISTORY = ROOT / "_data" / "fuel-prices-history.json"
REPO = "matthewgall/fuelfinder-archive"
COMMITS_URL = f"https://api.github.com/repos/{REPO}/commits"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{{sha}}/data.csv"

# The CSV's fuel codes, as the API (and so our cache) names them. HVO isn't in our data.
FUEL_CODES = {"E5": "E5", "E10": "E10", "B7S": "B7_STANDARD", "B7P": "B7_PREMIUM", "B10": "B10"}


def iso_stamp(text):
    """'Thu Oct 15 2026 14:12:18 GMT+0000 (Coordinated Universal Time)' as the
    API's ISO form, or None."""
    if not text:
        return None
    parsed = datetime.strptime(text.split(" (")[0], "%a %b %d %Y %H:%M:%S GMT%z")
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def fuel_prices(row):
    """A CSV row's prices in the shape of the API's fuel_prices list."""
    prices = []
    for code, fuel_type in FUEL_CODES.items():
        price = row.get(f"forecourts.fuel_price.{code}")
        if price:
            prices.append({
                "fuel_type": fuel_type,
                "price": round(float(price), 1),
                "price_change_effective_timestamp": iso_stamp(
                    row.get(f"forecourts.price_change_effective_timestamp.{code}")),
            })
    return prices


def last_copy_per_day(commits, start, end):
    """{date: sha} for the last copy of each day from start to end, from
    (sha, ISO time) pairs listed newest first."""
    latest = {}
    for sha, when in commits:
        day = when[:10]
        if start.isoformat() <= day <= end.isoformat():
            latest.setdefault(day, sha)
    return latest


def cache_for_day(cache, csv_text):
    """A copy of our station cache with each forecourt's prices from one
    archived CSV. A forecourt missing from the copy has no prices that day."""
    rows = {r["forecourts.node_id"]: r for r in csv.DictReader(io.StringIO(csv_text))}
    priced = copy.deepcopy(cache)
    for nid, station in priced.items():
        station["fuel_prices"] = fuel_prices(rows[nid]) if nid in rows else []
    return priced


def list_commits(start, end):
    commits, page = [], 1
    while True:
        resp = helper.get(COMMITS_URL, params={
            "path": "data.csv", "since": f"{start.isoformat()}T00:00:00Z",
            "until": f"{end.isoformat()}T23:59:59Z", "per_page": 100, "page": page})
        batch = resp.json()
        commits += [(c["sha"], c["commit"]["committer"]["date"]) for c in batch]
        if len(batch) < 100:
            return commits
        page += 1


def snapshot(folder, sha):
    path = folder / f"{sha}.csv"
    if not path.exists():
        path.write_text(helper.get(RAW_URL.format(sha=sha), timeout=120).text, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshots", type=Path, help="folder for the downloaded copies, outside the repository")
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    args.snapshots.mkdir(parents=True, exist_ok=True)

    cache = json.loads(CACHE.read_text())
    records = json.loads(HISTORY.read_text()).get("records", [])
    for day, sha in sorted(last_copy_per_day(list_commits(args.start, args.end), args.start, args.end).items()):
        payload = fuel.build_payload(cache_for_day(cache, snapshot(args.snapshots, sha)), date.fromisoformat(day))
        row = fuel_history.summarise_snapshot(payload)
        records = fuel_history.upsert_day(records, row)
        print(f"{day}: {row['forecourts']} forecourts, from {sha[:7]}")
    fuel_history.write_history(HISTORY, records)
    print(f"Wrote {len(records)} days to {HISTORY}")


if __name__ == "__main__":
    main()
