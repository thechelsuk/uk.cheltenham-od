#!/usr/bin/env python3
"""How many of the homes sold in Cheltenham each year could a typical full-time earner afford,
written to _data/cheltenham-affordability.json.

A sale counts as affordable when its price is no more than 4.5 times the median gross annual
full-time pay of people who live in Cheltenham that year (ONS Annual Survey of Hours and Earnings,
from _data/cheltenham-earnings.json). 4.5 times pay is roughly the most a lender will usually
offer one borrower. Sales are every Land Registry price-paid record in Cheltenham, both categories,
excluding the "other" property type, the same as house_summary.py.

Two scripts add to the one file, and neither removes the other's years:
  - _python/local/process-land-registry-history.py writes 2008 to 2022, from the full Land Registry
    files that only exist on the owner's machine.
  - this script, run monthly, adds each complete year from 2023 from the sales in
    _data/cheltenham-house-prices.json. That feed only holds the last 48 months, so a year
    it has already written is kept.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

MULTIPLE = 4.5
FIRST_YEAR = 2008                       # the first year of earnings data
OUT = Path(__file__).resolve().parent.parent / "_data" / "cheltenham-affordability.json"
DATA = OUT.parent

TYPE_NAMES = {"detached": "Detached", "semi_detached": "Semi-detached", "terraced": "Terraced", "flat": "Flats"}
FEED_TYPES = {"Detached": "detached", "Semi-detached": "semi_detached", "Terraced": "terraced",
              "Flat-maisonette": "flat"}


def money(n):
    return f"£{int(n):,}"


def block(prices, cap):
    within = sum(1 for p in prices if p <= cap)
    return {
        "sales": len(prices),
        "sales_display": f"{len(prices):,}",
        "within": within,
        "share": round(within * 100 / len(prices), 1),
        "share_display": f"{within * 100 / len(prices):.1f}%",
        "one_in": round(len(prices) / within) if within else None,
        "median_price": int(median(prices)),
        "median_price_display": money(median(prices)),
    }


def build_year(year, sales, pay):
    """One year's figures. `sales` is a list of (price, type) with type one of TYPE_NAMES."""
    cap = int(round(pay * MULTIPLE))
    entry = {"year": year, "pay": int(pay), "pay_display": money(pay), "cap": cap, "cap_display": money(cap),
             **block([p for p, _ in sales], cap)}
    entry["by_type"] = {name: block([p for p, t in sales if t == name], cap) if any(t == name for _, t in sales) else None
                        for name in TYPE_NAMES}
    return entry


def earnings_by_year():
    series = json.loads((DATA / "cheltenham-earnings.json").read_text())["series"]
    return {row["year"]: row["resident"] for row in series if row.get("resident")}


def save(new_years):
    """Merge these years into the file, replacing any with the same year."""
    years = {}
    if OUT.exists():
        years = {y["year"]: y for y in json.loads(OUT.read_text())["years"]}
    years.update({y["year"]: y for y in new_years})
    ordered = [years[k] for k in sorted(years)]
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "HM Land Registry Price Paid Data and ONS Annual Survey of Hours and Earnings",
        "source_url": "https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads",
        "earnings_source_url": "https://www.nomisweb.co.uk/",
        "licence": "Open Government Licence v3.0",
        "multiple": MULTIPLE,
        "first_year": ordered[0]["year"],
        "last_year": ordered[-1]["year"],
        "years": ordered,
    }
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return output


def main():
    pay = earnings_by_year()
    feed = json.loads((DATA / "cheltenham-house-prices.json").read_text())["transactions"]
    first_sale = min(t["date"] for t in feed)
    this_year = date.today().year

    by_year = {}
    for t in feed:
        kind = FEED_TYPES.get(t["property_type"])
        if kind:
            by_year.setdefault(int(t["date"][:4]), []).append((t["amount"], kind))

    # A year is only written once it is over, has earnings, and the feed reaches back to its start.
    years = [build_year(y, sales, pay[y]) for y, sales in sorted(by_year.items())
             if FIRST_YEAR <= y < this_year and y in pay and first_sale <= f"{y}-01-01"]
    if not years:
        print("No complete years to add")
        return
    output = save(years)
    print(f"Wrote {len(output['years'])} years ({output['first_year']}-{output['last_year']}) to {OUT}")


if __name__ == "__main__":
    main()
