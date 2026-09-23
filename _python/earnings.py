#!/usr/bin/env python3
"""Fetch median earnings for Cheltenham from the ONS Annual Survey of Hours
and Earnings (ASHE), via Nomis — a public, keyless API — and write
_data/cheltenham-earnings.json:

- Median annual pay for full-time employees, by where they live (residents)
  and where they work (workplace), for every year Nomis has for Cheltenham
- The same by-residence figure for Gloucestershire, the South West and
  England, for comparison, plus male and female full-time medians
- The latest year's annual, weekly and hourly medians side by side
- The ONS confidence figure for each year, so the page can flag noisy years

ASHE is published once a year in the autumn; refreshed monthly with the other
Nomis data.

Source: https://www.nomisweb.co.uk/api/v01/
"""

import datetime
import json

import config
import helper

RESIDENT = "NM_30_1"   # ASHE - resident analysis (where employees live)
WORKPLACE = "NM_99_1"  # ASHE - workplace analysis (where employees work)
START_YEAR = 2008      # Nomis holds no Cheltenham figures before this

CHELTENHAM = config.AREA_CODE
COMPARATORS = {"gloucestershire": "E10000013", "south_west": "E12000009", "england": "E92000001"}

# Nomis codes: sex 8 = full-time employees, 1 = male full-time, 3 = female full-time;
# item 2 = median; pay 7 = annual gross, 1 = weekly gross, 5 = hourly gross.
FULL_TIME, MALE_FT, FEMALE_FT = 8, 1, 3
MEDIAN = 2
ANNUAL, WEEKLY, HOURLY = 7, 1, 5
VALUE, CONFIDENCE = 20100, 20701


def fetch(dataset, geography, sex, pay, measures=VALUE, date=None):
    """{year: value} for one geography/sex/pay/measure. Years Nomis has no
    figure for (suppressed or not surveyed) come back empty and are left out."""
    date = date or f"{START_YEAR}-{datetime.date.today().year}"
    rows = helper.nomis_rows(dataset, geography=geography, date=date, sex=sex, item=MEDIAN, pay=pay,
                             measures=measures, select="date_name,obs_value")
    return {int(r["DATE_NAME"]): float(r["OBS_VALUE"]) for r in rows if r["OBS_VALUE"]}


def pounds(value, pence=False):
    return f"£{value:,.2f}" if pence else f"£{int(round(value)):,}"


def reliability(cv):
    """The ONS's own bands for a coefficient of variation (%)."""
    if cv is None:
        return None
    if cv <= 5:
        return "Precise"
    if cv <= 10:
        return "Reasonably precise"
    if cv <= 20:
        return "Acceptable"
    return "Unreliable"


def percent_change(new, old):
    return round((new - old) / old * 100, 1)


def signed(value):
    return f"{value:+.1f}%".replace("-", "−")


def main():
    resident = fetch(RESIDENT, CHELTENHAM, FULL_TIME, ANNUAL)
    if not resident:
        raise SystemExit("Nomis returned no resident earnings for Cheltenham")
    workplace = fetch(WORKPLACE, CHELTENHAM, FULL_TIME, ANNUAL)
    confidence = fetch(RESIDENT, CHELTENHAM, FULL_TIME, ANNUAL, measures=CONFIDENCE)
    male = fetch(RESIDENT, CHELTENHAM, MALE_FT, ANNUAL)
    female = fetch(RESIDENT, CHELTENHAM, FEMALE_FT, ANNUAL)
    comparators = {name: fetch(RESIDENT, code, FULL_TIME, ANNUAL) for name, code in COMPARATORS.items()}

    years = sorted(set(resident) | set(workplace))
    series = []
    for year in years:
        cv = confidence.get(year)
        entry = {
            "year": year,
            "resident": resident.get(year),
            "workplace": workplace.get(year),
            "male": male.get(year),
            "female": female.get(year),
            "confidence": cv,
            "reliability": reliability(cv),
        }
        for name, values in comparators.items():
            entry[name] = values.get(year)
        for key in ("resident", "workplace", "male", "female", *comparators):
            entry[f"{key}_display"] = pounds(entry[key]) if entry[key] else None
        series.append(entry)

    first_year, latest_year = min(resident), max(resident)

    # Latest year: annual, weekly and hourly medians for Cheltenham, the South West and England.
    latest_rows = []
    for label, pay, pence in (("Annual pay", ANNUAL, False), ("Weekly pay", WEEKLY, True), ("Hourly pay", HOURLY, True)):
        row = {"label": label}
        for name, code in {"cheltenham": CHELTENHAM, "south_west": COMPARATORS["south_west"], "england": COMPARATORS["england"]}.items():
            value = fetch(RESIDENT, code, FULL_TIME, pay, date=str(latest_year)).get(latest_year)
            row[name] = value
            row[f"{name}_display"] = pounds(value, pence) if value else None
        for name in ("england", "south_west"):
            if row["cheltenham"] and row[name]:
                row[f"vs_{name}"] = percent_change(row["cheltenham"], row[name])
                row[f"vs_{name}_display"] = signed(row[f"vs_{name}"])
        latest_rows.append(row)

    growth = {
        "first_year": first_year,
        "cheltenham": percent_change(resident[latest_year], resident[first_year]),
        "england": percent_change(comparators["england"][latest_year], comparators["england"][first_year]),
    }
    gap = None
    if latest_year in male and latest_year in female:
        gap = round((male[latest_year] - female[latest_year]) / male[latest_year] * 100, 1)

    output = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Office for National Statistics — Annual Survey of Hours and Earnings, via Nomis",
        "source_url": "https://www.nomisweb.co.uk/",
        "licence": "Open Government Licence v3.0",
        "geography_code": CHELTENHAM,
        "first_year": first_year,
        "latest_year": latest_year,
        "latest": {
            "year": latest_year,
            "resident": resident[latest_year],
            "resident_display": pounds(resident[latest_year]),
            "workplace": workplace.get(latest_year),
            "workplace_display": pounds(workplace[latest_year]) if workplace.get(latest_year) else None,
            "male_display": pounds(male[latest_year]) if latest_year in male else None,
            "female_display": pounds(female[latest_year]) if latest_year in female else None,
            "gender_gap": gap,
            "rows": latest_rows,
        },
        "growth": {**growth, "cheltenham_display": signed(growth["cheltenham"]), "england_display": signed(growth["england"])},
        "series": series,
    }

    out = helper.repo_root() / "_data" / "cheltenham-earnings.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {len(series)} years ({first_year}-{latest_year}) to {out} — latest resident median {output['latest']['resident_display']}")


if __name__ == "__main__":
    main()
