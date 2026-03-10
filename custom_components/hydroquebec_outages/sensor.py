"""Sensors for Hydro-Québec Outages (counts + last updated)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
    """Set up sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    locations = entry.data.get(CONF_LOCATIONS, [])

    entities = []
    for location in locations:
        entities.append(HydroQuebecOutageCountSensor(coordinator, entry, location))
        entities.append(HydroQuebecPlannedCountSensor(coordinator, entry, location))
        entities.append(HydroQuebecCustomersAffectedSensor(coordinator, entry, location))

    async_add_entities(entities)


class _HydroQuebecBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor."""

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


class HydroQuebecOutageCountSensor(_HydroQuebecBaseSensor):
    """Sensor: number of active outages within radius."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "outages"
    _attr_icon = "mdi:transmission-tower-off"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._loc_name}_outage_count"

    @property
    def name(self) -> str:
        return "Nearby Outages"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        nearby = HydroQuebecOutagesAPI.filter_nearby(
            self.coordinator.data.get("outages", []),
            self._latitude,
            self._longitude,
            self._radius_km,
        )
        return len(nearby)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "location_name": self._loc_name,
            "radius_km": self._radius_km,
            "last_updated": self.coordinator.data.get("last_updated") if self.coordinator.data else None,
        }


class HydroQuebecPlannedCountSensor(_HydroQuebecBaseSensor):
    """Sensor: number of planned interruptions within radius."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "interruptions"
    _attr_icon = "mdi:calendar-clock"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._loc_name}_planned_count"

    @property
    def name(self) -> str:
        return "Nearby Planned Interruptions"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        nearby = HydroQuebecOutagesAPI.filter_nearby(
            self.coordinator.data.get("planned", []),
            self._latitude,
            self._longitude,
            self._radius_km,
        )
        return len(nearby)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "location_name": self._loc_name,
            "radius_km": self._radius_km,
            "last_updated": self.coordinator.data.get("last_updated") if self.coordinator.data else None,
        }


class HydroQuebecCustomersAffectedSensor(_HydroQuebecBaseSensor):
    """Sensor: total customers affected by outages within radius."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "customers"
    _attr_icon = "mdi:account-group"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._loc_name}_customers_affected"

    @property
    def name(self) -> str:
        return "Customers Affected Nearby"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        nearby = HydroQuebecOutagesAPI.filter_nearby(
            self.coordinator.data.get("outages", []),
            self._latitude,
            self._longitude,
            self._radius_km,
        )
        return sum(o.get("customers_affected", 0) for o in nearby)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        nearby = HydroQuebecOutagesAPI.filter_nearby(
            self.coordinator.data.get("outages", []),
            self._latitude,
            self._longitude,
            self._radius_km,
        )
        return {
            "location_name": self._loc_name,
            "radius_km": self._radius_km,
            "outage_count": len(nearby),
            "last_updated": self.coordinator.data.get("last_updated"),
        }
