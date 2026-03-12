"""Hydro-Québec Outages integration for Home Assistant."""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import timedelta

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api_view import HydroQuebecDataView
from .const import DOMAIN, CONF_LOCATIONS, DEFAULT_SCAN_INTERVAL_MINUTES
from .hydroquebec_api import HydroQuebecOutagesAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

PANEL_URL_PATH = "hydroquebec-outages"
PANEL_TITLE    = "HQ Outages"
PANEL_ICON     = "mdi:transmission-tower-off"
PANEL_HTML     = "hydroquebec-panel.html"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register HTTP views once at startup (before any config entry loads)."""
    hass.http.register_view(HydroQuebecDataView(hass))
    return True


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

    # Copy panel HTML into www/ then register the sidebar panel
    _install_panel_html(hass)
    await _register_panel(hass, entry)

    return True


def _install_panel_html(hass: HomeAssistant) -> None:
    """Copy panel HTML into <config>/www/ so HA serves it at /local/."""
    src = os.path.join(os.path.dirname(__file__), "www", PANEL_HTML)
    www_dir = hass.config.path("www")
    os.makedirs(www_dir, exist_ok=True)
    dst = os.path.join(www_dir, PANEL_HTML)
    try:
        shutil.copy2(src, dst)
        _LOGGER.debug("Panel HTML installed to %s", dst)
    except OSError as err:
        _LOGGER.warning("Could not install panel HTML: %s", err)


async def _register_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the sidebar iframe panel."""
    # Remove stale registration first (safe if not registered)
    frontend.async_remove_panel(hass, PANEL_URL_PATH)

    locations = entry.data.get(CONF_LOCATIONS, [])
    # URL-encode the JSON so special chars don't break the iframe src
    import urllib.parse
    loc_param = urllib.parse.quote(json.dumps(locations, separators=(",", ":")))
    panel_url = f"/local/{PANEL_HTML}?locations={loc_param}"

    frontend.async_register_panel(
        hass,
        component_name="iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={"url": panel_url},
        require_admin=False,
    )
    _LOGGER.info("Registered HQ Outages panel at /%s → %s", PANEL_URL_PATH, panel_url)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
