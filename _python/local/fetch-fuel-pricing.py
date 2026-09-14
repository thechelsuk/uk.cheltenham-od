import html
import pathlib
import json
import os
import math
import datetime
import time
import sys
import requests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import helper

# Load .env file for local development if present
_env_file = helper.repo_root() / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# -- Configuration ------------------------------------------------------------

BASE_URL         = "https://www.fuel-finder.service.gov.uk"
AUTH_PATH        = "/api/v1/oauth/generate_access_token"
PFS_PATH         = "/api/v1/pfs"
PRICES_PATH      = "/api/v1/pfs/fuel-prices"

CHELTENHAM_LAT  = 51.899
CHELTENHAM_LON  = -2.078
RADIUS_MILES    = 20
EARTH_RADIUS_MI = 3958.8
BATCH_DELAY_SECS     = 1.5   # pause between paginated requests to avoid hammering the API
PRICE_LOOKBACK_DAYS  = 25    # how far back the daily price fetch looks
STALE_DAYS           = 10    # prices older than this are flagged as stale on the page
AVG_TANK_LITRES      = 55    # approx size of an average UK car fuel tank, for "full tank" savings

# Human-readable names for API fuel type codes
FUEL_LABELS = {
    "E5":           "Prem Unleaded",
    "E10":          "Unleaded",
    "B7_STANDARD":  "Diesel",
    "B7_PREMIUM":   "Prem Diesel",
    "SDV5":         "Super Diesel",
}


def fuel_label(code):
    return FUEL_LABELS.get(code, code)


# Brand tokens / road refs that stay fully uppercase after title-casing.
# Add to this set if a name comes out looking wrong.
ACRONYMS = {"MFG", "ASDA", "EG", "BP", "PFS", "SF", "PJ", "TGC", "PA", "UK"}


def clean_name(raw):
    return helper.clean_name(raw, ACRONYMS)


# -- Auth helpers -------------------------------------------------------------

def authenticate(client_id, client_secret):
    """Obtain a fresh access token, retrying on transient failures."""
    resp = helper.request_with_retry(
        "POST", BASE_URL + AUTH_PATH, max_attempts=4, retry_statuses=range(400, 600),
        json={"client_id": client_id, "client_secret": client_secret}, timeout=20,
    )
    data = resp.json()
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    return payload["access_token"]


# -- Helpers ------------------------------------------------------------------

