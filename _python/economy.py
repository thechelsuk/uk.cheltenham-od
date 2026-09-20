#!/usr/bin/env python3
"""Fetch the size and shape of Cheltenham's economy from Nomis — the ONS's
public, keyless labour market service — and write _data/cheltenham-economy.json:

- Jobs: employee jobs by industry for the latest year, with each industry's
  share of the total and how that compares with England (Business Register
  and Employment Survey), plus total employee jobs each year since 2015
- Businesses: the number of VAT and/or PAYE registered businesses each year
  since 2010, and the latest year by size band (UK Business Counts)
- Claimants: the monthly Claimant Count since January 2015, with the rate as
  a share of residents aged 16-64 compared with England

The three sources publish on different schedules (monthly, annually), so the
script is refreshed monthly with the other Nomis data.

Source: https://www.nomisweb.co.uk/api/v01/
"""

import csv
import datetime
import io
import json

import helper

BASE_URL = "https://www.nomisweb.co.uk/api/v01/dataset"
CHELTENHAM, ENGLAND = "E07000078", "E92000001"

BRES = "NM_189_1"              # Business Register and Employment Survey: open access
BRES_START_YEAR = 2015         # start of the current BRES series
ALL_INDUSTRIES = 37748736
SIC_SECTIONS = "150994945...150994965"  # SIC 2007 sections A to U
EMPLOYEES = 1

BUSINESS_COUNTS = "NM_142_1"   # UK Business Counts: enterprises by industry and size band
BUSINESS_START_YEAR = 2010
SIZE_BANDS = [(10, "Micro (0 to 9 employees)"), (20, "Small (10 to 49)"), (30, "Medium-sized (50 to 249)"), (40, "Large (250 or more)")]

CLAIMANTS = "NM_162_1"         # Claimant Count by sex and age
CLAIMANT_START = "2015-01"
COUNT, RATE = 1, 2             # claimant count; claimants as a proportion of residents aged 16-64


def fetch(dataset, select, **params):
    resp = helper.request_with_retry(
        "GET", f"{BASE_URL}/{dataset}.data.csv",
        params={**params, "measures": 20100, "select": select},
        timeout=30,
    )
    return list(csv.DictReader(io.StringIO(resp.text)))


def number(value):
    return float(value) if value not in ("", None) else None


def percent(value, digits=1):
    return round(value, digits)


def fetch_jobs():
    latest = fetch(BRES, "date_name,obs_value", geography=CHELTENHAM, date="latest",
                   industry=ALL_INDUSTRIES, employment_status=EMPLOYEES, measure=1)
    year = int(latest[0]["DATE_NAME"])
    total = int(float(latest[0]["OBS_VALUE"]))

    def sections(geography):
        rows = fetch(BRES, "industry_name,obs_value", geography=geography, date=str(year),
                     industry=SIC_SECTIONS, employment_status=EMPLOYEES, measure=1)
        return {r["INDUSTRY_NAME"]: number(r["OBS_VALUE"]) or 0 for r in rows}

    local, national = sections(CHELTENHAM), sections(ENGLAND)
    england_total = sum(national.values())
    industries = []
    for name, jobs in local.items():
        if not jobs:
            continue  # rounded to zero in Cheltenham
        share = jobs / total * 100
        england_share = national.get(name, 0) / england_total * 100 if england_total else None
        quotient = round(share / england_share, 2) if england_share else None
        industries.append({
            "name": name.split(" : ", 1)[-1],
            "code": name.split(" : ", 1)[0],
            "jobs": int(jobs),
            "jobs_display": f"{int(jobs):,}",
            "share": percent(share),
            "share_display": f"{share:.1f}%",
            "england_share": percent(england_share) if england_share is not None else None,
            "england_share_display": f"{england_share:.1f}%" if england_share is not None else None,
            "quotient": quotient,
            "quotient_display": f"{quotient:.2f}" if quotient is not None else None,
        })
    industries.sort(key=lambda i: i["jobs"], reverse=True)

    rows = fetch(BRES, "date_name,obs_value", geography=CHELTENHAM,
                 date=f"{BRES_START_YEAR}-{datetime.date.today().year}",
                 industry=ALL_INDUSTRIES, employment_status=EMPLOYEES, measure=1)
    series = [{"year": int(r["DATE_NAME"]), "jobs": int(float(r["OBS_VALUE"])), "jobs_display": f"{int(float(r['OBS_VALUE'])):,}"}
              for r in rows if r["OBS_VALUE"]]
    return {"year": year, "total": total, "total_display": f"{total:,}", "industries": industries, "series": series}


