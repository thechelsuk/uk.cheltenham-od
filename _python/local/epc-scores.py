#!/usr/bin/env python3
"""Full Energy Performance Certificate details for Cheltenham's homes: the
numeric energy efficiency score behind each A to G band, the score the home
could reach, and what kind of home it is. Run locally once a month (the Data
Refresh Reminder issue lists it), not in GitHub Actions.

The domestic search (14 calls, as epc.py makes) lists every certificate, and
each home keeps its latest. Full details need one call per certificate, so
they are kept between runs in _data-sources/epc-homes.json (gitignored,
about 6 MB): the first run fetches every home's certificate (about 43,600
calls, roughly 40 minutes within the API's limit of 6,000 calls every five
minutes), and later runs fetch only homes with a newer certificate. Homes
whose certificates are no longer published drop out, as the search no
longer lists them.

Addresses and postcodes carry Ordnance Survey and Royal Mail terms, so the
stored file keeps only the UPRN (or an internal key), the small area and
ward a home falls in, and certificate fields. _data/epc-scores.json, which
the site reads, holds area totals only.

    .venv/bin/python _python/local/epc-scores.py           # fetch new certificates, rebuild totals
    .venv/bin/python _python/local/epc-scores.py --limit 50  # try a few first
"""
import argparse
import hashlib
import json
import statistics
import sys
import threading
from collections import Counter
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import epc  # noqa: E402
import helper  # noqa: E402

API = "https://api.get-energy-performance-data.communities.gov.uk/api"
STORE = helper.repo_root() / "_data-sources" / "epc-homes.json"
OUT = helper.repo_root() / "_data" / "epc-scores.json"
CALLS_PER_SECOND = 15  # the API allows 20 (6,000 every five minutes)
WORKERS = 8
SAVE_EVERY = 1000


class Throttle:
    """At most `rate` calls a second across all threads."""

    def __init__(self, rate):
        self.gap = 1 / rate
        self.next = time.monotonic()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = self.next - now
            self.next = max(now, self.next) + self.gap
        if delay > 0:
            time.sleep(delay)


def home_key(cert):
    """The home's UPRN or, without one, a hash of its address, so the stored
    file never holds an address."""
    if cert.get("uprn"):
        return f"uprn:{cert['uprn']}"
    address = " ".join(str(cert.get(f) or "") for f in ("addressLine1", "addressLine2", "postcode")).upper()
    return "address:" + hashlib.sha256(address.encode()).hexdigest()[:16]


def latest_certificates(certs):
    """{home key: search record} for each home's latest certificate with an A to G band."""
    latest = {}
    for c in certs:
        band = (c.get("currentEnergyEfficiencyBand") or "").upper()
        if len(band) != 1 or band not in epc.BANDS:
            continue
        key = home_key(c)
        if key not in latest or (c.get("registrationDate") or "") > (latest[key].get("registrationDate") or ""):
            latest[key] = c
    return latest


def number(value):
    """A numeric field that some schemas wrap as {"value": n, "currency": ...}."""
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def details(data):
    """The certificate fields kept for each home, from a /certificate response."""
    parts = data.get("sap_building_parts") or [{}]
    heating = data.get("main_heating") or [{}]
    source = data.get("sap_energy_source") or {}
    return {
        "score": number(data.get("energy_rating_current")),
        "potential_score": number(data.get("energy_rating_potential")),
        "potential_band": data.get("potential_energy_efficiency_band"),
        "schema": data.get("schema_type"),
        "assessment": data.get("assessment_type"),
        "tenure": data.get("tenure"),
        "property_type": data.get("property_type"),
        "built_form": data.get("built_form"),
        "age_band": parts[0].get("construction_age_band"),
        "floor_area": number(data.get("total_floor_area")),
        "main_heating": (heating[0] or {}).get("description"),
        "mains_gas": source.get("mains_gas"),
        "co2": number(data.get("co2_emissions_current")),
        "heating_cost": number(data.get("heating_cost_current")),
    }


def fetch_details(numbers, headers, store, homes_by_number, limit=None):
    throttle = Throttle(CALLS_PER_SECOND)
    todo = numbers[:limit] if limit else numbers

    def one(number_):
        throttle.wait()
        resp = helper.get(f"{API}/certificate", headers=headers, timeout=60,
                          params={"certificate_number": number_})
        return number_, details(resp.json().get("data") or {})

    done = 0
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = [pool.submit(one, n) for n in todo]
        for future in as_completed(futures):
            try:
                number_, fields = future.result()
            except Exception as error:  # pylint: disable=broad-except
                print(f"  skipped a certificate: {error}")
                continue
            store[homes_by_number[number_]].update(fields, fetched=True)
            done += 1
            if done % SAVE_EVERY == 0:
                save_store(store)
                print(f"  {done:,} of {len(todo):,} certificates fetched")
    return done


def load_store():
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def save_store(store):
    STORE.parent.mkdir(exist_ok=True)
    STORE.write_text(json.dumps(store, sort_keys=True, separators=(",", ":")).replace('},"', '},\n"'))


def place(homes, latest):
    """Each home's small area (LSOA) and ward codes, from its postcode's centre."""
    data = helper.repo_root() / "_data"
    lsoas = [{"code": a["code"], "rings": a["boundary"]}
             for a in json.loads((data / "small-areas.json").read_text())["lsoas"]]
    wards = [{"code": w["code"], "rings": [w["boundary"]]}
             for w in json.loads((data / "wards" / "index.json").read_text())["wards"]]
    postcodes = {(latest[k].get("postcode") or "").upper() for k in homes}
    points = epc.geocode({p for p in postcodes if p})
    for key, home in homes.items():
        point = points.get((latest[key].get("postcode") or "").upper())
        home["lsoa"] = epc.area_for(*point, lsoas) if point else None
        home["ward"] = epc.area_for(*point, wards) if point else None


