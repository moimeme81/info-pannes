/**
 * Hydro-Québec Outages Map Card
 * Lovelace custom card — displays outage polygons + planned interruption
 * polygons on a Leaflet map, sourced from the Hydro-Québec open data API.
 *
 * Usage in Lovelace YAML:
 *   type: custom:hydroquebec-outages-map-card
 *   title: "Hydro-Québec Outages"          # optional
 *   latitude: 45.5017                       # map centre (optional, uses HA home)
 *   longitude: -73.5673
 *   zoom: 10                                # initial zoom (default 10)
 *   height: 500                             # card height px (default 500)
 *   locations:                              # optional pins
 *     - name: Home
 *       latitude: 45.5017
 *       longitude: -73.5673
 */

const CARD_VERSION = "1.2.0";
const DATA_URL = "/api/hydroquebec_outages/data";

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const JSZIP_JS    = "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js";

// ── Palette ────────────────────────────────────────────────────────────────
const COLOR = {
  outage:         { fill: "#e53935", border: "#b71c1c" },
  planned:        { fill: "#fb8c00", border: "#e65100" },
  locationPin:    "#1565c0",
  radiusCircle:   { fill: "#1565c020", border: "#1565c0" },
};

// ── KML polygon parser ─────────────────────────────────────────────────────
function parseKmlPolygons(kmlText) {
  if (!kmlText) return [];
  const parser = new DOMParser();
  const doc = parser.parseFromString(kmlText, "text/xml");
  const polygons = [];

  // Each <Placemark> may have one or more <Polygon> children
  doc.querySelectorAll("Placemark").forEach(pm => {
    const name = pm.querySelector("name")?.textContent?.trim() || "";
    const desc = pm.querySelector("description")?.textContent?.trim() || "";

    pm.querySelectorAll("Polygon").forEach(poly => {
      const outerRing = poly.querySelector("outerBoundaryIs coordinates,outerBoundaryIs > LinearRing > coordinates");
      if (!outerRing) return;

      const coords = outerRing.textContent.trim()
        .split(/\s+/)
        .map(t => {
          const parts = t.split(",");
          if (parts.length < 2) return null;
          const lon = parseFloat(parts[0]);
          const lat = parseFloat(parts[1]);
          if (isNaN(lat) || isNaN(lon)) return null;
          return [lat, lon];   // Leaflet uses [lat, lon]
        })
        .filter(Boolean);

      if (coords.length > 2) {
        polygons.push({ name, desc, coords });
      }
    });
  });

  return polygons;
}

// ── Async script loader ────────────────────────────────────────────────────
function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
    const s = document.createElement("script");
    s.src = src; s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  });
}

function loadStylesheet(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const l = document.createElement("link");
  l.rel = "stylesheet"; l.href = href;
  document.head.appendChild(l);
}