def haversine_miles(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_all_pages(path, token, extra_params=None, label=""):
    """Fetch all paginated results, sleeping between batches to stay polite."""
    results = []
    batch   = 1
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        params = {"batch-number": batch}
        if extra_params:
            params.update(extra_params)
        for attempt in range(4):
            try:
                resp = requests.get(
                    BASE_URL + path,
                    headers=headers,
                    params=params,
                    timeout=(10, 90),
                )
                if resp.status_code == 504:
                    wait = BATCH_DELAY_SECS * (attempt + 2)
                    print(f"  {label}batch {batch}: 504 timeout (attempt {attempt + 1}/4), waiting {wait}s...")
                    time.sleep(wait)
                    if attempt == 3:
                        resp.raise_for_status()
                    continue
                break
            except requests.exceptions.ReadTimeout:
                wait = BATCH_DELAY_SECS * (attempt + 2)
                print(f"  {label}batch {batch}: read timeout (attempt {attempt + 1}/4), waiting {wait}s...")
                time.sleep(wait)
                if attempt == 3:
                    raise
        # 404 means no more pages; anything else is a real error
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        results.extend(page)
        print(f"  {label}batch {batch}: {len(page)} records")
        if len(page) < 500:
            break
        batch += 1
        time.sleep(BATCH_DELAY_SECS)
    return results


def load_station_cache(cache_path):
    """Load local station info. Returns only non-None entries (real local stations)."""
    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        return {k: v for k, v in raw.items() if v is not None}
    return {}


def save_station_cache(cache_path, cache):
    cache_path.write_text(json.dumps(cache, indent=2))


def load_ignore_set(ignore_path):
    """Load the set of node_ids confirmed as outside our radius."""
    if ignore_path.exists():
        return set(json.loads(ignore_path.read_text()))
    return set()


def save_ignore_set(ignore_path, ignore_set):
    ignore_path.write_text(json.dumps(sorted(ignore_set), indent=2))


def fetch_local_prices(local_node_ids, token, since_date, label="prices "):
    """Page through the price feed and return records for local stations only.

    Stops early once every local station has reported a price in this batch,
    avoiding downloading the full national dataset unnecessarily.
    """
    results     = []
    remaining   = set(local_node_ids)   # IDs we still need prices for
    batch       = 1
    headers     = {"Authorization": f"Bearer {token}"}
    while remaining:
        params = {"batch-number": batch, "effective-start-timestamp": since_date}
        for attempt in range(4):
            try:
                resp = requests.get(
                    BASE_URL + PRICES_PATH,
                    headers=headers,
                    params=params,
                    timeout=(10, 90),
                )
                if resp.status_code == 504:
                    wait = BATCH_DELAY_SECS * (attempt + 2)
                    print(f"  {label}batch {batch}: 504 timeout (attempt {attempt + 1}/4), waiting {wait}s...")
                    time.sleep(wait)
                    if attempt == 3:
                        resp.raise_for_status()
                    continue
                break
            except requests.exceptions.ReadTimeout:
                wait = BATCH_DELAY_SECS * (attempt + 2)
                print(f"  {label}batch {batch}: read timeout (attempt {attempt + 1}/4), waiting {wait}s...")
                time.sleep(wait)
                if attempt == 3:
                    raise
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        found_this_page = 0
        for record in page:
            nid = record.get("node_id")
            if nid in remaining:
                results.append(record)
                remaining.discard(nid)
                found_this_page += 1
        print(f"  {label}batch {batch}: {len(page)} records, {found_this_page} local ({len(remaining)} still needed)")
        if len(page) < 500:
            break  # last page
        if not remaining:
            print(f"  All local stations covered — stopping early")
            break
        batch += 1
        time.sleep(BATCH_DELAY_SECS)
    return results


def station_from_pfs_record(record):
    loc  = record.get("location") or {}
    lat  = loc.get("latitude") or loc.get("lat")
    lon  = loc.get("longitude") or loc.get("lng") or loc.get("lon")
    if lat is None or lon is None:
        return None
    lat, lon = float(lat), float(lon)
    dist = haversine_miles(CHELTENHAM_LAT, CHELTENHAM_LON, lat, lon)
    if dist > RADIUS_MILES:
        return None
    loc_addr  = loc.get("address_line_1") or ""
    postcode  = loc.get("postcode") or ""
    # Avoid duplicating postcode if it's already at the end of address_line_1
    if postcode and loc_addr.upper().endswith(postcode.upper()):
        address = loc_addr
    elif postcode:
        address = f"{loc_addr}, {postcode}"
    else:
        address = loc_addr
    return {
        "trading_name":   record.get("trading_name") or "Unknown",
        "brand_name":     record.get("brand_name") or "",
        "distance_miles": round(dist, 2),
        "is_supermarket": bool(record.get("is_supermarket_service_station")),
        "address":        address,
        "postcode":       postcode,
        "lat":            round(lat, 6),
        "lon":            round(lon, 6),
    }


# -- Main ---------------------------------------------------------------------

if __name__ == "__main__":
    root            = helper.repo_root()
    cache_path      = root / "_data" / "fuel-stations.json"
    ignore_path     = root / "_data" / "ignore-stations.json"
    out_path        = root / "_data" / "fuel-prices.json"
    bootstrap       = "--bootstrap" in sys.argv

    FUEL_KEY   = os.getenv("FUEL_KEY") or ""
    FUEL_TOKEN = os.getenv("FUEL_TOKEN") or ""

    if not FUEL_KEY or not FUEL_TOKEN:
        print("Error: FUEL_KEY and FUEL_TOKEN environment variables are required")
        raise SystemExit(1)

    # 1. Authenticate — fresh token each run (per API security guidelines).
    print("Authenticating...")
    access_token = authenticate(FUEL_KEY, FUEL_TOKEN)
    print("  OK")

    lookback_date = (datetime.date.today() - datetime.timedelta(days=PRICE_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    # 2. Load station location cache and ignore list
    station_cache = load_station_cache(cache_path)
    ignore_set    = load_ignore_set(ignore_path)

    if bootstrap:
        print(f"Bootstrap mode: clearing ignore list ({len(ignore_set)} entries) and fetching all PFS records...")
        ignore_set = set()
        save_ignore_set(ignore_path, ignore_set)
        pfs_added = 0
        pfs_ignored = 0
        try:
            all_pfs = fetch_all_pages(PFS_PATH, access_token, label="PFS ")
            for record in all_pfs:
                nid   = record.get("node_id")
                entry = station_from_pfs_record(record)
                if entry:
                    # Preserve any stored prices when refreshing station metadata
                    existing = station_cache.get(nid) or {}
                    if existing.get("fuel_prices"):
                        entry["fuel_prices"]    = existing["fuel_prices"]
                        entry["prices_updated"] = existing["prices_updated"]
                    station_cache[nid] = entry
                    pfs_added += 1
                else:
                    station_cache.pop(nid, None)  # remove if previously local
                    ignore_set.add(nid)
                    pfs_ignored += 1
            save_station_cache(cache_path, station_cache)
            save_ignore_set(ignore_path, ignore_set)
            print(f"  Bootstrap complete: {pfs_added} local stations, {pfs_ignored} ignored")
        except Exception as e:
            print(f"  Bootstrap PFS fetch stopped ({e}); partial progress saved")
            save_station_cache(cache_path, station_cache)
            save_ignore_set(ignore_path, ignore_set)

        # Seed price history using the same early-exit approach as the daily run
        print(f"Seeding price history (last {PRICE_LOOKBACK_DAYS} days)...")
        try:
            local_ids       = set(station_cache.keys())
            historic_prices = fetch_local_prices(local_ids, access_token, lookback_date, label="seed-prices ")
            seeded = 0
            for record in historic_prices:
                nid    = record.get("node_id")
                cached = station_cache.get(nid)
                if cached:
                    new_prices = record.get("fuel_prices") or []
                    if new_prices:
                        existing_date = cached.get("prices_updated") or ""
                        record_date   = (record.get("effective_start_timestamp") or "")[:10]
                        if record_date >= existing_date:
                            cached["fuel_prices"]    = new_prices
                            cached["prices_updated"] = record_date or lookback_date
                            seeded += 1
            save_station_cache(cache_path, station_cache)
            print(f"  Price history seeded for {seeded} local stations")
        except Exception as e:
            print(f"  Price history seed stopped ({e}); partial progress saved")
            save_station_cache(cache_path, station_cache)
    else:
        print(f"Station cache: {len(station_cache)} local stations, {len(ignore_set)} ignored")

    # 3. Fetch prices for local stations (early exit once all reported in).
    local_ids  = set(station_cache.keys())
    print(f"Fetching prices for {len(local_ids)} local stations (lookback: {PRICE_LOOKBACK_DAYS} days, since {lookback_date})...")
    all_prices = fetch_local_prices(local_ids, access_token, lookback_date)
    print(f"  Price records returned for local stations: {len(all_prices)}")

    # 4. Merge fresh prices into the station cache.
    today       = datetime.date.today()
    today_str   = today.strftime("%Y-%m-%d")
    price_updates = 0
    for record in all_prices:
        nid    = record.get("node_id")
        cached = station_cache.get(nid)
        if cached:
            new_prices  = record.get("fuel_prices") or []
            record_date = (record.get("effective_start_timestamp") or "")[:10] or today_str
            if new_prices:
                existing_date = cached.get("prices_updated") or ""
                if record_date >= existing_date:
                    cached["fuel_prices"]    = new_prices
                    cached["prices_updated"] = record_date
                    price_updates += 1
    if price_updates:
        save_station_cache(cache_path, station_cache)
    print(f"Local stations with fresh prices: {price_updates}")

    # 5. Per-station latest as_of date.
    def station_as_of(station):
        change_dates = [
            (p.get("price_change_effective_timestamp") or "")[:10]
            for p in (station.get("fuel_prices") or [])
            if p.get("price_change_effective_timestamp")
        ]
        return max(change_dates) if change_dates else (station.get("prices_updated") or "")

    priced = {nid: s for nid, s in station_cache.items() if s.get("fuel_prices")}

    # 6. De-dupe: same name + postcode = same forecourt; keep the freshest.
    deduped = {}
    for nid, s in priced.items():
        key = ((s.get("trading_name") or "").strip().lower(),
               (s.get("postcode") or "").replace(" ", "").upper())
        keep = deduped.get(key)
        if keep is None or station_as_of(s) > station_as_of(priced[keep]):
            deduped[key] = nid
    kept_nids = set(deduped.values())
    print(f"Priced stations: {len(priced)} → {len(kept_nids)} after de-dupe")

    # 7. Fuel-type columns (fixed order, only those present).
    FUEL_ORDER = ["E10", "E5", "B7_STANDARD", "B7_PREMIUM", "SDV5"]
    present = set()
    for nid in kept_nids:
        for p in station_cache[nid]["fuel_prices"]:
            if p.get("fuel_type"):
                present.add(p["fuel_type"])
    fuel_type_cols = [ft for ft in FUEL_ORDER if ft in present] + \
                     sorted(ft for ft in present if ft not in FUEL_ORDER)

    # 8. Cheapest station per fuel type + area context (min / typical).
    cheapest = {}          # ft -> {"price","nid"}
    all_vals = {ft: [] for ft in fuel_type_cols}
    for nid in kept_nids:
        lookup = {p["fuel_type"]: p for p in station_cache[nid]["fuel_prices"] if p.get("fuel_type")}
        for ft in fuel_type_cols:
            p = lookup.get(ft)
            if p and p.get("price") is not None:
                val = float(p["price"])
                all_vals[ft].append(val)
                if ft not in cheapest or val < cheapest[ft]["price"]:
                    cheapest[ft] = {"price": val, "nid": nid}

    def median(xs):
        xs = sorted(xs)
        n = len(xs)
        if not n:
            return None
        mid = n // 2
        return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2

    context = []
    typical_by_ft = {}
    for ft in fuel_type_cols:
        vals = all_vals[ft]
        if vals:
            typical = round(median(vals), 1)
            typical_by_ft[ft] = typical
            context.append({
                "label":    fuel_label(ft),
                "cheapest": round(min(vals), 1),
                "typical":  typical,
            })

    # 9. Build render-ready rows, sorted by distance then name.
    ordered = sorted(
        kept_nids,
        key=lambda n: (station_cache[n]["distance_miles"], (station_cache[n]["trading_name"] or "").lower()),
    )

    stations = []
    for nid in ordered:
        s      = station_cache[nid]
        lookup = {p["fuel_type"]: p for p in s["fuel_prices"] if p.get("fuel_type")}
        as_of  = station_as_of(s) or "?"
        try:
            stale = (today - datetime.date.fromisoformat(as_of)).days > STALE_DAYS
        except ValueError:
            stale = True

        cells = []
        for ft in fuel_type_cols:
            p = lookup.get(ft)
            if p and p.get("price") is not None:
                val = float(p["price"])
                cells.append({
                    "display":  f"{val:.1f}p",
                    "val":      f"{val:.1f}",
                    "cheapest": cheapest.get(ft, {}).get("nid") == nid,
                })
            else:
                cells.append({"display": "–", "val": "9999", "cheapest": False})

        name = clean_name(s["trading_name"])

        # Cheapest available price for this station, for the map popup.
        avail = [float(lookup[ft]["price"]) for ft in fuel_type_cols
                 if lookup.get(ft) and lookup[ft].get("price") is not None]
        popup = name
        if avail:
            popup += f" — from {min(avail):.1f}p"

        stations.append({
            "name":           name,
            "address":        s.get("address") or "",
            "postcode":       s.get("postcode") or "",
            "lat":            s.get("lat"),
            "lon":            s.get("lon"),
            "distance_miles": s["distance_miles"],
            "is_supermarket": s.get("is_supermarket", False),
            "as_of":          as_of,
            "stale":          stale,
            "cells":          cells,
            "popup":          popup,
        })

    headline = []
    for ft in fuel_type_cols:
        if ft in cheapest:
            s = station_cache[cheapest[ft]["nid"]]
            raw_brand = s.get("brand_name") or ""
            brand = clean_name(raw_brand)
            entry = {
                "label": fuel_label(ft),
                "price": f"{cheapest[ft]['price']:.1f}",
                "name":  clean_name(s["trading_name"]),
                "brand": brand if brand and raw_brand.lower() != s["trading_name"].lower() else "",
            }
            typical = typical_by_ft.get(ft)
            if typical:
                price_per_litre = cheapest[ft]["price"]
                pct_cheaper     = (typical - price_per_litre) / typical * 100
                if pct_cheaper >= 0.1:
                    tank_saving = (typical - price_per_litre) * AVG_TANK_LITRES / 100
                    entry["pct_cheaper"] = f"{pct_cheaper:.1f}"
                    entry["tank_litres"] = AVG_TANK_LITRES
                    entry["tank_saving"] = f"{tank_saving:.2f}"
            headline.append(entry)


    payload = {
        "updated":       helper.updated_timestamp(),
        "updated_iso":   today_str,
        "radius_miles":  RADIUS_MILES,
        "lookback_days": PRICE_LOOKBACK_DAYS,
        "stale_days":    STALE_DAYS,
        "columns":       [fuel_label(ft) for ft in fuel_type_cols],
        "headline":      headline,
        "context":       context,
        "stations":      stations,
    }

    helper.write_json(out_path, payload)
    print(f"Wrote {len(stations)} stations to {out_path}")

