"""Binary sensors for Hydro-Québec Outages."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_LOCATIONS,
    CONF_LOCATION_NAME,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
)
from .hydroquebec_api import HydroQuebecOutagesAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    locations = entry.data.get(CONF_LOCATIONS, [])

    entities = []
    for location in locations:
        entities.append(
            HydroQuebecOutageBinarySensor(coordinator, entry, location)
        )
        entities.append(
            HydroQuebecPlannedBinarySensor(coordinator, entry, location)
        )

    async_add_entities(entities)


class _HydroQuebecBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Hydro-Québec binary sensors."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, location: dict) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._location = location
        self._loc_name = location[CONF_LOCATION_NAME]
        self._latitude = location[CONF_LATITUDE]
        self._longitude = location[CONF_LONGITUDE]
        self._radius_km = location[CONF_RADIUS_KM]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._loc_name}")},
            name=f"Hydro-Québec – {self._loc_name}",
            manufacturer="Hydro-Québec",
            model="Outage Monitor",
            entry_type=DeviceEntryType.SERVICE,
        )


class HydroQuebecOutageBinarySensor(_HydroQuebecBaseBinarySensor):
    """Binary sensor: True when there is an active outage near the location."""

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._loc_name}_active_outage"

    @property
    def name(self) -> str:
        return "Active Outage"

    @property
    def _nearby_outages(self) -> list[dict[str, Any]]:
        if not self.coordinator.data:
            return []
        return HydroQuebecOutagesAPI.filter_nearby(
            self.coordinator.data.get("outages", []),
            self._latitude,
            self._longitude,
            self._radius_km,
        )

    @property
    def is_on(self) -> bool:
        return len(self._nearby_outages) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nearby = self._nearby_outages
        attrs: dict[str, Any] = {
            "location_name": self._loc_name,
            "monitored_latitude": self._latitude,
            "monitored_longitude": self._longitude,
            "radius_km": self._radius_km,
            "outage_count": len(nearby),
        }
        if nearby:
            closest = nearby[0]
            attrs.update(
                {
                    "closest_outage_distance_km": closest.get("distance_km"),
                    "closest_outage_customers_affected": closest.get("customers_affected"),
                    "closest_outage_start_time": closest.get("start_time"),
                    "closest_outage_estimated_end": closest.get("estimated_end_time"),
                    "closest_outage_cause": closest.get("cause"),
                    "closest_outage_status": closest.get("status"),
                    "closest_outage_latitude": closest.get("latitude"),
                    "closest_outage_longitude": closest.get("longitude"),
                    "all_outages": [
                        {
                            "distance_km": o.get("distance_km"),
                            "customers_affected": o.get("customers_affected"),
                            "start_time": o.get("start_time"),
                            "estimated_end_time": o.get("estimated_end_time"),
                            "cause": o.get("cause"),
                            "status": o.get("status"),
                            "latitude": o.get("latitude"),
                            "longitude": o.get("longitude"),
                        }
                        for o in nearby
                    ],
                }
            )
        return attrs


class HydroQuebecPlannedBinarySensor(_HydroQuebecBaseBinarySensor):
    """Binary sensor: True when there is a planned interruption near the location."""

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._loc_name}_planned_interruption"

    @property
    def name(self) -> str:
        return "Planned Interruption"

    @property
    def _nearby_planned(self) -> list[dict[str, Any]]:
        if not self.coordinator.data:
            return []
        return HydroQuebecOutagesAPI.filter_nearby(
            self.coordinator.data.get("planned", []),
            self._latitude,
            self._longitude,
            self._radius_km,
        )

    @property
    def is_on(self) -> bool:
        return len(self._nearby_planned) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nearby = self._nearby_planned
        attrs: dict[str, Any] = {
            "location_name": self._loc_name,
            "monitored_latitude": self._latitude,
            "monitored_longitude": self._longitude,
            "radius_km": self._radius_km,
            "planned_count": len(nearby),
        }
        if nearby:
            closest = nearby[0]
            attrs.update(
                {
                    "closest_planned_distance_km": closest.get("distance_km"),
                    "closest_planned_customers_affected": closest.get("customers_affected"),
                    "closest_planned_start": closest.get("planned_start"),
                    "closest_planned_end": closest.get("planned_end"),
                    "closest_planned_cause": closest.get("cause"),
                    "closest_planned_status": closest.get("status"),
                    "closest_planned_latitude": closest.get("latitude"),
                    "closest_planned_longitude": closest.get("longitude"),
                    "all_planned": [
                        {
                            "distance_km": p.get("distance_km"),
                            "customers_affected": p.get("customers_affected"),
                            "planned_start": p.get("planned_start"),
                            "planned_end": p.get("planned_end"),
                            "cause": p.get("cause"),
                            "status": p.get("status"),
                            "latitude": p.get("latitude"),
                            "longitude": p.get("longitude"),
                        }
                        for p in nearby
                    ],
                }
            )
        return attrs
