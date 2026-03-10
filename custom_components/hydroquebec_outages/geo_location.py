"""
Geo location platform for Hydro-Québec Outages.

Creates geo_location entities for each active outage and planned interruption.
These automatically appear as pins on the built-in HA Map (sidebar).

Each entity has:
  - latitude / longitude  → position on the map
  - source                → groups entities under this integration
  - icon                  → mdi icon shown on the map pin
  - extra attributes      → cause, status, customers affected, times
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SOURCE = "Hydro-Québec"

OUTAGE_ICON  = "mdi:transmission-tower-off"
PLANNED_ICON = "mdi:calendar-clock"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up geo_location entities from coordinator data."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Track which entity unique_ids are currently registered so we can
    # add new ones and remove stale ones as the data refreshes.
    tracked: dict[str, HydroQuebecGeoEvent] = {}

    @callback
    def _handle_update() -> None:
        if not coordinator.data:
            return

        outages = coordinator.data.get("outages", [])
        planned = coordinator.data.get("planned", [])

        new_unique_ids: set[str] = set()
        to_add: list[HydroQuebecGeoEvent] = []

        # ── Active outages ────────────────────────────────────────────────
        for idx, o in enumerate(outages):
            if o.get("latitude") is None or o.get("longitude") is None:
                continue
            uid = f"{entry.entry_id}_outage_{idx}_{o.get('start_time','')}"
            new_unique_ids.add(uid)
            if uid not in tracked:
                entity = HydroQuebecGeoEvent(
                    unique_id=uid,
                    event_type="outage",
                    data=o,
                    entry_id=entry.entry_id,
                )
                tracked[uid] = entity
                to_add.append(entity)
            else:
                tracked[uid].update_data(o)

        # ── Planned interruptions ─────────────────────────────────────────
        for idx, p in enumerate(planned):
            if p.get("latitude") is None or p.get("longitude") is None:
                continue
            uid = f"{entry.entry_id}_planned_{idx}_{p.get('planned_start','')}"
            new_unique_ids.add(uid)
            if uid not in tracked:
                entity = HydroQuebecGeoEvent(
                    unique_id=uid,
                    event_type="planned",
                    data=p,
                    entry_id=entry.entry_id,
                )
                tracked[uid] = entity
                to_add.append(entity)
            else:
                tracked[uid].update_data(p)

        # ── Remove stale entities ─────────────────────────────────────────
        stale = set(tracked) - new_unique_ids
        for uid in stale:
            entity = tracked.pop(uid)
            hass.async_create_task(entity.async_remove())

        if to_add:
            async_add_entities(to_add)

        # Trigger state write on all tracked entities
        for entity in tracked.values():
            entity.async_write_ha_state()

    coordinator.async_add_listener(_handle_update)

    # Run immediately with current data
    if coordinator.data:
        _handle_update()


class HydroQuebecGeoEvent(CoordinatorEntity, GeolocationEvent):
    """A single outage or planned interruption as a geo_location entity."""

    _attr_should_poll = False
    _attr_source = SOURCE

    def __init__(
        self,
        unique_id: str,
        event_type: str,   # "outage" or "planned"
        data: dict[str, Any],
        entry_id: str,
    ) -> None:
        # GeolocationEvent doesn't take coordinator in __init__, skip CoordinatorEntity init
        GeolocationEvent.__init__(self)
        self._attr_unique_id = unique_id
        self._event_type = event_type
        self._data = data
        self._entry_id = entry_id
        self._apply_data(data)

    # ── CoordinatorEntity wiring (manual since we skip super().__init__) ──

    def update_data(self, data: dict[str, Any]) -> None:
        """Called when coordinator refreshes — update internal state."""
        self._data = data
        self._apply_data(data)

    def _apply_data(self, data: dict[str, Any]) -> None:
        """Set all entity attributes from raw data dict."""
        self._attr_latitude  = data.get("latitude")
        self._attr_longitude = data.get("longitude")

        if self._event_type == "outage":
            customers = data.get("customers_affected", "?")
            cause     = data.get("cause", "Unknown")
            est_end   = data.get("estimated_end_time", "")
            self._attr_name = f"Outage – {customers} customers – {cause}"
            self._attr_icon = OUTAGE_ICON
            # distance is required by GeolocationEvent — use 0 (local events)
            self._attr_distance = 0.0
        else:
            customers  = data.get("customers_affected", "?")
            cause      = data.get("cause", "Unknown")
            start_time = data.get("planned_start", "")
            self._attr_name = f"Planned – {customers} customers – {cause}"
            self._attr_icon = PLANNED_ICON
            self._attr_distance = 0.0

    # ── Extra state attributes shown in the entity detail panel ──────────

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data
        if self._event_type == "outage":
            return {
                "type":               "Active outage",
                "customers_affected": d.get("customers_affected"),
                "cause":              d.get("cause"),
                "status":             d.get("status"),
                "start_time":         d.get("start_time"),
                "estimated_end_time": d.get("estimated_end_time"),
                "source":             SOURCE,
            }
        return {
            "type":               "Planned interruption",
            "customers_affected": d.get("customers_affected"),
            "cause":              d.get("cause"),
            "status":             d.get("status"),
            "planned_start":      d.get("planned_start"),
            "planned_end":        d.get("planned_end"),
            "notice_id":          d.get("notice_id"),
            "source":             SOURCE,
        }

    # ── Required GeolocationEvent properties ─────────────────────────────

    @property
    def source(self) -> str:
        return SOURCE

    @property
    def distance(self) -> float | None:
        return self._attr_distance

    @property
    def latitude(self) -> float | None:
        return self._attr_latitude

    @property
    def longitude(self) -> float | None:
        return self._attr_longitude
