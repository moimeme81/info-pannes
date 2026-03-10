"""Hydro-Québec Outages integration for Home Assistant."""
from __future__ import annotations

import logging
import os
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api_view import HydroQuebecDataView
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL_MINUTES
from .hydroquebec_api import HydroQuebecOutagesAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the HTTP API view and Lovelace resource once."""
    hass.http.register_view(HydroQuebecDataView(hass))

    # Copy the JS card into www/ so HA can serve it
    _ensure_www_resource(hass)

    return True


def _ensure_www_resource(hass: HomeAssistant) -> None:
    """Copy the bundled JS card file into <config>/www/ if not already there."""
    src = os.path.join(os.path.dirname(__file__), "www", "hydroquebec-outages-map-card.js")
    www_dir = hass.config.path("www")
    dst = os.path.join(www_dir, "hydroquebec-outages-map-card.js")

    if not os.path.isfile(src):
        _LOGGER.error("Map card JS not found at %s", src)
        return

    os.makedirs(www_dir, exist_ok=True)
    try:
        with open(src, "rb") as f_src, open(dst, "wb") as f_dst:
            f_dst.write(f_src.read())
        _LOGGER.info("Hydro-Québec map card installed to %s", dst)
    except OSError as err:
        _LOGGER.warning("Could not install map card JS: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hydro-Québec Outages from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = HydroQuebecOutagesAPI(hass)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=api.async_fetch_all,
        update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
