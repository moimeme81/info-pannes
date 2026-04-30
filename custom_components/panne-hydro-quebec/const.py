"""Constantes pour l'intégration Pannes Hydro-Québec."""
from datetime import timedelta

# TRÈS IMPORTANT : Le DOMAIN doit correspondre EXACTEMENT au nom de votre dossier
DOMAIN = "hydroquebec_outages"

CONF_ADDRESS = "address"
CONF_LAT = "lat"
CONF_LON = "lon"

URL_VERSION = "https://pannes.hydroquebec.com/pannes/donnees/v3_0/bisversion.json"
URL_MARKERS = "https://pannes.hydroquebec.com/pannes/donnees/v3_0/bismarkers{version}.json"
URL_KMZ = "https://pannes.hydroquebec.com/pannes/donnees/v3_0/bispoly{version}.kmz"

SCAN_INTERVAL = timedelta(minutes=15)
