#!/usr/bin/env python3
"""Cheltenham in numbers: one headline figure from each dataset the site
already holds, with its source and the page it comes from, written to
_data/cheltenham-numbers.json for the /cheltenham-in-numbers page.

Nothing is fetched: this only reads other _data files, so it runs after them in
the hourly workflow and the figures stay in step with their pages.
"""
import json
from datetime import datetime, timezone

import helper

DATA = helper.repo_root() / "_data"


def load(name):
    return json.loads((DATA / name).read_text())


def number(n):
    return f"{n:,}"


def pct(part, whole):
    return round(100 * part / whole) if whole else 0


def figure(label, value, detail, link, source):
    return {"label": label, "value_display": value, "detail": detail, "link": link, "source": source}


def build():
    stats = load("cheltenham-stats.json")
    wards = load("wards/index.json")["wards"]
    ward_files = [load(f"wards/{w['slug']}.json") for w in wards]
    politics = load("ward-politics.json")
    mp = load("politics.json")["current_mp"]
    homes = load("house-summary.json")["current"]
    rent = load("rents.json")["latest"]
    schools = load("schools.json")
    dentists = load("dentists.json")["practices"]
    cqc = load("cqc.json")["summary"]
    childcare = load("childcare.json")["summary"]
    collisions = load("road-collisions.json")
    broadband = load("broadband-summary.json")
    food = load("food-standards.json")
    listed = load("listed-buildings.json")
    charities = load("charities.json")["summary"]
    ev = load("ev-charging.json")["summary"]
    car_parks = load("car-parks.json")["car_parks"]
    fuel = load("fuel-prices.json")
    fires = load("wildfire-incidents.json")

    crimes = sum(w["crime_total"] for w in wards)
    councillors = sum(len(w["councillors"]) for w in politics["wards"].values())
    zone3 = sum(w["flood"]["zone3"] for w in ward_files)
    postcodes = sum(w["flood"]["postcodes"] for w in ward_files)
    gigabit = next(t["count"] for t in broadband["tier_totals"] if t["tier"] == 4)
    rated = [v for v in food if v["rating"] in ("0", "1", "2", "3", "4", "5")]
    five_star = sum(v["rating"] == "5" for v in rated)
    unleaded = next(h for h in fuel["headline"] if h["label"] == "Unleaded")
    grades = listed["grade_counts"]
    located_years = [y for y in fires["by_year"] if y.get("located")]

    groups = [
        ("People and Place", [
            figure("People living in Cheltenham", stats["population_latest"]["population_formatted"],
                   f"{stats['population_latest']['year']} estimate, up {stats['growth_pct']}% since "
                   f"{stats['population_earliest']['year']}", "/about-cheltenham", "Office for National Statistics"),
            figure("Electoral wards", number(len(wards)), f"with {councillors} borough councillors",
                   "/cheltenham-wards", "Cheltenham Borough Council"),
            figure("Member of Parliament", mp["name"], f"{mp['party']}, since {mp['since'][:4]}",
                   "/cheltenham-politics", "UK Parliament"),
        ]),
        ("Homes", [
            figure("Median house price", homes["median_display"], f"across {homes['count_display']} sales in the latest 12 months",
                   "/cheltenham-house-prices", "HM Land Registry"),
            figure("Average monthly rent", rent["price_display"],
                   f"{rent['month_name']} {rent['year']}, {rent['annual_change_display']} on a year earlier",
                   "/cheltenham-rent-prices", "Office for National Statistics"),
            figure("Postcodes with gigabit broadband", f"{pct(gigabit, broadband['unit_total'])}%",
                   f"{number(gigabit)} of {number(broadband['unit_total'])} postcodes",
                   "/cheltenham-broadband-internet-speeds", "Ofcom"),
        ]),
        ("Health, Care and Schools", [
            figure("Schools", number(len(schools)), "in the GL50 to GL54 postcodes", "/cheltenham-schools",
                   "Department for Education"),
            figure("Nurseries and childcare providers", number(childcare["providers"]),
                   f"with {childcare['places_display']} places", "/cheltenham-nurseries-childcare", "Ofsted"),
            figure("Dental practices", number(len(dentists)), "in the GL50 to GL54 postcodes", "/cheltenham-dentists", "NHS"),
            figure("Care homes", number(cqc["care_homes"]),
                   f"{cqc['care_homes_good_or_better']} rated good or outstanding", "/cheltenham-care-homes",
                   "Care Quality Commission"),
        ]),
        ("Safety and Environment", [
            figure("Crimes reported", number(crimes), "in the latest 12 months", "/cheltenham-crime-data", "Police.uk"),
            figure("Road collisions with injuries", collisions["totals"]["collisions_display"],
                   f"{collisions['first_year']} to {collisions['last_year']}, "
                   f"{collisions['totals']['ksi']} fatal or serious", "/cheltenham-road-collisions",
                   "Department for Transport"),
            figure("Postcodes in Flood Zone 3", f"{pct(zone3, postcodes)}%", f"{number(zone3)} of {number(postcodes)} postcodes",
                   "/cheltenham-flood-zones", "Environment Agency"),
            figure("Grass and woodland fires", number(sum(y["total"] for y in located_years)),
                   f"around Cheltenham, {located_years[0]['year']} to {located_years[-1]['year']}",
                   "/cheltenham-wildfire-risk/history", "Fire statistics, MHCLG"),
        ]),
        ("Getting Around", [
            figure("Cheapest unleaded today", f"{unleaded['price']}p", "a litre, within 20 miles of Cheltenham",
                   "/cheltenham-fuel-prices", "GOV.UK fuel price scheme"),
            figure("EV charging locations", number(ev["total_locations"]), f"with {ev['total_connectors']} connectors, within 6 km of the town centre",
                   "/cheltenham-ev-charging", "Open Charge Map"),
            figure("Car parks", number(len(car_parks)), "within 6 km of the town centre", "/cheltenham-car-parks",
                   "OpenStreetMap"),
        ]),
        ("Community and Heritage", [
            figure("Registered charities", number(charities["count"]), f"with a combined income of {charities['total_income_display']} a year",
                   "/cheltenham-charities", "Charity Commission"),
            figure("Food venues with a five-star hygiene rating", f"{pct(five_star, len(rated))}%",
                   f"{number(five_star)} of {number(len(rated))} rated venues", "/cheltenham-food-standards",
                   "Food Standards Agency"),
            figure("Listed buildings", number(sum(grades.values())),
                   f"{grades.get('I', 0)} Grade I and {grades.get('II*', 0)} Grade II*", "/cheltenham-listed-buildings",
                   "Historic England"),
        ]),
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": [{"name": name, "figures": figures} for name, figures in groups],
    }


def main():
    payload = build()
    helper.write_json(DATA / "cheltenham-numbers.json", payload)
    print(f"Wrote {sum(len(g['figures']) for g in payload['groups'])} figures")


if __name__ == "__main__":
    main()
