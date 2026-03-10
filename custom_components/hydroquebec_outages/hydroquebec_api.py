"""Hydro-Québec API client."""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BIS_VERSION_URL,
    BIS_MARKERS_URL,
    AIP_VERSION_URL,
    AIP_MARKERS_URL,
    CAUSE_CODES,
    STATUS_CODES,
)

_LOGGER = logging.getLogger(__name__)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_coordinates(coord_str: str) -> tuple[float, float] | None:
    """Parse '[lon, lat]' coordinate string from the API."""
    try:
        coords = json.loads(coord_str)
        # API returns [longitude, latitude]
        return float(coords[1]), float(coords[0])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _decode_cause(code: str) -> str:
    """Decode a cause code to human-readable string."""
    return CAUSE_CODES.get(str(code), f"Unknown ({code})")


def _decode_status(code: str) -> str:
    """Decode a status code to human-readable string."""
    return STATUS_CODES.get(str(code), str(code))


def _parse_outage(row: list) -> dict[str, Any]:
    """
    Parse a raw outage row from bismarkers JSON.

    Row format (0-indexed):
      0: customers_affected
      1: start_time
      2: estimated_end_time
      3: type ('P' = outage)
      4: coordinates '[lon, lat]'
      5: status (A/L/R)
      6: (unused)
      7: (unused)
      8: cause_code
      9: message_id
    """
    coords = _parse_coordinates(row[4]) if len(row) > 4 else None
    return {
        "customers_affected": int(row[0]) if row[0] else 0,
        "start_time": row[1] if len(row) > 1 else None,
        "estimated_end_time": row[2] if len(row) > 2 else None,
        "type": row[3] if len(row) > 3 else None,
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
        "status": _decode_status(row[5]) if len(row) > 5 else None,
        "cause": _decode_cause(row[8]) if len(row) > 8 else "Unknown",
        "cause_code": str(row[8]) if len(row) > 8 else None,
    }


def _parse_planned(row: list) -> dict[str, Any]:
    """
    Parse a raw planned interruption row from aipmarkers JSON.

    Row format varies but key fields include:
      0: customers_affected
      1: notice_id
      2: planned_start
      3: planned_end
      4: actual_start
      5: actual_end
      6: postponed_start
      7: postponed_end
      8: rescheduled_start
      9: rescheduled_end
      10: cause_code
      11: remark_code
      12: municipality_id
      13: status
      14: coordinates '[lon, lat]'
    """
    coords = _parse_coordinates(row[14]) if len(row) > 14 else None
    return {
        "customers_affected": int(row[0]) if row[0] else 0,
        "notice_id": row[1] if len(row) > 1 else None,
        "planned_start": row[2] if len(row) > 2 else None,
        "planned_end": row[3] if len(row) > 3 else None,
        "actual_start": row[4] if len(row) > 4 else None,
        "actual_end": row[5] if len(row) > 5 else None,
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
        "cause": _decode_cause(row[10]) if len(row) > 10 else "Unknown",
        "cause_code": str(row[10]) if len(row) > 10 else None,
        "status": _decode_status(row[13]) if len(row) > 13 else None,
    }


class HydroQuebecOutagesAPI:
    """Client for the Hydro-Québec outages open data API."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._session = None

    def _get_session(self):
        if self._session is None:
            self._session = async_get_clientsession(self._hass)
        return self._session

    async def _get_json(self, url: str) -> Any:
        session = self._get_session()
        async with session.get(url, timeout=30) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def async_fetch_outages(self) -> list[dict[str, Any]]:
        """Fetch all current outages."""
        try:
            version_data = await self._get_json(BIS_VERSION_URL)
            version = version_data.get("version") or version_data.get("bisversion")
            if not version:
                # Try raw string
                version = str(version_data).strip().strip('"')
            markers_url = BIS_MARKERS_URL.format(version=version)
            data = await self._get_json(markers_url)
            pannes = data.get("pannes", [])
            return [_parse_outage(row) for row in pannes if isinstance(row, list)]
        except Exception as err:
            _LOGGER.warning("Failed to fetch outages: %s", err)
            return []

    async def async_fetch_planned(self) -> list[dict[str, Any]]:
        """Fetch all planned interruptions."""
        try:
            version_data = await self._get_json(AIP_VERSION_URL)
            version = version_data.get("version") or version_data.get("aipversion")
            if not version:
                version = str(version_data).strip().strip('"')
            markers_url = AIP_MARKERS_URL.format(version=version)
            data = await self._get_json(markers_url)
            aips = data.get("avis", data.get("pannes", []))
            return [_parse_planned(row) for row in aips if isinstance(row, list)]
        except Exception as err:
            _LOGGER.warning("Failed to fetch planned interruptions: %s", err)
            return []

    async def async_fetch_all(self) -> dict[str, Any]:
        """Fetch both outages and planned interruptions."""
        outages = await self.async_fetch_outages()
        planned = await self.async_fetch_planned()
        return {
            "outages": outages,
            "planned": planned,
            "last_updated": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def filter_nearby(
        events: list[dict[str, Any]],
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[dict[str, Any]]:
        """Filter events to those within radius_km of the given coordinates."""
        nearby = []
        for event in events:
            elat = event.get("latitude")
            elon = event.get("longitude")
            if elat is None or elon is None:
                continue
            dist = _haversine_km(latitude, longitude, elat, elon)
            if dist <= radius_km:
                nearby.append({**event, "distance_km": round(dist, 2)})
        return sorted(nearby, key=lambda x: x["distance_km"])
