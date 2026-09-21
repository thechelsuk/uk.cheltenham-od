#!/usr/bin/env python3
"""Summarise road collisions in Cheltenham from the Department for Transport's road
safety data (STATS19), write _data/road-collisions.json.

Run manually, once a year — not part of any scheduled workflow. The DfT publishes
police-reported injury collisions each year, and the monthly data refresh reminder asks
you to check for a new release.

  1. Download the three "last 5 years" CSV files from
     https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-safety-data
     into the gitignored _data-sources/ folder:
       https://data.dft.gov.uk/road-accidents-safety-data/dft-road-casualty-statistics-collision-last-5-years.csv
       https://data.dft.gov.uk/road-accidents-safety-data/dft-road-casualty-statistics-casualty-last-5-years.csv
       https://data.dft.gov.uk/road-accidents-safety-data/dft-road-casualty-statistics-vehicle-last-5-years.csv
  2. If the file names have changed, update the three constants below.
  3. python _python/local/process-road-collisions.py

Only collisions in Cheltenham (ONS district E07000078) are kept. Location is the
collision's coordinates as published; no age, sex or other personal detail is used.
The page maps the fatal and serious collisions; every severity is counted in the totals.
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))          # _python/local/
SOURCE_DIR = os.path.join(HERE, "..", "..", "_data-sources")
OUT = os.path.join(HERE, "..", "..", "_data", "road-collisions.json")

# Update these three when a newer download has a different name.
COLLISION_FILE = "dft-road-casualty-statistics-collision-last-5-years.csv"
CASUALTY_FILE = "dft-road-casualty-statistics-casualty-last-5-years.csv"
VEHICLE_FILE = "dft-road-casualty-statistics-vehicle-last-5-years.csv"

DISTRICT = "E07000078"      # Cheltenham
SOURCE_URL = "https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-safety-data"

SEVERITY = {"1": "Fatal", "2": "Serious", "3": "Slight"}
ROAD_CLASS = {"1": "Motorway", "2": "A(M)", "3": "A", "4": "B", "5": "C", "6": "Unclassified"}
DAYS = {"1": "Sunday", "2": "Monday", "3": "Tuesday", "4": "Wednesday", "5": "Thursday", "6": "Friday", "7": "Saturday"}
DAY_ORDER = ["2", "3", "4", "5", "6", "7", "1"]
DARK = {"4", "5", "6", "7"}

# STATS19 casualty_type and vehicle_type codes grouped into road users the page can explain.
CASUALTY_GROUPS = {
    "0": "Pedestrian", "1": "Cyclist",
    "2": "Motorcyclist", "3": "Motorcyclist", "4": "Motorcyclist", "5": "Motorcyclist", "23": "Motorcyclist",
    "97": "Motorcyclist",
    "8": "Car or taxi occupant", "9": "Car or taxi occupant",
    "10": "Bus, coach or minibus occupant", "11": "Bus, coach or minibus occupant",
    "19": "Van or goods vehicle occupant", "20": "Van or goods vehicle occupant",
    "21": "Van or goods vehicle occupant", "98": "Van or goods vehicle occupant",
}
VEHICLE_GROUPS = {
    "1": "Pedal cycle",
    "2": "Motorcycle", "3": "Motorcycle", "4": "Motorcycle", "5": "Motorcycle", "23": "Motorcycle", "97": "Motorcycle",
    "8": "Car or taxi", "9": "Car or taxi",
    "10": "Bus, coach or minibus", "11": "Bus, coach or minibus",
    "19": "Van or goods vehicle", "20": "Van or goods vehicle", "21": "Van or goods vehicle", "98": "Van or goods vehicle",
}
OTHER = "Other or unknown"
USER_ORDER = ["Pedestrian", "Cyclist", "Motorcyclist", "Car or taxi occupant", "Bus, coach or minibus occupant",
              "Van or goods vehicle occupant", OTHER]
VEHICLE_ORDER = ["Car or taxi", "Pedal cycle", "Van or goods vehicle", "Motorcycle", "Bus, coach or minibus", OTHER]


def read(name):
    path = os.path.join(SOURCE_DIR, name)
    if not os.path.exists(path):
        sys.exit(f"{os.path.normpath(path)} not found: see the steps at the top of this script.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def number(n):
    return f"{n:,}"


def share(part, whole):
    return round(part * 100 / whole) if whole else 0


def road_label(row):
    cls = ROAD_CLASS.get(row["first_road_class"], "")
    if cls in ("A", "B", "C", "A(M)") and row["first_road_number"] not in ("", "0", "-1"):
        return f"{cls}{row['first_road_number']}"
    return "Unclassified road" if cls == "Unclassified" else (f"{cls} road" if cls else "Unknown")


def user_group(code):
    return CASUALTY_GROUPS.get(code, OTHER)


def vehicle_group(code):
    return VEHICLE_GROUPS.get(code, OTHER)


def sev_counts(rows):
    c = Counter(r["collision_severity"] for r in rows)
    return {"fatal": c["1"], "serious": c["2"], "slight": c["3"], "total": sum(c.values())}


def main():
    collisions = {r["collision_index"]: r for r in read(COLLISION_FILE) if r["local_authority_ons_district"] == DISTRICT}
    if not collisions:
        sys.exit(f"No collisions found for {DISTRICT}: check the file and the DISTRICT constant.")
    casualties, vehicles = defaultdict(list), defaultdict(list)
    for r in read(CASUALTY_FILE):
        if r["collision_index"] in collisions:
            casualties[r["collision_index"]].append(r)
    escooter = 0
    for r in read(VEHICLE_FILE):
        if r["collision_index"] in collisions:
            vehicles[r["collision_index"]].append(r)
            if r.get("escooter_flag") == "1":
                escooter += 1
    rows = list(collisions.values())
    years = sorted({int(r["collision_year"]) for r in rows})

    # Totals and by-year counts. "Killed or seriously injured" (KSI) is fatal plus serious.
    total = sev_counts(rows)
    all_casualties = [c for cs in casualties.values() for c in cs]
    cas_total = Counter(c["casualty_severity"] for c in all_casualties)
    by_year = []
    for y in years:
        yr = [r for r in rows if int(r["collision_year"]) == y]
        ids = {r["collision_index"] for r in yr}
        cy = Counter(c["casualty_severity"] for i in ids for c in casualties[i])
        s = sev_counts(yr)
        by_year.append({"year": y, "collisions": s["total"], "fatal": s["fatal"], "serious": s["serious"],
                        "slight": s["slight"], "casualties": sum(cy.values()),
                        "casualties_fatal": cy["1"], "casualties_serious": cy["2"], "casualties_slight": cy["3"]})

    # Casualties by road user, and vehicles involved.
    users = defaultdict(Counter)
    for c in all_casualties:
        users[user_group(c["casualty_type"])][c["casualty_severity"]] += 1
    by_user = []
    for g in USER_ORDER:
        c = users.get(g)
        if not c:
            continue
        n = sum(c.values())
        by_user.append({"user": g, "fatal": c["1"], "serious": c["2"], "slight": c["3"], "total": n,
                        "share": share(n, len(all_casualties))})
    veh_counts, veh_collisions = Counter(), defaultdict(set)
    all_vehicles = 0
    for i, vs in vehicles.items():
        for v in vs:
            g = vehicle_group(v["vehicle_type"])
            veh_counts[g] += 1
            veh_collisions[g].add(i)
            all_vehicles += 1
    by_vehicle = [{"vehicle": g, "vehicles": veh_counts[g], "collisions": len(veh_collisions[g]),
                   "share_of_collisions": share(len(veh_collisions[g]), len(rows))}
                  for g in VEHICLE_ORDER if veh_counts[g]]

    # When: hour of day and day of week.
    hours = Counter(int(r["time"][:2]) for r in rows if r["time"][:2].isdigit())
    ksi_hours = Counter(int(r["time"][:2]) for r in rows if r["time"][:2].isdigit() and r["collision_severity"] in "12")
    by_hour = [{"hour": h, "label": f"{h:02d}:00", "collisions": hours[h], "ksi": ksi_hours[h]} for h in range(24)]
    days = Counter(r["day_of_week"] for r in rows)
    ksi_days = Counter(r["day_of_week"] for r in rows if r["collision_severity"] in "12")
    by_day = [{"day": DAYS[d], "collisions": days[d], "ksi": ksi_days[d]} for d in DAY_ORDER]

    # Where and in what conditions.
    by_class = []
    for code in ("3", "4", "5", "6"):
        sub = [r for r in rows if r["first_road_class"] == code]
        if sub:
            by_class.append({"road": {"3": "A roads", "4": "B roads", "5": "C roads", "6": "Unclassified roads"}[code],
                             **sev_counts(sub), "share": share(len(sub), len(rows))})
    by_speed = []
    for limit in sorted({r["speed_limit"] for r in rows if r["speed_limit"].isdigit()}, key=int):
        sub = [r for r in rows if r["speed_limit"] == limit]
        by_speed.append({"speed_limit": int(limit), **sev_counts(sub), "share": share(len(sub), len(rows))})
    dark = [r for r in rows if r["light_conditions"] in DARK]
    light = {"daylight": len(rows) - len(dark), "dark": len(dark), "dark_share": share(len(dark), len(rows))}
    numbered = defaultdict(list)
    for r in rows:
        label = road_label(r)
        if label[0] in "ABC" and label[1:].isdigit() or label.startswith("A(M)"):
            numbered[label].append(r)
    top_roads = sorted(({"road": k, **sev_counts(v)} for k, v in numbered.items()),
                       key=lambda x: (-x["total"], x["road"]))[:10]

    # The fatal and serious collisions, one record each, for the map and the table.
    serious = []
    for r in sorted(rows, key=lambda r: (datetime.strptime(r["date"], "%d/%m/%Y"), r["time"]), reverse=True):
        if r["collision_severity"] not in "12" or r["latitude"] in ("", "NULL"):
            continue
        cs = casualties[r["collision_index"]]
        cas_summary = ", ".join(f"{n} {g.lower()} ({s.lower()})" for (g, s), n in sorted(
            Counter((user_group(c["casualty_type"]), SEVERITY[c["casualty_severity"]]) for c in cs).items(),
            key=lambda x: (USER_ORDER.index(x[0][0]), x[0][1])))
        veh_summary = ", ".join(f"{n} {g.lower()}" if n > 1 else g.lower() for g, n in sorted(
            Counter(vehicle_group(v["vehicle_type"]) for v in vehicles[r["collision_index"]]).items(),
            key=lambda x: VEHICLE_ORDER.index(x[0])))
        serious.append({
            "id": r["collision_index"],
            "date": datetime.strptime(r["date"], "%d/%m/%Y").strftime("%Y-%m-%d"),
            "time": r["time"],
            "severity": SEVERITY[r["collision_severity"]],
            "road": road_label(r),
            "speed_limit": int(r["speed_limit"]) if r["speed_limit"].isdigit() else None,
            "casualties": len(cs),
            "casualties_summary": cas_summary.capitalize() if cas_summary else "Not recorded",
            "vehicles": veh_summary.capitalize() if veh_summary else "Not recorded",
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
        })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Department for Transport road safety data (STATS19)",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "district": DISTRICT,
        "first_year": years[0],
        "last_year": years[-1],
        "totals": {
            "collisions": total["total"], "collisions_display": number(total["total"]),
            "fatal": total["fatal"], "serious": total["serious"], "slight": total["slight"],
            "ksi": total["fatal"] + total["serious"],
            "casualties": len(all_casualties), "casualties_display": number(len(all_casualties)),
            "casualties_fatal": cas_total["1"], "casualties_serious": cas_total["2"], "casualties_slight": cas_total["3"],
            "vehicles": all_vehicles, "vehicles_display": number(all_vehicles),
            "escooters": escooter,
        },
        "by_year": by_year,
        "by_user": by_user,
        "by_vehicle": by_vehicle,
        "by_hour": by_hour,
        "by_day": by_day,
        "by_road_class": by_class,
        "by_speed_limit": by_speed,
        "light": light,
        "top_roads": top_roads,
        "serious_collisions": serious,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {total['total']} collisions ({years[0]}-{years[-1]}), {len(serious)} fatal or serious mapped, "
          f"to {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
