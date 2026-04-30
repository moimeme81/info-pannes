"""Affichage des pannes sur la carte."""
import json
import logging
from homeassistant.components.geo_location import GeoLocationEvent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle
from .const import DOMAIN, URL_VERSION, URL_MARKERS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configurer la géolocalisation."""
    # On vérifie si la carte est déjà chargée pour éviter les doublons si on a plusieurs adresses
    if hass.data[DOMAIN].get("geo_loaded"):
        return
    hass.data[DOMAIN]["geo_loaded"] = True

    session = async_get_clientsession(hass)
    
    async def update_outages():
        try:
            async with session.get(URL_VERSION) as r:
                version = json.loads(await r.text())
            async with session.get(URL_MARKERS.format(version=version)) as r:
                data = await r.json(content_type=None)
            
            events = []
            for p in data.get("pannes", []):
                coords = json.loads(p[4])
                events.append(HQOutageEvent(f"Panne ({p[0]} clients)", coords[1], coords[0], p[0]))
            async_add_entities(events)
        except Exception as e:
            _LOGGER.error("Erreur geo_location : %s", e)

    await update_outages()

class HQOutageEvent(GeoLocationEvent):
    def __init__(self, name, lat, lon, clients):
        self._name = name
        self._lat = lat
        self._lon = lon
        self._clients = clients

    @property
    def name(self): return self._name
    @property
    def latitude(self): return self._lat
    @property
    def longitude(self): return self._lon
    @property
    def source(self): return "hq_pannes"
    @property
    def unit_of_measurement(self): return "clients"
    @property
    def icon(self): return "mdi:transmission-tower"
