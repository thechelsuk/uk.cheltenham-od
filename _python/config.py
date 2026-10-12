"""Settings shared by the _python fetchers: who we say we are, where
Cheltenham is, the APIs several scripts call, and how far each dataset
searches. Change a value here and every script that uses it follows.

Functions that use these live in helper.py.
"""
import json
import pathlib

# --- Identity ---------------------------------------------------------------

USER_AGENT = "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"
HEADERS = {"User-Agent": USER_AGENT}

# --- Where Cheltenham is ------------------------------------------------------

# Cheltenham town centre (lat, lon). Every "miles from the town centre" figure
# and every search around town is measured from this one point.
CENTRE = (51.8994, -2.0783)

# Cheltenham Racecourse (Prestbury Park), the centre for race-day searches.
RACECOURSE = (51.9251, -2.0587)

# Cheltenham borough's ONS/GSS area code, as Nomis and the ONS use it.
AREA_CODE = "E07000078"

# Postcode districts covering Cheltenham and its surrounding villages.
POSTCODE_DISTRICTS = ("GL50", "GL51", "GL52", "GL53", "GL54")

# --- Shared APIs --------------------------------------------------------------

NOMIS_API = "https://www.nomisweb.co.uk/api/v01/dataset"
ODS_API = "https://directory.spineservices.nhs.uk/ORD/2-0-0"
POSTCODES_API = "https://api.postcodes.io/postcodes"
# The receiver Worker (uk.cheltenham-od.receiver) holding Street Manager works.
STREET_WORKS_URL = "https://cheltenham-od-receiver.cloudflare-10f.workers.dev/works.json"

# Public Overpass (OpenStreetMap) servers, tried in order; the next one is
# used when a server is down or busy.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
)

# --- How far each dataset searches from CENTRE (or RACECOURSE) ---------------
# Every distance-based page uses one of four bands, defined once in
# _data/distance-bands.json so the site glossary (/glossary) shows the same
# figures: town (walkable), local (the villages and hills around town),
# area (where people travel in from) and drive (worth a drive, like fuel).
# Each dataset below takes its band's miles, converted to the unit its API
# wants (the suffix says which; Overpass only takes metres).
# Exceptions keep their own figure and are listed in the same file.

_BANDS = {
    band["id"]: band["miles"]
    for band in json.loads((pathlib.Path(__file__).resolve().parents[1] / "_data" / "distance-bands.json")
                           .read_text(encoding="utf-8"))["bands"]
}
TOWN_MILES = _BANDS["town"]
LOCAL_MILES = _BANDS["local"]
AREA_MILES = _BANDS["area"]
DRIVE_MILES = _BANDS["drive"]

METRES_PER_MILE = 1609.344
KM_PER_MILE = METRES_PER_MILE / 1000

# Town
EV_CHARGING_RADIUS_KM = round(TOWN_MILES * KM_PER_MILE, 1)
HOTELS_RADIUS_M = round(TOWN_MILES * METRES_PER_MILE)
PERMIT_ZONES_RADIUS_M = round(TOWN_MILES * METRES_PER_MILE)
POST_OFFICES_RADIUS_M = round(TOWN_MILES * METRES_PER_MILE)
SEWAGE_RADIUS_MILES = TOWN_MILES
TAXI_RANKS_RADIUS_M = round(TOWN_MILES * METRES_PER_MILE)

# Local
CAR_PARKS_RADIUS_M = round(LOCAL_MILES * METRES_PER_MILE)
CYCLE_ROUTES_RADIUS_M = round(LOCAL_MILES * METRES_PER_MILE)
INPOST_MAX_DISTANCE_M = round(LOCAL_MILES * METRES_PER_MILE)
PLAY_AREAS_RADIUS_MILES = LOCAL_MILES
RACING_RADIUS_M = round(LOCAL_MILES * METRES_PER_MILE)  # from RACECOURSE
STREET_WORKS_RADIUS_MILES = LOCAL_MILES
WATER_QUALITY_RADIUS_KM = round(LOCAL_MILES * KM_PER_MILE, 1)
WILDFIRE_RADIUS_MILES = LOCAL_MILES
WILDFIRE_RADIUS_KM = round(LOCAL_MILES * KM_PER_MILE, 1)  # for the map and census-area searches

# Area
AIR_QUALITY_RADIUS_KM = round(AREA_MILES * KM_PER_MILE, 1)
FOODBANK_RADIUS_MILES = AREA_MILES
HOSPITALS_RADIUS_MILES = AREA_MILES
INTERESTS_RADIUS_M = round(AREA_MILES * METRES_PER_MILE)
ROADWORKS_RADIUS_MILES = AREA_MILES

# Drive
FUEL_RADIUS_MILES = DRIVE_MILES
PARKRUN_MAX_MILES = DRIVE_MILES

# Exceptions (see "exceptions" in _data/distance-bands.json)
# River gauges on Cheltenham's own rivers, rain gauges on the nearby hills.
RIVER_LEVELS_RADIUS_KM = {"level": 6, "rainfall": 12}
# Historic England's listed buildings are searched by area, in British
# National Grid metres: (min easting, min northing, max easting, max northing).
LISTED_BUILDINGS_BBOX = (391000, 218000, 398000, 225000)