def code_labels(headers):
    """{code name: {key: label}} for tenure, property type and built form,
    from the register's own code lists. Labels differ slightly between
    schema versions ("rented (social)", "rental (social)"), so the most
    common one is used."""
    labels = {}
    for code in ("tenure", "property_type", "built_form"):
        rows = helper.get(f"{API}/codes/info", headers=headers, params={"code": code}).json()["data"]
        labels[code] = {
            str(row["key"]): Counter(v["value"].strip().lower() for v in row["values"]).most_common(1)[0][0]
            for row in rows
        }
    return labels


def home_type(home, labels):
    """House types by built form ("Mid-terrace house"); flats, maisonettes,
    bungalows and park homes as they are."""
    kind = labels["property_type"].get(str(home.get("property_type")))
    if not kind:
        return None
    if kind == "house":
        form = labels["built_form"].get(str(home.get("built_form")), "")
        form = form.replace("enclosed ", "")
        return f"{form.capitalize()} house" if form and form != "not recorded" else "House (form not recorded)"
    return kind.capitalize()


def tenure(home, labels):
    value = home.get("tenure")
    label = labels["tenure"].get(str(value)) if value is not None else None
    label = label or (str(value).strip().lower() if value else None)
    if not label or label == "unknown":
        return None
    return {"owner-occupied": "Owner-occupied", "rented (social)": "Social rented", "rental (social)": "Social rented",
            "rented (private)": "Private rented", "rental (private)": "Private rented"}.get(label)


HEATING = (
    ("heat pump", "Heat pump"),
    ("community", "Community heating"),
    ("mains gas", "Mains gas"),
    ("lpg", "LPG"),
    ("oil", "Oil"),
    ("electric", "Electric"),
)


def heating(home):
    text = home.get("main_heating") or ""
    if isinstance(text, dict):  # older schemas: {"language": "1", "value": "..."}
        text = text.get("value") or ""
    text = text.lower()
    if not text:
        return None
    for needle, label in HEATING:
        if needle in text:
            return label
    return "Other"


def summarise(homes):
    """Score totals for a group of homes: how many, the median and mean
    score, the share rated C or better, how many are below C, and the share
    whose potential rating is C or better."""
    scores = [h["score"] for h in homes if h.get("score") is not None]
    potential = [h for h in homes if h.get("potential_band")]
    below_c = sum(1 for h in homes if h.get("band") in "DEFG")
    return {
        "homes": len(homes),
        "homes_display": f"{len(homes):,}",
        "median_score": round(statistics.median(scores)) if scores else None,
        "mean_score": round(statistics.mean(scores), 1) if scores else None,
        "c_plus_pct": round(100 * (len(homes) - below_c) / len(homes), 1) if homes else None,
        "below_c": below_c,
        "below_c_display": f"{below_c:,}",
        "potential_c_plus_pct": round(100 * sum(h["potential_band"] in "ABC" for h in potential) / len(potential), 1)
        if potential else None,
    }


def group(homes, label):
    """summarise() for each group, as {label: totals}, largest group first."""
    groups = {}
    for h in homes:
        name = label(h)
        if name:
            groups.setdefault(name, []).append(h)
    return [{"name": name, **summarise(rows)} for name, rows in
            sorted(groups.items(), key=lambda item: -len(item[1]))]


def by_area(homes, key):
    groups = {}
    for h in homes:
        if h.get(key):
            groups.setdefault(h[key], []).append(h)
    return {code: summarise(rows) for code, rows in sorted(groups.items())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="fetch at most this many certificates (for a trial run)")
    args = parser.parse_args()

    key = epc.load_key()
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    latest = latest_certificates(epc.fetch_certificates(key))
    print(f"{len(latest):,} homes have a current certificate")

    old = load_store()
    store = {}
    homes_by_number = {}
    for home, cert in latest.items():
        record = old.get(home, {})
        if record.get("certificate") != cert["certificateNumber"]:
            record = {"certificate": cert["certificateNumber"]}
        record.update(band=cert["currentEnergyEfficiencyBand"].upper(), date=cert.get("registrationDate"))
        store[home] = record
        homes_by_number[cert["certificateNumber"]] = home
    place(store, latest)
    save_store(store)

    todo = [r["certificate"] for r in store.values() if not r.get("fetched")]
    print(f"{len(todo):,} certificates to fetch ({len(store) - len(todo):,} kept from the last run)")
    fetched = fetch_details(todo, headers, store, homes_by_number, args.limit)
    save_store(store)

    homes = list(store.values())
    with_details = [h for h in homes if h.get("fetched")]
    labels = code_labels(headers)
    helper.write_json(OUT, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": epc.SOURCE,
        "source_url": epc.SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "homes_with_details": len(with_details),
        "borough": summarise(with_details),
        "ward": by_area(with_details, "ward"),
        "lsoa": by_area(with_details, "lsoa"),
        "by_home_type": group(with_details, lambda h: home_type(h, labels)),
        "by_tenure": group(with_details, lambda h: tenure(h, labels)),
        "tenure_unknown_display": f"{sum(1 for h in with_details if not tenure(h, labels)):,}",
        "by_heating": group(with_details, heating),
    })
    print(f"Fetched {fetched:,} certificates; {len(with_details):,} of {len(homes):,} homes now have details")


if __name__ == "__main__":
    main()