def fetch_businesses():
    rows = fetch(BUSINESS_COUNTS, "date_name,obs_value", geography=CHELTENHAM,
                 date=f"{BUSINESS_START_YEAR}-{datetime.date.today().year}",
                 industry=ALL_INDUSTRIES, employment_sizeband=0, legal_status=0)
    series = [{"year": int(r["DATE_NAME"]), "businesses": int(float(r["OBS_VALUE"])), "businesses_display": f"{int(float(r['OBS_VALUE'])):,}"}
              for r in rows if r["OBS_VALUE"]]
    latest = series[-1]
    by_size = []
    for code, label in SIZE_BANDS:
        value = fetch(BUSINESS_COUNTS, "obs_value", geography=CHELTENHAM, date=str(latest["year"]),
                      industry=ALL_INDUSTRIES, employment_sizeband=code, legal_status=0)[0]["OBS_VALUE"]
        count = int(float(value))
        by_size.append({"label": label, "businesses": count, "businesses_display": f"{count:,}",
                        "share_display": f"{count / latest['businesses'] * 100:.1f}%"})
    return {"year": latest["year"], "total": latest["businesses"], "total_display": latest["businesses_display"],
            "by_size": by_size, "series": series}


def fetch_claimants():
    def monthly(geography, measure):
        rows = fetch(CLAIMANTS, "date_code,date_name,obs_value", geography=geography,
                     date=f"{CLAIMANT_START}-{datetime.date.today().year}-12", gender=0, age=0, measure=measure)
        return {r["DATE_CODE"]: (r["DATE_NAME"], number(r["OBS_VALUE"])) for r in rows}

    count, rate, england_rate = monthly(CHELTENHAM, COUNT), monthly(CHELTENHAM, RATE), monthly(ENGLAND, RATE)
    series = [{"period": period, "count": int(count[period][1]), "rate": rate[period][1], "england_rate": england_rate.get(period, (None, None))[1]}
              for period in sorted(count) if count[period][1] is not None]
    latest = series[-1]
    return {
        "period": latest["period"],
        "period_name": count[latest["period"]][0],
        "count": latest["count"],
        "count_display": f"{latest['count']:,}",
        "rate": latest["rate"],
        "rate_display": f"{latest['rate']:.1f}%",
        "england_rate_display": f"{latest['england_rate']:.1f}%" if latest["england_rate"] is not None else None,
        "series": series,
    }


def main():
    jobs = fetch_jobs()
    print(f"Jobs: {jobs['total_display']} employee jobs in {jobs['year']}, {len(jobs['industries'])} industries")
    businesses = fetch_businesses()
    print(f"Businesses: {businesses['total_display']} in {businesses['year']}, {len(businesses['series'])} years")
    claimants = fetch_claimants()
    print(f"Claimants: {claimants['count_display']} in {claimants['period_name']} ({claimants['rate_display']})")

    output = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Office for National Statistics via Nomis: Business Register and Employment Survey, UK Business Counts and Claimant Count",
        "source_url": "https://www.nomisweb.co.uk/",
        "licence": "Open Government Licence v3.0",
        "geography_code": CHELTENHAM,
        "jobs": jobs,
        "businesses": businesses,
        "claimants": claimants,
    }
    out = helper.repo_root() / "_data" / "cheltenham-economy.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
