"""Config flow for Hydro-Québec Outages."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    default_name: str = "",
    default_lat: float | None = None,
    default_lon: float | None = None,
    default_radius: float = DEFAULT_RADIUS_KM,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LOCATION_NAME, default=default_name): str,
            vol.Required(
                CONF_LATITUDE,
                default=default_lat,
            ): selector.selector({"number": {"min": -90, "max": 90, "step": 0.000001, "mode": "box"}}),
            vol.Required(
                CONF_LONGITUDE,
                default=default_lon,
            ): selector.selector({"number": {"min": -180, "max": 180, "step": 0.000001, "mode": "box"}}),
            vol.Required(CONF_RADIUS_KM, default=default_radius): selector.selector(
                {"number": {"min": 0.5, "max": 100, "step": 0.5, "unit_of_measurement": "km", "mode": "slider"}}
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
        """First step: add the first location."""
        errors: dict[str, str] = {}

        # Pre-fill with HA's configured home location
        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude

        if user_input is not None:
            try:
                lat = float(user_input[CONF_LATITUDE])
                lon = float(user_input[CONF_LONGITUDE])
                radius = float(user_input[CONF_RADIUS_KM])
                name = str(user_input[CONF_LOCATION_NAME]).strip()
                if not name:
                    errors[CONF_LOCATION_NAME] = "name_required"
                else:
                    self._locations = [
                        {
                            CONF_LOCATION_NAME: name,
                            CONF_LATITUDE: lat,
                            CONF_LONGITUDE: lon,
                            CONF_RADIUS_KM: radius,
                        }
                    ]
                    return self.async_create_entry(
                        title=name,
                        data={CONF_LOCATIONS: self._locations},
                    )
            except (ValueError, TypeError):
                errors["base"] = "invalid_coordinates"

        schema = _location_schema(
            default_name="Home",
            default_lat=home_lat,
            default_lon=home_lon,
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "docs_url": "https://donnees.hydroquebec.com/explore/dataset/pannes-interruptions/information/"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return HydroQuebecOutagesOptionsFlow(config_entry)


class HydroQuebecOutagesOptionsFlow(config_entries.OptionsFlow):
    """Handle options (add/edit/remove locations)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._locations: list[dict[str, Any]] = list(
            config_entry.data.get(CONF_LOCATIONS, [])
        )
        self._edit_index: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_location", "remove_location", "done"],
        )

    async def async_step_add_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new location."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                name = str(user_input[CONF_LOCATION_NAME]).strip()
                if not name:
                    errors[CONF_LOCATION_NAME] = "name_required"
                else:
                    self._locations.append(
                        {
                            CONF_LOCATION_NAME: name,
                            CONF_LATITUDE: float(user_input[CONF_LATITUDE]),
                            CONF_LONGITUDE: float(user_input[CONF_LONGITUDE]),
                            CONF_RADIUS_KM: float(user_input[CONF_RADIUS_KM]),
                        }
                    )
                    return await self._save_and_finish()
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
        """Remove an existing location."""
        if not self._locations:
            return await self._save_and_finish()

        if user_input is not None:
            selected_name = user_input.get("location")
            self._locations = [
                loc for loc in self._locations if loc[CONF_LOCATION_NAME] != selected_name
            ]
            return await self._save_and_finish()

        location_names = [loc[CONF_LOCATION_NAME] for loc in self._locations]
        return self.async_show_form(
            step_id="remove_location",
            data_schema=vol.Schema(
                {
                    vol.Required("location"): selector.selector(
                        {"select": {"options": location_names}}
                    )
                }
            ),
        )

    async def async_step_done(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self._save_and_finish()

    async def _save_and_finish(self) -> FlowResult:
        # Persist locations back into the config entry data
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data={**self._config_entry.data, CONF_LOCATIONS: self._locations},
        )
        return self.async_create_entry(title="", data={})
