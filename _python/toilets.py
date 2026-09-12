#!/usr/bin/env python3
"""
Fetch toilet data from the Great British Toilet Map (toiletmap.org.uk),
filter to Cheltenham, named toilets only, and write to Jekyll's _data dir.

Source: https://www.toiletmap.org.uk/dataset
"""

import json
import re
import sys
from pathlib import Path

import requests

import helper

try:
    from better_profanity import profanity
    profanity.load_censor_words()
    HAS_PROFANITY_LIB = True
except ImportError:
    HAS_PROFANITY_LIB = False

# Extra terms not always caught by the profanity library, or too mild to be
# flagged as profanity but still clearly a joke/vandalism entry for a toilet
# map (e.g. "pee in bush"). Word-boundary matched, case-insensitive.
JUNK_KEYWORDS = [
    r"\bpee\b", r"\bwee\b", r"\bwee-?wee\b", r"\bpiss\b", r"\bpissing\b",
    r"\btoilet\s*joke\b", r"\btest\b", r"\bn/?a\b", r"\basdf+\b",
    r"\bxxx+\b", r"\bfake\b", r"\bdo\s*not\s*use\b", r"\bnot\s*real\b",
]
JUNK_PATTERN = re.compile("|".join(JUNK_KEYWORDS), re.IGNORECASE)

# Names that are a single very short/generic word are suspicious for a
# toilet map (a real venue name is rarely one bare common noun).
GENERIC_NAME_PATTERN = re.compile(
    r"^(bush|tree|hedge|field|grass|outside|somewhere|here|there|toilet|loo)$",
    re.IGNORECASE,
)

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_opening_times(raw) -> dict | None:
    """Convert the source's [[start,end], ...] x7 array into a labelled dict.

    Source convention (Mon=index 0 ... Sun=index 6):
      ["HH:MM", "HH:MM"] -> open that range
      ["00:00", "00:00"] -> open 24 hours (NOT closed)
      []                 -> closed that day
      whole field null   -> no data supplied

    Malformed entries (wrong length, unexpected shape) are marked "unknown"
    rather than raising, since source data quality is inconsistent.
    """
    if not raw or not isinstance(raw, list):
        return None

    parsed = {}
    for i, day in enumerate(DAYS):
        if i >= len(raw):
            parsed[day] = None
            continue
        entry = raw[i]
        if not entry:
            parsed[day] = "closed"
        elif isinstance(entry, list) and len(entry) == 2:
            start, end = entry
            if start == "00:00" and end == "00:00":
                parsed[day] = "24 hours"
            else:
                parsed[day] = f"{start}-{end}"
        else:
            parsed[day] = "unknown"
    return parsed


def summarise_opening_times(parsed: dict | None) -> str | None:
    """Collapse a day->hours dict into compressed ranges, e.g.
    'Mon-Fri 09:00-17:00, Sat-Sun closed'. Returns None if no data."""
    if not parsed:
        return None

    day_abbr = {
        "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
        "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
    }
    values = [parsed[d] for d in DAYS]

    groups = []  # list of (start_idx, end_idx, value)
    start = 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[start]:
            groups.append((start, i - 1, values[start]))
            start = i

    parts = []
    for start_idx, end_idx, value in groups:
        if start_idx == end_idx:
            day_label = day_abbr[DAYS[start_idx]]
        else:
            day_label = f"{day_abbr[DAYS[start_idx]]}-{day_abbr[DAYS[end_idx]]}"
        parts.append(f"{day_label} {value}")

    return ", ".join(parts)


# Real UK public toilet charges are typically 10p-£2. Anything above this
# in payment_details is implausible and more likely a joke/vandalism entry
# than a genuine price.
MAX_PLAUSIBLE_CHARGE_GBP = 5.0
PRICE_PATTERN = re.compile(r"£\s*(\d+(?:\.\d{1,2})?)")


def has_implausible_price(payment_details: str) -> bool:
    for match in PRICE_PATTERN.finditer(payment_details):
        if float(match.group(1)) > MAX_PLAUSIBLE_CHARGE_GBP:
            return True
    return False


def is_likely_junk(rec: dict) -> tuple[bool, str]:
    """Return (flagged, reason) — heuristic only."""
    name = (rec.get("name") or "").strip()
    notes = (rec.get("notes") or "").strip()
    payment_details = (rec.get("payment_details") or "").strip()
    combined = f"{name} {notes} {payment_details}"

    if HAS_PROFANITY_LIB and profanity.contains_profanity(combined):
        return True, "profanity"
    if JUNK_PATTERN.search(combined):
        return True, "keyword match"
    if has_implausible_price(payment_details):
        return True, "implausible price"
    if GENERIC_NAME_PATTERN.match(name):
        return True, "generic/implausible name"
    if len(name) <= 2:
        return True, "name too short"

    # All-24-hours-every-day is sometimes a genuine filling station, but
    # combined with a generic name it's more often unfilled placeholder data.
    raw_hours = rec.get("opening_times")
    if raw_hours and isinstance(raw_hours, list) and len(raw_hours) == 7:
        if all(h == ["00:00", "00:00"] for h in raw_hours) and len(name.split()) <= 1:
            return True, "24/7 hours + single-word name (likely placeholder)"

    return False, ""

