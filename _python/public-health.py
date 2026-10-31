#!/usr/bin/env python3
"""Fetch public health indicators for Cheltenham from the Office for Health
Improvement and Disparities (OHID) Fingertips API — public and keyless — and
write _data/public-health.json:

- The latest Cheltenham value of each indicator listed in
  _data/public-health-indicators.json, next to England's value for the same
  sex, age and period, with Fingertips' own comparison (Better, Similar, Worse)
  and recent trend
- Life expectancy at birth for men and women each year, against England
- Year 6 children overweight or obese in each Cheltenham ward

Fingertips returns every district (or ward) in England in one CSV, so the rows
are streamed and only Cheltenham, its wards and England are kept. England's
row must be matched on sex and age as well as period: England is published for
every age band, and the first England row is often a single band (18 to 24),
not all adults.

Fingertips updates monthly; most indicators change once a year. Refreshed
monthly.

Source: https://fingertips.phe.org.uk/api
"""

import csv
import datetime
import json

import config
import helper

API = "https://fingertips.phe.org.uk/api/all_data/csv/by_indicator_id"
CHELTENHAM = config.AREA_CODE
ENGLAND = "E92000001"
DISTRICT_TYPE = 501  # Lower tier local authorities (post 4/23)
WARD_TYPE = 8        # Electoral Best Fit Wards (2024)
ENGLAND_TYPE = 15

SEX_LABELS = {"Male": " (men)", "Female": " (women)"}

COMPARED = {
    "Better": "Better than England",
    "Similar": "Similar to England",
    "Worse": "Worse than England",
    "Higher": "Higher than England",
    "Lower": "Lower than England",
}


def stream_rows(indicator_ids, child_type, parent_type):
    """Yield each CSV row Fingertips returns for these indicators."""
    params = {"indicator_ids": ",".join(str(i) for i in indicator_ids),
              "child_area_type_id": child_type, "parent_area_type_id": parent_type}
    response = helper.get(API, params=params, timeout=300, stream=True)
    response.encoding = "utf-8-sig"
    yield from csv.DictReader(response.iter_lines(decode_unicode=True))


def keep(rows, codes):
    """Rows for these areas only, without the deprivation/ethnicity breakdowns."""
    for r in rows:
        if r["Area Code"] in codes and not r["Category Type"]:
            yield r


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def display(value, unit):
    if unit == "per 100,000":
        return f"{value:.1f} per 100,000" if value < 100 else f"{int(round(value)):,} per 100,000"
    if unit == "%":
        return f"{value:.1f}%"
    return f"{value:.1f} {unit}"


def period_display(period):
    return period.replace(" - ", "–")


def compared_display(compared):
    return COMPARED.get(compared, "Not compared")


def latest_entry(rows, indicator, sex):
    """The latest Cheltenham row for one indicator and sex, with England's row
    for the same sex, age and period. None when Cheltenham has no value."""
    wanted = str(indicator["id"])
    rng = indicator.get("range")
    candidates = [r for r in rows if r["Indicator ID"] == wanted and r["Sex"] == sex
                  and (not rng or r["Time period range"] == rng)]
    local = [r for r in candidates if r["Area Code"] == CHELTENHAM and number(r["Value"]) is not None]
    if not local:
        return None
    # Several ages can exist (smoking by age band); the widest is the one with most people.
    latest = max(local, key=lambda r: (r["Time period Sortable"], -len(r["Age"])))
    england = next((r for r in candidates if r["Area Code"] == ENGLAND and r["Age"] == latest["Age"]
                    and r["Time period"] == latest["Time period"] and number(r["Value"]) is not None), None)
    unit = indicator["unit"]
    value = round(number(latest["Value"]), 1)
    entry = {
        "id": indicator["id"],
        "label": indicator["label"],
        "label_display": indicator["label"] + SEX_LABELS.get(sex, ""),
        "sex": sex,
        "age": latest["Age"],
        "period": latest["Time period"],
        "period_display": period_display(latest["Time period"]),
        "unit": unit,
        "value": value,
        "value_display": display(value, unit),
        "england": None,
        "england_display": None,
        "compared": latest["Compared to England value or percentiles"],
        "compared_display": compared_display(latest["Compared to England value or percentiles"]),
        "trend": latest["Recent Trend"] if latest["Recent Trend"] not in ("", "Cannot be calculated") else None,
    }
    if england:
        entry["england"] = round(number(england["Value"]), 1)
        entry["england_display"] = display(entry["england"], unit)
    return entry