// ══════════════════════════════════════════════════════════════════════════
class HydroQuebecOutagesMapCard extends HTMLElement {

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._map = null;
    this._outageLayer = null;
    this._plannedLayer = null;
    this._pinLayer = null;
    this._radiusLayer = null;
    this._loaded = false;
    this._refreshTimer = null;
  }

  // ── Lovelace lifecycle ───────────────────────────────────────────────────

  setConfig(config) {
    this._config = {
      title:     config.title     ?? "Hydro-Québec Outages",
      latitude:  config.latitude  ?? null,
      longitude: config.longitude ?? null,
      zoom:      config.zoom      ?? 10,
      height:    config.height    ?? 500,
      locations: config.locations ?? [],
    };
    this._buildShell();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._initMap();
    }
  }

  disconnectedCallback() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
    if (this._map) { this._map.remove(); this._map = null; }
  }

  // ── DOM skeleton ─────────────────────────────────────────────────────────

  _buildShell() {
    const cfg = this._config;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        #map { width: 100%; height: ${cfg.height}px; background: #e8e0d8; }
        #status-bar {
          display: flex; align-items: center; gap: 8px;
          padding: 6px 12px; font-size: 12px;
          background: var(--card-background-color, #fff);
          color: var(--secondary-text-color, #666);
          border-top: 1px solid var(--divider-color, #e0e0e0);
        }
        .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .dot-outage  { background: ${COLOR.outage.fill}; }
        .dot-planned { background: ${COLOR.planned.fill}; }
        #refresh-btn {
          margin-left: auto; cursor: pointer; padding: 2px 8px;
          border: 1px solid var(--divider-color, #ccc);
          border-radius: 4px; background: transparent;
          color: var(--primary-color, #03a9f4); font-size: 12px;
        }
        #last-updated { margin-left: 4px; font-style: italic; }
        #loading-overlay {
          position: absolute; inset: 0;
          display: flex; align-items: center; justify-content: center;
          background: rgba(255,255,255,0.7); font-size: 14px;
          color: #555; pointer-events: none; z-index: 500;
        }
        .map-wrapper { position: relative; }
      </style>
      <ha-card header="${cfg.title}">
        <div class="map-wrapper">
          <div id="map"></div>
          <div id="loading-overlay">Loading map…</div>
        </div>
        <div id="status-bar">
          <span class="dot dot-outage"></span><span>Active outage</span>
          <span class="dot dot-planned"></span><span>Planned interruption</span>
          <span id="last-updated"></span>
          <button id="refresh-btn" title="Refresh now">↺ Refresh</button>
        </div>
      </ha-card>
    `;
    this.shadowRoot.getElementById("refresh-btn")
      .addEventListener("click", () => this._fetchAndRender());
  }

  // ── Map initialisation ───────────────────────────────────────────────────

  async _initMap() {
    try {
      loadStylesheet(LEAFLET_CSS);
      await loadScript(LEAFLET_JS);

      const cfg = this._config;
      const mapEl = this.shadowRoot.getElementById("map");

      const centreLat = cfg.latitude  ?? this._hass?.config?.latitude  ?? 46.8;
      const centreLon = cfg.longitude ?? this._hass?.config?.longitude ?? -71.2;

      // Leaflet needs a real DOM node — use the shadow root element
      const L = window.L;
      this._map = L.map(mapEl, { zoomControl: true }).setView([centreLat, centreLon], cfg.zoom);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(this._map);

      this._outageLayer  = L.layerGroup().addTo(this._map);
      this._plannedLayer = L.layerGroup().addTo(this._map);
      this._pinLayer     = L.layerGroup().addTo(this._map);
      this._radiusLayer  = L.layerGroup().addTo(this._map);

      // Layer control
      L.control.layers(null, {
        "🔴 Active outages":        this._outageLayer,
        "🟠 Planned interruptions": this._plannedLayer,
        "📍 Monitored locations":   this._pinLayer,
        "⭕ Search radius":          this._radiusLayer,
      }, { collapsed: false }).addTo(this._map);

      await this._fetchAndRender();

      // Auto-refresh every 15 min
      this._refreshTimer = setInterval(() => this._fetchAndRender(), 15 * 60 * 1000);

    } catch (err) {
      console.error("[HQ Map Card] Init error:", err);
      this._setOverlay("⚠ Failed to load map: " + err.message);
    }
  }

  // ── Data fetch + render ──────────────────────────────────────────────────

  async _fetchAndRender() {
    this._setOverlay("Fetching outage data…");
    try {
      const resp = await fetch(DATA_URL, {
        headers: { Authorization: `Bearer ${this._hass.auth.data.access_token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      this._render(data);
    } catch (err) {
      console.error("[HQ Map Card] Fetch error:", err);
      this._setOverlay("⚠ Could not load outage data: " + err.message);
    }
  }

  _render(data) {
    const L = window.L;
    const cfg = this._config;

    this._outageLayer.clearLayers();
    this._plannedLayer.clearLayers();
    this._pinLayer.clearLayers();
    this._radiusLayer.clearLayers();

    // ── Draw KML polygons ──────────────────────────────────────────────────
    const bisPolygons = parseKmlPolygons(data.bis_kml);
    const aipPolygons = parseKmlPolygons(data.aip_kml);

    bisPolygons.forEach(({ name, desc, coords }) => {
      L.polygon(coords, {
        color:       COLOR.outage.border,
        fillColor:   COLOR.outage.fill,
        fillOpacity: 0.35,
        weight:      1.5,
      }).bindPopup(`<b>🔴 Active Outage</b>${name ? `<br>${name}` : ""}${desc ? `<br><small>${desc}</small>` : ""}`)
        .addTo(this._outageLayer);
    });

    aipPolygons.forEach(({ name, desc, coords }) => {
      L.polygon(coords, {
        color:       COLOR.planned.border,
        fillColor:   COLOR.planned.fill,
        fillOpacity: 0.30,
        weight:      1.5,
        dashArray:   "6 4",
      }).bindPopup(`<b>🟠 Planned Interruption</b>${name ? `<br>${name}` : ""}${desc ? `<br><small>${desc}</small>` : ""}`)
        .addTo(this._plannedLayer);
    });

    // ── Draw outage point markers (fallback / extra info) ──────────────────
    (data.outages ?? []).forEach(o => {
      if (o.latitude == null || o.longitude == null) return;
      const popup = this._outagePopup(o);
      L.circleMarker([o.latitude, o.longitude], {
        radius: 6, color: COLOR.outage.border,
        fillColor: COLOR.outage.fill, fillOpacity: 0.9, weight: 1,
      }).bindPopup(popup).addTo(this._outageLayer);
    });

    (data.planned ?? []).forEach(p => {
      if (p.latitude == null || p.longitude == null) return;
      const popup = this._plannedPopup(p);
      L.circleMarker([p.latitude, p.longitude], {
        radius: 6, color: COLOR.planned.border,
        fillColor: COLOR.planned.fill, fillOpacity: 0.9, weight: 1,
        dashArray: "3 3",
      }).bindPopup(popup).addTo(this._plannedLayer);
    });

    // ── Draw configured location pins + radius circles ─────────────────────
    const locations = cfg.locations.length > 0
      ? cfg.locations
      : (cfg.latitude != null
          ? [{ name: "Monitored location", latitude: cfg.latitude, longitude: cfg.longitude, radius_km: null }]
          : []);

    locations.forEach(loc => {
      if (loc.latitude == null || loc.longitude == null) return;

      const icon = L.divIcon({
        className: "",
        html: `<div style="
          width:14px;height:14px;border-radius:50%;
          background:${COLOR.locationPin};border:2px solid white;
          box-shadow:0 1px 4px #0006;
        "></div>`,
        iconAnchor: [7, 7],
      });

      L.marker([loc.latitude, loc.longitude], { icon })
        .bindPopup(`<b>📍 ${loc.name ?? "Location"}</b>`)
        .addTo(this._pinLayer);

      if (loc.radius_km) {
        L.circle([loc.latitude, loc.longitude], {
          radius: loc.radius_km * 1000,
          color:       COLOR.radiusCircle.border,
          fillColor:   COLOR.radiusCircle.fill,
          fillOpacity: 1,
          weight:      1,
          dashArray:   "4 4",
        }).bindTooltip(`${loc.name ?? "Location"} — ${loc.radius_km} km radius`, { sticky: true })
          .addTo(this._radiusLayer);
      }
    });

    // ── Update status bar ──────────────────────────────────────────────────
    const lu = data.last_updated
      ? new Date(data.last_updated + "Z").toLocaleTimeString()
      : "";
    const el = this.shadowRoot.getElementById("last-updated");
    if (el) el.textContent = lu ? `Updated: ${lu}` : "";

    this._setOverlay(null);   // hide overlay

    // Auto-fit bounds if polygons exist and no explicit centre configured
    if (cfg.latitude == null && (bisPolygons.length + aipPolygons.length) > 0) {
      try {
        const allCoords = [...bisPolygons, ...aipPolygons].flatMap(p => p.coords);
        if (allCoords.length) this._map.fitBounds(allCoords, { padding: [20, 20] });
      } catch (_) {}
    }
  }

  // ── Popup builders ────────────────────────────────────────────────────────

  _outagePopup(o) {
    return `
      <b>🔴 Active Outage</b><br>
      <b>Customers:</b> ${o.customers_affected ?? "?"}<br>
      <b>Cause:</b> ${o.cause ?? "?"}<br>
      <b>Status:</b> ${o.status ?? "?"}<br>
      <b>Started:</b> ${o.start_time ?? "?"}<br>
      <b>Est. end:</b> ${o.estimated_end_time ?? "?"}
    `;
  }

  _plannedPopup(p) {
    return `
      <b>🟠 Planned Interruption</b><br>
      <b>Customers:</b> ${p.customers_affected ?? "?"}<br>
      <b>Cause:</b> ${p.cause ?? "?"}<br>
      <b>Status:</b> ${p.status ?? "?"}<br>
      <b>Start:</b> ${p.planned_start ?? "?"}<br>
      <b>End:</b> ${p.planned_end ?? "?"}
    `;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  _setOverlay(msg) {
    const el = this.shadowRoot.getElementById("loading-overlay");
    if (!el) return;
    if (msg) { el.textContent = msg; el.style.display = "flex"; }
    else      { el.style.display = "none"; }
  }

  // ── Lovelace card meta ────────────────────────────────────────────────────

  getCardSize() {
    return Math.ceil(this._config.height / 50) + 1;
  }

  static getConfigElement() {
    return null; // no visual editor for now
  }

  static getStubConfig() {
    return {
      type: "custom:hydroquebec-outages-map-card",
      title: "Hydro-Québec Outages",
      zoom: 10,
      height: 500,
    };
  }
}

customElements.define("hydroquebec-outages-map-card", HydroQuebecOutagesMapCard);

// Register with HACS / Lovelace card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type:        "hydroquebec-outages-map-card",
  name:        "Hydro-Québec Outages Map",
  description: "Map showing active outages and planned interruptions from Hydro-Québec.",
  preview:     false,
  documentationURL: "https://github.com/YOUR_USERNAME/hydroquebec-outages-ha",
});

console.info(
  `%c HYDRO-QUÉBEC OUTAGES MAP CARD %c v${CARD_VERSION} `,
  "background:#003da5;color:#fff;font-weight:700;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e53935;color:#fff;font-weight:700;padding:2px 6px;border-radius:0 3px 3px 0"
);
