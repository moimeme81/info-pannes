"""HTTP API view — exposes outage data + raw KMZ bytes to the Lovelace card."""
from __future__ import annotations

import io
import logging
import zipfile
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    API_ENDPOINT_DATA,
    API_BASE,
    BIS_VERSION_URL,
    AIP_VERSION_URL,
)

_LOGGER = logging.getLogger(__name__)


class HydroQuebecDataView(HomeAssistantView):
    """
    Single endpoint that returns everything the map card needs as JSON:
      {
        outages:  [...],         # parsed outage markers
        planned:  [...],         # parsed planned markers
        bis_kml:  "<kml>...",    # KML text extracted from bispoly KMZ
        aip_kml:  "<kml>...",    # KML text extracted from aippoly KMZ
        last_updated: "...",
      }
    The card can call this once and get all it needs.
    """

    url = API_ENDPOINT_DATA
    name = "api:hydroquebec_outages:data"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        session = async_get_clientsession(self._hass)

        payload: dict[str, Any] = {
            "outages": [],
            "planned": [],
            "bis_kml": None,
            "aip_kml": None,
            "last_updated": None,
        }

        # Pull latest data from coordinator if available
        domain_data = self._hass.data.get(DOMAIN, {})
        for entry_data in domain_data.values():
            coordinator = entry_data.get("coordinator")
            if coordinator and coordinator.data:
                payload["outages"] = coordinator.data.get("outages", [])
                payload["planned"] = coordinator.data.get("planned", [])
                payload["last_updated"] = coordinator.data.get("last_updated")
                break

        # Fetch KMZ files and extract KML
        try:
            bis_version = await _get_version(session, BIS_VERSION_URL, ("version", "bisversion"))
            if bis_version:
                kmz_url = f"{API_BASE}/bispoly{bis_version}.kmz"
                payload["bis_kml"] = await _fetch_kml_from_kmz(session, kmz_url)
        except Exception as err:
            _LOGGER.warning("Could not fetch BIS KMZ: %s", err)

        try:
            aip_version = await _get_version(session, AIP_VERSION_URL, ("version", "aipversion"))
            if aip_version:
                kmz_url = f"{API_BASE}/aippoly{aip_version}.kmz"
                payload["aip_kml"] = await _fetch_kml_from_kmz(session, kmz_url)
        except Exception as err:
            _LOGGER.warning("Could not fetch AIP KMZ: %s", err)

        return web.json_response(payload)


async def _get_version(session, url: str, keys: tuple) -> str | None:
    """Fetch a version JSON and extract the version string."""
    async with session.get(url, timeout=15) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    if isinstance(data, dict):
        for key in keys:
            if data.get(key):
                return str(data[key])
    # Raw string response
    return str(data).strip().strip('"') if data else None


async def _fetch_kml_from_kmz(session, url: str) -> str | None:
    """Download a KMZ (zip) and return the first KML file as a string."""
    async with session.get(url, timeout=30) as resp:
        resp.raise_for_status()
        raw = await resp.read()

    buf = io.BytesIO(raw)
    try:
        with zipfile.ZipFile(buf) as zf:
            kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kml_names:
                _LOGGER.warning("No KML file found in KMZ from %s", url)
                return None
            # Prefer the largest KML (some KMZs bundle icons too)
            kml_names.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
            return zf.read(kml_names[0]).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as err:
        _LOGGER.warning("Bad KMZ from %s: %s", url, err)
        return None