def life_expectancy_series(rows, indicator_id):
    """Single-year life expectancy at birth for men and women, Cheltenham and England."""
    keys = {(CHELTENHAM, "Male"): "male", (CHELTENHAM, "Female"): "female",
            (ENGLAND, "Male"): "england_male", (ENGLAND, "Female"): "england_female"}
    years = {}
    for r in rows:
        key = keys.get((r["Area Code"], r["Sex"]))
        if r["Indicator ID"] != str(indicator_id) or r["Time period range"] != "1y" or not key:
            continue
        value = number(r["Value"])
        if value is None:
            continue
        years.setdefault(r["Time period"], {"year": r["Time period"]})[key] = round(value, 1)
    return [years[y] for y in sorted(years)]


def ward_table(rows, indicator_id, slugs):
    """The latest value for each Cheltenham ward, alphabetically, plus the
    Cheltenham and England figures for the same period."""
    mine = [r for r in rows if r["Indicator ID"] == str(indicator_id)]
    wards = [r for r in mine if r["Parent Code"] == CHELTENHAM and number(r["Value"]) is not None]
    if not wards:
        return None
    period = max(wards, key=lambda r: r["Time period Sortable"])["Time period"]

    def area(code):
        found = next((r for r in mine if r["Area Code"] == code and r["Time period"] == period), None)
        return round(number(found["Value"]), 1) if found and number(found["Value"]) is not None else None

    table = {"period": period, "period_display": period_display(period), "rows": []}
    for name, code in (("cheltenham", CHELTENHAM), ("england", ENGLAND)):
        table[name] = area(code)
        table[f"{name}_display"] = display(table[name], "%") if table[name] is not None else None
    for r in sorted((r for r in wards if r["Time period"] == period), key=lambda r: r["Area Name"]):
        value = round(number(r["Value"]), 1)
        count = number(r["Count"])
        compared = r["Compared to England value or percentiles"]
        table["rows"].append({
            "code": r["Area Code"],
            "name": r["Area Name"],
            "slug": slugs.get(r["Area Code"]),
            "value": value,
            "value_display": display(value, "%"),
            "count": int(round(count)) if count is not None else None,
            "compared": compared,
            "compared_display": compared_display(compared),
        })
    return table


def ward_slugs():
    """{ward code: page slug} from the ward files behind /cheltenham-wards/*."""
    slugs = {}
    for path in (helper.repo_root() / "_data" / "wards").glob("*.json"):
        data = json.loads(path.read_text())
        if isinstance(data, dict) and data.get("code"):
            slugs[data["code"]] = path.stem
    return slugs


def build(curated, district_rows, ward_rows, slugs):
    groups = []
    for group in curated["groups"]:
        entries = []
        for indicator in group["indicators"]:
            for sex in indicator.get("sexes", ["Persons"]):
                entry = latest_entry(district_rows, indicator, sex)
                if entry:
                    entries.append(entry)
                else:
                    print(f"No Cheltenham value for {indicator['id']} {indicator['label']} ({sex})")
        if entries:
            groups.append({"name": group["name"], "indicators": entries})

    entries_all = [e for g in groups for e in g["indicators"]]
    life = life_expectancy_series(district_rows, curated["life_expectancy_chart"])
    wards = ward_table(ward_rows, curated["ward_indicator"]["id"], slugs)
    if wards:
        wards["label"] = curated["ward_indicator"]["label"]
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Office for Health Improvement and Disparities — Public Health Profiles (Fingertips)",
        "source_url": "https://fingertips.phe.org.uk/",
        "licence": "Open Government Licence v3.0",
        "geography_code": CHELTENHAM,
        "indicator_count": len(entries_all),
        "better_count": sum(e["compared"] == "Better" for e in entries_all),
        "worse_count": sum(e["compared"] == "Worse" for e in entries_all),
        "life_expectancy": {"latest": life[-1] if life else None, "first_year": life[0]["year"] if life else None,
                            "series": life},
        "groups": groups,
        "wards": wards,
    }


def main():
    root = helper.repo_root()
    curated = json.loads((root / "_data" / "public-health-indicators.json").read_text())
    ids = [i["id"] for g in curated["groups"] for i in g["indicators"]]
    district_rows = list(keep(stream_rows(ids, DISTRICT_TYPE, ENGLAND_TYPE), {CHELTENHAM, ENGLAND}))
    if not any(r["Area Code"] == CHELTENHAM for r in district_rows):
        raise SystemExit("Fingertips returned no Cheltenham rows")

    slugs = ward_slugs()
    ward_rows = list(keep(stream_rows([curated["ward_indicator"]["id"]], WARD_TYPE, DISTRICT_TYPE),
                          {CHELTENHAM, ENGLAND, *slugs}))
    output = build(curated, district_rows, ward_rows, slugs)

    out = root / "_data" / "public-health.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {output['indicator_count']} indicators and "
          f"{len(output['wards']['rows']) if output['wards'] else 0} wards to {out}")


if __name__ == "__main__":
    main()
