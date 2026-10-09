"""Where the Care Quality Commission (CQC) data comes from, kept apart from
cqc.py so the source can be swapped without touching anything else.

It reads the CQC API (https://api.service.cqc.org.uk), which needs a
subscription key in the CQC_KEY environment variable (a GitHub secret in
Actions, .env locally). The list endpoint gives every location in
Gloucestershire with its postcode; the ones in our postcode districts are
then fetched one by one for their service types, specialisms and ratings.

load_locations(postcode_districts) returns one dict per location:
    id, ods_code, name, address, postcode, website, url,
    service_types (list), specialisms (list), category, care_home (bool),
    overall, published (YYYY-MM-DD or None),
    ratings: {"safe", "effective", "caring", "responsive", "well_led"}
"""
import os
import re

import helper

API = "https://api.service.cqc.org.uk/public/v1"
DATA_PAGE = "https://www.cqc.org.uk/about-us/transparency/using-cqc-data"
SOURCE_NAME = "CQC API: registered locations and latest ratings"

COUNTY = "Gloucestershire"
KEY_QUESTIONS = {"Safe": "safe", "Effective": "effective", "Caring": "caring",
                 "Responsive": "responsive", "Well-led": "well_led"}
VALID_RATINGS = ("Outstanding", "Good", "Requires improvement", "Inadequate")

# Load .env file for local development if present
_env_file = helper.repo_root() / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))


def _get(path, **params):
    key = os.environ.get("CQC_KEY")
    if not key:
        raise RuntimeError("CQC_KEY is not set")
    return helper.get(API + path, headers={"Ocp-Apim-Subscription-Key": key}, params=params, timeout=60).json()


def _postcode_ok(postcode, districts):
    return (postcode or "").strip().upper().split(" ")[0] in districts


def _listed(districts):
    """Ids of every location in the county whose postcode is in the districts."""
    ids, page = [], 1
    while True:
        data = _get("/locations", localAuthority=COUNTY, perPage=1000, page=page)
        ids.extend(loc["locationId"] for loc in data["locations"] if _postcode_ok(loc.get("postalCode"), districts))
        if page >= data["totalPages"]:
            return ids
        page += 1


def _website(url):
    url = (url or "").strip()
    if not url:
        return None
    return url if re.match(r"^https?://", url, re.I) else "https://" + url


def _rating(value):
    """The rating as CQC spells it elsewhere (the API varies the capitals), or None."""
    return next((r for r in VALID_RATINGS if r.lower() == (value or "").strip().lower()), None)


def _latest_rating(d):
    """(overall, published, key question ratings) from whichever is newest of the
    older inspection ratings (currentRatings) and the newer assessment
    ratings, which locations assessed under the current framework have
    instead."""
    candidates = []
    overall = (d.get("currentRatings") or {}).get("overall") or {}
    if _rating(overall.get("rating")):
        candidates.append((overall.get("reportDate") or "", _rating(overall["rating"]), overall.get("keyQuestionRatings") or []))
    for assessment in d.get("assessment") or []:
        published = (assessment.get("assessmentPlanPublishedDateTime") or "")[:10]
        for group in (assessment.get("ratings") or {}).get("asgRatings") or []:
            if _rating(group.get("rating")):
                candidates.append((published, _rating(group["rating"]), group.get("keyQuestionRatings") or []))
    if not candidates:
        return None, None, {}
    published, rating, questions = max(candidates, key=lambda c: c[0])
    return rating, published or None, {KEY_QUESTIONS[q["name"]]: _rating(q.get("rating"))
                                       for q in questions if q["name"] in KEY_QUESTIONS}


def _location(d):
    types = list(dict.fromkeys(t["name"].replace("Doctors/Gps", "Doctors/GPs") for t in d.get("gacServiceTypes") or []))
    overall, published, ratings = _latest_rating(d)
    lines = (d.get("postalAddressLine1"), d.get("postalAddressLine2"), d.get("postalAddressTownCity"))
    primary = next((c["name"] for c in d.get("inspectionCategories") or [] if str(c.get("primary")).lower() == "true"), None)
    return {
        "id": d["locationId"],
        "ods_code": d.get("odsCode") or None,
        "name": d["name"],
        "address": ", ".join(p.strip().strip(",") for p in lines if p and p.strip(" ,")),
        "postcode": (d.get("postalCode") or "").strip().upper(),
        "website": _website(d.get("website")),
        "url": f"https://www.cqc.org.uk/location/{d['locationId']}",
        "service_types": types,
        "specialisms": [s["name"] for s in d.get("specialisms") or []],
        "category": primary,
        "care_home": d.get("careHome") == "Y" or any(t in ("Residential homes", "Nursing homes") for t in types),
        "overall": overall,
        "published": published,
        "ratings": {key: ratings.get(key) for key in KEY_QUESTIONS.values()},
    }


def load_locations(postcode_districts):
    locations = []
    for location_id in sorted(_listed(postcode_districts)):
        detail = _get(f"/locations/{location_id}")
        if detail.get("registrationStatus", "Registered") == "Registered":
            locations.append(_location(detail))
    return locations
