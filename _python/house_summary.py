#!/usr/bin/env python3
"""
build_house_summary.py

Single responsibility: read _data/cheltenham-house-prices.json (written by
extract_house_prices.py) and compute every number the site's markdown pages
need, pre-formatted for direct Liquid output.

Writes _data/house-summary.json. Markdown pages should contain plain,
hand-written prose with Liquid placeholders like:

    Cheltenham has seen {{ site.data.house-summary.current.count_display }}
    properties change hands over the past year,
    {{ site.data.house-summary.current.count_change }}.

No prose is generated in Python. No maths happens in Liquid. This script
does the maths and the formatting (commas, £ signs, "up X% (Y: Z)" strings);
Liquid just drops values into place.

Re-run this any time the raw data changes. Cheap and fast - no network calls.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median, mean

# ---------------------------------------------------------------------------
DRY_RUN = False
RAW_DATA_PATH = Path("_data/cheltenham-house-prices.json")
SUMMARY_DATA_PATH = Path("_data/house-summary.json")
HISTORY_DATA_PATH = Path("_data/cheltenham-house-price-history.json")
# ---------------------------------------------------------------------------


def load_transactions() -> tuple[list[dict], dict]:
    if not RAW_DATA_PATH.exists():
        print(f"ERROR: {RAW_DATA_PATH} not found. Run extract_house_prices.py first.", file=sys.stderr)
        sys.exit(1)
    raw = json.loads(RAW_DATA_PATH.read_text(encoding="utf-8"))
    return raw["transactions"], raw


def normalize_property_type(t: dict) -> str:
    """Table display uses `| default: 'Other'` for blank/null property_type -
    match that behaviour here so domestic-split counts agree with what's
    visibly shown in the table. Never compare t['property_type'] directly.
    Also normalizes case/whitespace, since the Land Registry label for this
    value may not be the exact literal string "Other" (e.g. "other", "OTHER",
    or trailing whitespace from the SPARQL result)."""
    pt = t.get("property_type")
    if not pt or not pt.strip():
        return "Other"
    if pt.strip().lower() == "other":
        return "Other"
    return pt.strip()


def compute_stats(transactions: list[dict]) -> dict:
    prices = [t["amount"] for t in transactions if t["amount"]]
    if not prices:
        return {"count": 0}
    return {
        "count": len(prices),
        "median": int(median(prices)),
        "mean": int(mean(prices)),
        "min": min(prices),
        "max": max(prices),
    }


def pct_change(new: float, old: float) -> float | None:
    if not old:
        return None
    return ((new - old) / old) * 100


def money(n: int) -> str:
    return f"£{n:,}"


def change_str(current: float, prior: float, label: str, currency: bool = False) -> str | None:
    """'up 12% (2025: 1,900)' / 'down 4% (2025: £320,000)' - or None if no prior data."""
    change = pct_change(current, prior)
    if change is None:
        return None
    direction = "up" if change >= 0 else "down"
    prior_str = money(int(prior)) if currency else f"{int(prior):,}"
    return f"{direction} {abs(change):.0f}% ({label}: {prior_str})"


def split_rolling_12mo(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    now = datetime.now(timezone.utc)
    cutoff_12 = now - timedelta(days=365)
    cutoff_24 = now - timedelta(days=730)
    current, prior = [], []
    for t in transactions:
        if not t["date"]:
            continue
        d = datetime.fromisoformat(t["date"]).replace(tzinfo=timezone.utc)
        if d >= cutoff_12:
            current.append(t)
        elif d >= cutoff_24:
            prior.append(t)
    return current, prior


def bucket_by_calendar_year(transactions: list[dict]) -> dict[str, list[dict]]:
    by_year: dict[str, list[dict]] = {}
    for t in transactions:
        if not t["date"]:
            continue
        by_year.setdefault(t["date"][:4], []).append(t)
    return by_year


def build_period_block(current_txns: list[dict], prior_txns: list[dict], prior_label: str) -> dict:
    """One block of fully pre-formatted values: overall, new-build, domestic - all
    with _display values and _change strings ready for direct Liquid output."""
    overall = compute_stats(current_txns)
    prior_overall = compute_stats(prior_txns) if prior_txns else {"count": 0}

    new_build = compute_stats([t for t in current_txns if t["new_build"]])
    prior_new_build = compute_stats([t for t in prior_txns if t["new_build"]]) if prior_txns else {"count": 0}

    domestic = compute_stats([t for t in current_txns if normalize_property_type(t) != "Other"])
    prior_domestic = compute_stats([t for t in prior_txns if normalize_property_type(t) != "Other"]) if prior_txns else {"count": 0}

    other_count = len([t for t in current_txns if normalize_property_type(t) == "Other"])
    prior_other_count = len([t for t in prior_txns if normalize_property_type(t) == "Other"])

    block = {
        "count": overall.get("count", 0),
        "count_display": f"{overall.get('count', 0):,}",
        "count_change": change_str(overall.get("count", 0), prior_overall.get("count", 0), prior_label),

        "median_display": money(overall["median"]) if overall.get("count") else None,
        "median_change": change_str(overall.get("median", 0), prior_overall.get("median", 0), prior_label, currency=True)
            if overall.get("count") and prior_overall.get("count") else None,

        "mean_display": money(overall["mean"]) if overall.get("count") else None,
        "mean_change": change_str(overall.get("mean", 0), prior_overall.get("mean", 0), prior_label, currency=True)
            if overall.get("count") and prior_overall.get("count") else None,

        "min_display": money(overall["min"]) if overall.get("count") else None,
        "max_display": money(overall["max"]) if overall.get("count") else None,
        "range_prior_display": (
            f"{prior_label}: {money(prior_overall['min'])}\u2013{money(prior_overall['max'])}"
            if prior_overall.get("count") else None
        ),

        "new_build_count": new_build.get("count", 0),
        "new_build_count_display": f"{new_build.get('count', 0):,}",
        "new_build_count_change": change_str(new_build.get("count", 0), prior_new_build.get("count", 0), prior_label)
            if new_build.get("count") else None,
        "new_build_median_display": money(new_build["median"]) if new_build.get("count") else None,
        "new_build_median_change": change_str(new_build.get("median", 0), prior_new_build.get("median", 0), prior_label, currency=True)
            if new_build.get("count") and prior_new_build.get("count") else None,

        "domestic_count": domestic.get("count", 0),
        "domestic_count_display": f"{domestic.get('count', 0):,}",
        "domestic_count_change": change_str(domestic.get("count", 0), prior_domestic.get("count", 0), prior_label)
            if domestic.get("count") else None,
        "domestic_mean_display": money(domestic["mean"]) if domestic.get("count") else None,
        "domestic_mean_change": change_str(domestic.get("mean", 0), prior_domestic.get("mean", 0), prior_label, currency=True)
            if domestic.get("count") and prior_domestic.get("count") else None,
        "domestic_median_display": money(domestic["median"]) if domestic.get("count") else None,

        "other_count": other_count,
        "other_count_prior": prior_other_count,
        "other_note": (
            f"{other_count} sale{'s' if other_count != 1 else ''} this period and "
            f"{prior_other_count} the period before "
            f"{'were' if (other_count + prior_other_count) != 1 else 'was'} classed as \"Other\"."
        ) if (other_count + prior_other_count) else None,
    }
    return block


def build_by_year(transactions: list[dict]) -> list[dict]:
    by_year = bucket_by_calendar_year(transactions)
    years_sorted = sorted(by_year.keys(), reverse=True)
    results = []
    for i, year in enumerate(years_sorted):
        prior_year = years_sorted[i + 1] if i + 1 < len(years_sorted) else None
        prior_txns = by_year.get(prior_year, []) if prior_year else []
        block = build_period_block(by_year[year], prior_txns, prior_year or "prior year")
        block["year"] = year
        results.append(block)
    return results


def build_overall_since_history(transactions: list[dict]) -> dict | None:
    """Every sale since the first year of the history file (see
    _python/local/process-land-registry-history.py): its yearly figures up to
    its last year, plus every live transaction after that. None if there is no
    history file, so the page falls back gracefully."""
    if not HISTORY_DATA_PATH.exists():
        return None
    history = json.loads(HISTORY_DATA_PATH.read_text(encoding="utf-8"))
    live = [t for t in transactions if t.get("amount") and t["date"] and int(t["date"][:4]) > history["last_year"]]
    count = sum(y["count"] for y in history["years"]) + len(live)
    total = sum(y["total"] for y in history["years"]) + sum(t["amount"] for t in live)
    lowest = min([y["min"] for y in history["years"]] + [t["amount"] for t in live])
    highest = max([y["max"] for y in history["years"]] + [t["amount"] for t in live])
    latest = max(t["date"] for t in transactions if t["date"])
    return {
        "first_year": history["first_year"],
        "to_month": datetime.fromisoformat(latest).strftime("%B %Y"),
        "count": count,
        "count_display": f"{count:,}",
        "mean_display": money(int(total / count)),
        "min_display": money(lowest),
        "max_display": money(highest),
    }


def write_summary(payload: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"--- DRY RUN: would write {SUMMARY_DATA_PATH} ---")
        print(json.dumps(payload, indent=2)[:2000] + "\n... (truncated)")
        return
    SUMMARY_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_DATA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {SUMMARY_DATA_PATH}")


def main():
    transactions, raw = load_transactions()
    print(f"Loaded {len(transactions)} transactions (source generated_at: {raw.get('generated_at')}).")

    current_txns, prior_txns = split_rolling_12mo(transactions)
    current_year = str(datetime.now(timezone.utc).year - 1)  # rolling-12mo label, financial-report style
    rolling = build_period_block(current_txns, prior_txns, current_year)

    full_dataset = compute_stats(transactions)
    full_dataset_display = {
        "count_display": f"{full_dataset.get('count', 0):,}",
        "median_display": money(full_dataset["median"]) if full_dataset.get("count") else None,
        "mean_display": money(full_dataset["mean"]) if full_dataset.get("count") else None,
        "min_display": money(full_dataset["min"]) if full_dataset.get("count") else None,
        "max_display": money(full_dataset["max"]) if full_dataset.get("count") else None,
        "months": raw.get("months_fetched"),
    }

    by_year = build_by_year(transactions)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_generated_at": raw.get("generated_at"),
        "current": rolling,          # rolling 12mo vs prior 12mo - for the main summary page
        "full_dataset": full_dataset_display,
        "by_year": by_year,          # calendar-year blocks, most recent first - for year subpages
        "overall": build_overall_since_history(transactions),  # every sale since the history file's first year
    }

    write_summary(payload, DRY_RUN)


if __name__ == "__main__":
    main()