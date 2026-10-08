"""The daily fuel price history around Cheltenham, shared by pi/fuel.py (which
adds today's row on every run) and local/fuel-history-backfill.py (which
rebuilds past days from the git history of _data/fuel-prices.json).

Each row summarises one day's prices as last checked that day: the cheapest,
average and highest price per fuel across the forecourts within 20 miles whose
price is current (not stale), and how many forecourts were counted. B10 is left
out, as only one forecourt nearby sells it."""
import json

import helper

HISTORY_FUELS = ("Unleaded", "Prem Unleaded", "Diesel", "Prem Diesel")
NO_PRICE = 9999.0


def summarise_snapshot(payload):
    """One history row from a _data/fuel-prices.json payload."""
    columns = payload["columns"]
    prices = {label: [] for label in HISTORY_FUELS}
    forecourts = 0
    for station in payload["stations"]:
        if station.get("stale"):
            continue
        priced = False
        for label, c in zip(columns, station["cells"]):
            val = float(c["val"])
            if val == NO_PRICE:
                continue
            priced = True
            if label in prices:
                prices[label].append(val)
        forecourts += priced
    fuels = {}
    for label in HISTORY_FUELS:
        vals = prices[label]
        if vals:
            fuels[label] = {
                "cheapest": round(min(vals), 1),
                "average": round(sum(vals) / len(vals), 1),
                "highest": round(max(vals), 1),
                "forecourts": len(vals),
            }
    return {"date": payload["updated_iso"], "forecourts": forecourts, "fuels": fuels}


def upsert_day(records, row):
    """Replace any row for row's date with row, oldest first."""
    kept = [r for r in records if r["date"] != row["date"]]
    kept.append(row)
    return sorted(kept, key=lambda r: r["date"])


def last_snapshot_per_day(commits):
    """{date: commit} keeping the newest commit for each date, from
    (commit, date) pairs listed newest first as git log gives them."""
    latest = {}
    for commit, day in commits:
        latest.setdefault(day, commit)
    return latest


def write_history(path, records):
    helper.write_json(path, {
        "source": "GOV.UK fuel price scheme",
        "source_url": "https://www.gov.uk/check-fuel-prices",
        "licence": "Open Government Licence v3.0",
        "refresh": "hourly",
        "fuels": list(HISTORY_FUELS),
        "first_date": records[0]["date"] if records else None,
        "count": len(records),
        "records": records,
    })


def update_history(path, payload):
    """Add or refresh today's row in the history file at `path`."""
    records = json.loads(path.read_text()).get("records", []) if path.exists() else []
    records = upsert_day(records, summarise_snapshot(payload))
    write_history(path, records)
    return records
