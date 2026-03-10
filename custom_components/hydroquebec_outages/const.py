"""Constants for the Hydro-Québec Outages integration."""

DOMAIN = "hydroquebec_outages"

# API endpoints
API_BASE = "https://pannes.hydroquebec.com/pannes/donnees/v3_0"
BIS_VERSION_URL = f"{API_BASE}/bisversion.json"
BIS_MARKERS_URL = f"{API_BASE}/bismarkers{{version}}.json"
AIP_VERSION_URL = f"{API_BASE}/aipversion.json"
AIP_MARKERS_URL = f"{API_BASE}/aipmarkers{{version}}.json"

# Config keys
CONF_LOCATIONS = "locations"
CONF_LOCATION_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS_KM = "radius_km"

# Defaults
DEFAULT_RADIUS_KM = 5.0
DEFAULT_SCAN_INTERVAL_MINUTES = 15

# Cause codes
CAUSE_CODES = {
    "11": "Equipment failure",
    "12": "Equipment failure",
    "13": "Equipment failure",
    "14": "Equipment failure",
    "15": "Equipment failure",
    "58": "Equipment failure",
    "70": "Equipment failure",
    "72": "Equipment failure",
    "73": "Equipment failure",
    "74": "Equipment failure",
    "79": "Equipment failure",
    "21": "Weather conditions",
    "22": "Weather conditions",
    "24": "Weather conditions",
    "25": "Weather conditions",
    "26": "Weather conditions",
    "31": "Accident or incident",
    "32": "Accident or incident",
    "33": "Accident or incident",
    "34": "Accident or incident",
    "41": "Accident or incident",
    "42": "Accident or incident",
    "43": "Accident or incident",
    "44": "Accident or incident",
    "54": "Accident or incident",
    "55": "Accident or incident",
    "56": "Accident or incident",
    "57": "Accident or incident",
    "51": "Vegetation damage",
    "52": "Animal damage",
    "53": "Animal damage",
    "10": "Planned maintenance",
}

# Status codes
STATUS_CODES = {
    "A": "Work assigned",
    "L": "Crew at work",
    "R": "Crew en route",
}

# Sensor names
SENSOR_ACTIVE_OUTAGE = "active_outage"
SENSOR_PLANNED_INTERRUPTION = "planned_interruption"
SENSOR_NEARBY_OUTAGES_COUNT = "nearby_outages_count"
SENSOR_NEARBY_PLANNED_COUNT = "nearby_planned_count"

# KMZ polygon endpoints
BIS_POLY_URL = f"{API_BASE}/bispoly{{version}}.kmz"
AIP_POLY_URL = f"{API_BASE}/aippoly{{version}}.kmz"

# HA HTTP API paths (served by our api_view)
API_ENDPOINT_BASE = "/api/hydroquebec_outages"
API_ENDPOINT_DATA = f"{API_ENDPOINT_BASE}/data"
