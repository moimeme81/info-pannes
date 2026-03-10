"""Hydro-Québec Outages integration for Home Assistant."""
from __future__ import annotations

import logging
import os
import re
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

JS_FILENAME   = "hydroquebec-outages-map-card.js"
JS_LOCAL_URL  = f"/local/{JS_FILENAME}"   # base URL without ?v=


def _read_card_version(src_path: str) -> str:
    """Extract CARD_VERSION from the JS source so the resource URL stays in sync."""
    try:
        with open(src_path) as f:
            for line in f:
                m = re.search(r'CARD_VERSION\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return "0"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the HTTP API view, copy JS card, and register Lovelace resource."""
    hass.http.register_view(HydroQuebecDataView(hass))

    src = os.path.join(os.path.dirname(__file__), "www", JS_FILENAME)
    _copy_www_resource(hass, src)

    version = _read_card_version(src)
    await _register_lovelace_resource(hass, version)

    return True


def _copy_www_resource(hass: HomeAssistant, src: str) -> None:
    """Copy the bundled JS card into <config>/www/ (always overwrite so updates apply)."""
    if not os.path.isfile(src):
        _LOGGER.error("Map card JS not found at %s", src)
        return

    www_dir = hass.config.path("www")
    os.makedirs(www_dir, exist_ok=True)
    dst = os.path.join(www_dir, JS_FILENAME)
    try:
        with open(src, "rb") as f_in, open(dst, "wb") as f_out:
            f_out.write(f_in.read())
        _LOGGER.debug("Hydro-Québec map card copied to %s", dst)
    except OSError as err:
        _LOGGER.warning("Could not copy map card JS: %s", err)


async def _register_lovelace_resource(hass: HomeAssistant, version: str) -> None:
    """
    Register (or update) the Lovelace JS resource with a cache-busting ?v= param.

    Uses the lovelace storage collection when available (HA ≥ 2022.x).
    Falls back gracefully if the API isn't available.
    """
    versioned_url = f"{JS_LOCAL_URL}?v={version}"

    try:
        from homeassistant.components.lovelace import resources as ll_resources  # type: ignore

        res_coll = ll_resources.ResourceStorageCollection(hass, hass.data.get("lovelace"))

        await res_coll.async_load()
        existing = {r["url"]: r["id"] for r in res_coll.async_items()}

        # Remove any stale entries for this file (different ?v= or no ?v=)
        stale = [
            rid for url, rid in existing.items()
            if JS_FILENAME in url and url != versioned_url
        ]
        for rid in stale:
            try:
                await res_coll.async_delete_item(rid)
                _LOGGER.info("Removed stale Lovelace resource: %s", rid)
            except Exception:  # noqa: BLE001
                pass

        # Add the versioned URL if not already present
        if versioned_url not in existing:
            await res_coll.async_create_item(
                {"res_type": "module", "url": versioned_url}
            )
            _LOGGER.info("Registered Lovelace resource: %s", versioned_url)
        else:
            _LOGGER.debug("Lovelace resource already current: %s", versioned_url)

    except Exception as err:  # noqa: BLE001
        # Non-fatal — user can register manually
        _LOGGER.warning(
            "Could not auto-register Lovelace resource (%s). "
            "Add it manually: Settings → Dashboards → Resources → %s (JavaScript module)",
            err, versioned_url,
        )


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
