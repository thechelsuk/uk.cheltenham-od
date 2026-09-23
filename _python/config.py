"""Settings shared by the _python fetchers: who we say we are, where
Cheltenham is, the APIs several scripts call, and how far each dataset
searches. Change a value here and every script that uses it follows.

Functions that use these live in helper.py.
"""

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

# Public Overpass (OpenStreetMap) servers, tried in order; the next one is
# used when a server is down or busy.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
)

# --- How far each dataset searches from CENTRE (or RACECOURSE) ---------------
# Units differ by source, as each API takes them; the suffix says which.
# Overpass only takes metres.

# Measures
# ---------
# The Environment Agency APIs (river levels, water quality) take kilometres.
# Open Charge Map (EV) takes km or miles.
# InPost takes metres.
# The others (DEFRA, sewage, foodbank, hospitals, roadworks) search wider
# and filter by distance in our own code, so any unit works.


AIR_QUALITY_RADIUS_KM = 20
CAR_PARKS_RADIUS_M = 6000
CYCLE_ROUTES_RADIUS_M = 8000
EV_CHARGING_RADIUS_KM = 6.0
FOODBANK_RADIUS_MILES = 10
HOSPITALS_RADIUS_MILES = 10
HOTELS_RADIUS_M = 6000
INPOST_MAX_DISTANCE_M = 15000
INTERESTS_RADIUS_M = 26000
PARKRUN_MAX_MILES = 4
PLAY_AREAS_RADIUS_MILES = 10
POST_OFFICES_RADIUS_M = 5000
RACING_RADIUS_M = 8000
RIVER_LEVELS_RADIUS_KM = {"level": 6, "rainfall": 12}
ROADWORKS_RADIUS_MILES = 10
SEWAGE_RADIUS_MILES = 4
WATER_QUALITY_RADIUS_KM = 8
