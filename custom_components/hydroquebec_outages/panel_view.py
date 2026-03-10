"""HTTP view that serves the Hydro-Québec panel HTML page."""
from __future__ import annotations

import os

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

_PANEL_HTML = os.path.join(os.path.dirname(__file__), "www", "hydroquebec-panel.html")


class HydroQuebecPanelView(HomeAssistantView):
    """Serve the standalone map panel HTML."""

    url  = "/api/hydroquebec_outages/panel"
    name = "api:hydroquebec_outages:panel"
    requires_auth = False   # iframe panels load before HA auth context is injected

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        try:
            with open(_PANEL_HTML, encoding="utf-8") as f:
                html = f.read()
        except OSError:
            return web.Response(status=404, text="Panel HTML not found")

        # Forward any query params (locations) straight through — the HTML reads them
        return web.Response(
            content_type="text/html",
            charset="utf-8",
            text=html,
        )