DATASET_PAGE_URL = "https://www.toiletmap.org.uk/dataset"

# Fallback only used if the dataset page's markup changes shape and the
# scrape below fails outright. This WILL go stale — the scraper is the
# real source of truth.
FALLBACK_SOURCE_URL = (
    "https://p02w6qqjlqmja4sk.public.blob.vercel-storage.com/exports/"
    "toilets-2026-09-07T00%3A00%3A40.706Z-e0QMyHlRtmMUQPdYIXgbWVyMCRAUw6.json"
    "?download=1"
)


def find_json_download_url(page_url: str = DATASET_PAGE_URL) -> str:
    """Scrape the Toilet Map dataset page for the current JSON export link.

    The export filename/token changes every time the dataset is refreshed
    (e.g. toilets-2026-09-07T00%3A00%3A40.706Z-<token>.json), so it can't be
    hardcoded. The page lists a JSON link and a CSV link side by side, both
    hosted on the same vercel-storage.com/exports/ path — we grab hrefs
    ending in .json (ignoring the .csv one) and pick the first match.
    """
    resp = requests.get(
        page_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; toilet-data-fetcher/1.0)"},
        timeout=20,
    )
    resp.raise_for_status()

    # Matches href="...exports/....json?download=1" (or query params in
    # any order), whether the quotes are single or double.
    matches = re.findall(
        r'href=["\']([^"\']*?/exports/[^"\']*?\.json\?[^"\']*)["\']',
        resp.text,
    )
    if not matches:
        raise ValueError(
            f"Could not find a .json export link on {page_url} — "
            "page markup may have changed."
        )

    url = matches[0]
    # Hrefs pulled from raw HTML may contain HTML entities (e.g. &amp;).
    url = url.replace("&amp;", "&")
    return url

AREA_NAME = "Cheltenham"
IGNORE_IDS = {
    "2319b85caf99ec61aba515e4",
    "6448f645d84833e33775bf6e",
}


def fetch_data(url: str) -> list[dict]:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()

ACRONYMS = {"WH", "BP", "ASDA", "GWSR", "UK"}


def clean_name(name: str) -> str:
    return helper.clean_name(name, ACRONYMS)




def google_maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def clean_record(rec: dict) -> dict:
    """Keep only fields useful for a Jekyll site; flatten location."""
    lon, lat = rec["location"]["coordinates"]
    opening_times = parse_opening_times(rec.get("opening_times"))
    return {
        "id": rec["id"],
        "name": clean_name(rec["name"].strip()),
        "latitude": lat,
        "longitude": lon,
        "maps_url": google_maps_url(lat, lon),
        "accessible": rec.get("accessible"),
        "all_gender": rec.get("all_gender"),
        "baby_change": rec.get("baby_change"),
        "men": rec.get("men"),
        "women": rec.get("women"),
        "urinal_only": rec.get("urinal_only"),
        "radar_key": rec.get("radar"),
        "no_payment": rec.get("no_payment"),
        "payment_details": rec.get("payment_details"),
        "opening_times": opening_times,
        "opening_hours_summary": summarise_opening_times(opening_times),
        "notes": rec.get("notes"),
        "active": rec.get("active"),
        "verified_at": rec.get("verified_at"),
        "updated_at": rec.get("updated_at"),
    }


def filter_records(records: list[dict], area_name: str) -> tuple[list[dict], int]:
    """Return (clean, dropped_count), excluding ignored and junk records."""
    clean = []
    dropped = 0
    for rec in records:
        if rec.get("id") in IGNORE_IDS:
            dropped += 1
            continue
        areas = rec.get("areas")
        if not areas or areas.get("name") != area_name:
            continue
        name = rec.get("name")
        if not name or not name.strip():
            continue

        junk, _reason = is_likely_junk(rec)
        if junk:
            dropped += 1
            continue

        clean.append(clean_record(rec))
    return clean, dropped


def write_output(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def main() -> None:
    root = helper.repo_root()
    output_path = root / "_data/toilets.json"

    if not HAS_PROFANITY_LIB:
        print("Note: 'better_profanity' not installed — falling back to the "
              "custom keyword list only (pip install better_profanity).")

    try:
        source_url = find_json_download_url()
        print(f"Found current JSON export: {source_url}\n")
    except Exception as e:
        print(f"Warning: could not discover current export URL ({e}). "
              f"Falling back to last-known URL — this may 404.", file=sys.stderr)
        source_url = FALLBACK_SOURCE_URL

    print("Fetching data from source...")
    data = fetch_data(source_url)
    print(f"Total records fetched: {len(data)}")

    clean, dropped = filter_records(data, AREA_NAME)
    print(f"Named toilets in {AREA_NAME}: {len(clean) + dropped}")
    print(f"  Kept: {len(clean)}")
    print(f"  Dropped as junk: {dropped}")

    if not clean:
        print("No matching records found. Check AREA_NAME matches the 'areas.name' "
              "field in the source data (e.g. it may need to be a district/borough name).")
        sys.exit(1)

    clean.sort(key=lambda rec: rec["name"].lower())

    write_output(clean, output_path)
    print(f"Written {len(clean)} records to {output_path}")


if __name__ == "__main__":
    main()