"""Config flow for Hydro-Québec Outages."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_LOCATIONS,
    CONF_LOCATION_NAME,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    DEFAULT_RADIUS_KM,
)

_LOGGER = logging.getLogger(__name__)


def _location_schema(
    default_name: str = "Home",
    default_lat: float = 45.5017,
    default_lon: float = -73.5673,
    default_radius: float = DEFAULT_RADIUS_KM,
) -> vol.Schema:
    """Build a voluptuous schema for a monitored location."""
    return vol.Schema(
        {
            vol.Required(CONF_LOCATION_NAME, default=default_name): str,
            vol.Required(CONF_LATITUDE, default=default_lat): vol.Coerce(float),
            vol.Required(CONF_LONGITUDE, default=default_lon): vol.Coerce(float),
            vol.Required(CONF_RADIUS_KM, default=default_radius): vol.All(
                vol.Coerce(float), vol.Range(min=0.1, max=200)
            ),
        }
    )


class HydroQuebecOutagesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._locations: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step: configure the first location."""
        errors: dict[str, str] = {}

        home_lat = self.hass.config.latitude or 45.5017
        home_lon = self.hass.config.longitude or -73.5673

        if user_input is not None:
            try:
                name = str(user_input[CONF_LOCATION_NAME]).strip()
                lat = float(user_input[CONF_LATITUDE])
                lon = float(user_input[CONF_LONGITUDE])
                radius = float(user_input[CONF_RADIUS_KM])

                if not name:
                    errors[CONF_LOCATION_NAME] = "name_required"
                elif not (-90 <= lat <= 90):
                    errors[CONF_LATITUDE] = "invalid_coordinates"
                elif not (-180 <= lon <= 180):
                    errors[CONF_LONGITUDE] = "invalid_coordinates"
                else:
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_LOCATIONS: [
                                {
                                    CONF_LOCATION_NAME: name,
                                    CONF_LATITUDE: lat,
                                    CONF_LONGITUDE: lon,
                                    CONF_RADIUS_KM: radius,
                                }
                            ]
                        },
                    )
            except (ValueError, TypeError):
                errors["base"] = "invalid_coordinates"

        return self.async_show_form(
            step_id="user",
            data_schema=_location_schema(
                default_lat=home_lat,
                default_lon=home_lon,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HydroQuebecOutagesOptionsFlow":
        return HydroQuebecOutagesOptionsFlow(config_entry)


class HydroQuebecOutagesOptionsFlow(config_entries.OptionsFlow):
    """Handle options: add / remove monitored locations."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._locations: list[dict[str, Any]] = list(
            config_entry.data.get(CONF_LOCATIONS, [])
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show action selector: add or remove."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_location()
            if action == "remove":
                return await self.async_step_remove_location()
            return self._finish()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): vol.In(
                        {
                            "add": "Add a location",
                            "remove": "Remove a location",
                            "done": "Done (save & close)",
                        }
                    )
                }
            ),
        )

    async def async_step_add_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new location."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                name = str(user_input[CONF_LOCATION_NAME]).strip()
                lat = float(user_input[CONF_LATITUDE])
                lon = float(user_input[CONF_LONGITUDE])
                radius = float(user_input[CONF_RADIUS_KM])

                if not name:
                    errors[CONF_LOCATION_NAME] = "name_required"
                elif not (-90 <= lat <= 90):
                    errors[CONF_LATITUDE] = "invalid_coordinates"
                elif not (-180 <= lon <= 180):
                    errors[CONF_LONGITUDE] = "invalid_coordinates"
                else:
                    self._locations.append(
                        {
                            CONF_LOCATION_NAME: name,
                            CONF_LATITUDE: lat,
                            CONF_LONGITUDE: lon,
                            CONF_RADIUS_KM: radius,
                        }
                    )
                    return self._finish()
            except (ValueError, TypeError):
                errors["base"] = "invalid_coordinates"

        return self.async_show_form(
            step_id="add_location",
            data_schema=_location_schema(),
            errors=errors,
        )

    async def async_step_remove_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a location by name."""
        if not self._locations:
            return self._finish()

        if user_input is not None:
            selected = user_input.get("location_name")
            self._locations = [
                loc
                for loc in self._locations
                if loc[CONF_LOCATION_NAME] != selected
            ]
            return self._finish()

        location_names = [loc[CONF_LOCATION_NAME] for loc in self._locations]
        return self.async_show_form(
            step_id="remove_location",
            data_schema=vol.Schema(
                {
                    vol.Required("location_name"): vol.In(location_names),
                }
            ),
        )

    def _finish(self) -> FlowResult:
        """Save updated locations back to config entry data and close options."""
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={**self._config_entry.data, CONF_LOCATIONS: self._locations},
        )
        return self.async_create_entry(title="", data={})
