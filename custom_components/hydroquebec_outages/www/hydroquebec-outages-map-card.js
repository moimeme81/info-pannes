/**
 * Hydro-Québec Outages Map Card  v1.3.0
 *
 * Fixes vs 1.2:
 *  - Leaflet CSS injected into shadowRoot (not document.head) so styles apply
 *  - Title rendered as plain div — ha-card header="" attr caused overlap
 *  - invalidateSize() called via ResizeObserver + rAF after Leaflet init
 *  - Map div height set inline so Leaflet reads it before layout
 *  - loadStylesheet now accepts a target (shadowRoot or document.head)
 *
 * Lovelace YAML:
 *   type: custom:hydroquebec-outages-map-card
 *   title: "Hydro-Québec Outages"   # optional
 *   latitude: 45.5017               # map centre (optional, defaults to HA home)
 *   longitude: -73.5673
 *   zoom: 10
 *   height: 500
 *   locations:
 *     - name: Home
 *       latitude: 45.5017
 *       longitude: -73.5673
 *       radius_km: 5
 */

const CARD_VERSION = "1.3.0";
const DATA_URL     = "/api/hydroquebec_outages/data";
const LEAFLET_JS   = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS_URL = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";

const COLOR = {
  outage:       { fill: "#e53935", border: "#b71c1c" },
  planned:      { fill: "#fb8c00", border: "#e65100" },
  locationPin:  "#1565c0",
  radius:       { fill: "rgba(21,101,192,0.08)", border: "#1565c0" },
};

// ── KML parser ──────────────────────────────────────────────────────────────
function parseKmlPolygons(kmlText) {
  if (!kmlText) return [];
  const doc = new DOMParser().parseFromString(kmlText, "text/xml");
  const out = [];
  doc.querySelectorAll("Placemark").forEach(pm => {
    const name = pm.querySelector("name")?.textContent?.trim() ?? "";
    const desc = pm.querySelector("description")?.textContent?.trim() ?? "";
    pm.querySelectorAll("Polygon").forEach(poly => {
      // Handle both namespace variants of the coordinates element
      const coordEl =
        poly.querySelector("outerBoundaryIs coordinates") ||
        poly.querySelector("outerBoundaryIs LinearRing coordinates") ||
        poly.querySelector("coordinates");
      if (!coordEl) return;
      const coords = coordEl.textContent.trim()
        .split(/\s+/)
        .map(t => {
          const p = t.split(",");
          const lon = parseFloat(p[0]), lat = parseFloat(p[1]);
          return (isNaN(lat) || isNaN(lon)) ? null : [lat, lon];
        })
        .filter(Boolean);
      if (coords.length > 2) out.push({ name, desc, coords });
    });
  });
  return out;
}

// ── Script loader (idempotent) ───────────────────────────────────────────────
function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
    const s = Object.assign(document.createElement("script"),
      { src, onload: resolve, onerror: reject });
    document.head.appendChild(s);
  });
}

// ── Leaflet CSS must go into the shadow root, not document.head ─────────────
async function injectLeafletCss(shadowRoot) {
  // Fetch the CSS text and inject as a <style> so it scopes to the shadow DOM
  if (shadowRoot.querySelector("#leaflet-style")) return;
  try {
    const res  = await fetch(LEAFLET_CSS_URL);
    const text = await res.text();
    const style = document.createElement("style");
    style.id = "leaflet-style";
    // Leaflet uses .leaflet-container and children — no adjustment needed
    style.textContent = text;
    shadowRoot.insertBefore(style, shadowRoot.firstChild);
  } catch (e) {
    console.warn("[HQ Map] Could not inject Leaflet CSS:", e);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
class HydroQuebecOutagesMapCard extends HTMLElement {

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._map          = null;
    this._layers       = {};
    this._hass         = null;
    this._config       = {};
    this._mapReady     = false;
    this._pendingData  = null;
    this._refreshTimer = null;
  }

  // ── Lovelace API ────────────────────────────────────────────────────────────

  setConfig(cfg) {
    this._config = {
      title:     cfg.title     ?? "Hydro-Québec Outages",
      latitude:  cfg.latitude  ?? null,
      longitude: cfg.longitude ?? null,
      zoom:      cfg.zoom      ?? 10,
      height:    cfg.height    ?? 500,
      locations: cfg.locations ?? [],
    };
    this._buildSkeleton();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  disconnectedCallback() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
    if (this._map) { this._map.remove(); this._map = null; }
    this._mapReady = false;
  }

  getCardSize() { return Math.ceil(this._config.height / 50) + 2; }

  static getStubConfig() {
    return { type: "custom:hydroquebec-outages-map-card", title: "Hydro-Québec Outages" };
  }

  // ── DOM skeleton (no ha-card header attr — causes overlap) ──────────────────

  _buildSkeleton() {
    const { height, title } = this._config;
    this.shadowRoot.innerHTML = `
      <style>
        :host       { display: block; }
        ha-card     { display: flex; flex-direction: column; overflow: hidden; }
        .card-title {
          padding: 12px 16px 4px;
          font-size: 1.1em; font-weight: 500;
          color: var(--primary-text-color, #212121);
        }
        .map-wrap   { position: relative; flex: 1; }
        #map        { width: 100%; height: ${height}px; }
        #overlay    {
          position: absolute; inset: 0; z-index: 800;
          display: flex; align-items: center; justify-content: center;
          background: rgba(255,255,255,0.75);
          font-size: 13px; color: #444; pointer-events: none;
        }
        .status-bar {
          display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
          padding: 6px 12px; font-size: 12px;
          color: var(--secondary-text-color, #555);
          border-top: 1px solid var(--divider-color, #e0e0e0);
          background: var(--card-background-color, #fff);
        }
        .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
        .dot-out  { background: ${COLOR.outage.fill}; }
        .dot-plan { background: ${COLOR.planned.fill}; }
        #lu   { margin-left: auto; font-style: italic; }
        #btn  {
          cursor: pointer; padding: 2px 8px; font-size: 12px;
          border: 1px solid var(--divider-color, #ccc); border-radius: 4px;
          background: transparent; color: var(--primary-color, #03a9f4);
        }
      </style>
      <ha-card>
        ${title ? `<div class="card-title">${title}</div>` : ""}
        <div class="map-wrap">
          <div id="map"></div>
          <div id="overlay">Loading…</div>
        </div>
        <div class="status-bar">
          <span class="dot dot-out"></span><span>Active outage</span>
          <span class="dot dot-plan"></span><span>Planned interruption</span>
          <span id="lu"></span>
          <button id="btn">↺ Refresh</button>
        </div>
      </ha-card>`;

    this.shadowRoot.getElementById("btn")
      .addEventListener("click", () => this._fetchAndRender());
  }

  // ── Boot: inject Leaflet CSS into shadow root FIRST, then load JS ────────────

  async _boot() {
    try {
      // 1. Inject Leaflet CSS into the shadow root (critical fix)
      await injectLeafletCss(this.shadowRoot);
      // 2. Load Leaflet JS into the global scope (only once across all instances)
      await loadScript(LEAFLET_JS);
      // 3. Init the map
      await this._initMap();
    } catch (err) {
      console.error("[HQ Map Card] Boot error:", err);
      this._setOverlay("⚠ " + err.message);
    }
  }

  // ── Map init ────────────────────────────────────────────────────────────────

  async _initMap() {
    const L   = window.L;
    const cfg = this._config;
    const mapEl = this.shadowRoot.getElementById("map");

    const lat = cfg.latitude  ?? this._hass?.config?.latitude  ?? 46.8;
    const lon = cfg.longitude ?? this._hass?.config?.longitude ?? -71.2;

    this._map = L.map(mapEl, { zoomControl: true }).setView([lat, lon], cfg.zoom);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(this._map);

    const mk = (label) => L.layerGroup().addTo(this._map);
    this._layers = {
      outage:  mk(), planned: mk(),
      pins:    mk(), radius:  mk(),
    };

    L.control.layers(null, {
      "🔴 Active outages":        this._layers.outage,
      "🟠 Planned interruptions": this._layers.planned,
      "📍 Monitored locations":   this._layers.pins,
      "⭕ Search radius":          this._layers.radius,
    }, { collapsed: false }).addTo(this._map);

    // CRITICAL: tell Leaflet the map div has the right size now that layout settled
    // Use rAF + a small delay to guarantee the card is painted
    requestAnimationFrame(() => {
      setTimeout(() => {
        this._map?.invalidateSize();
      }, 100);
    });

    // Also watch for resize (sidebar open/close, panel switch)
    if (window.ResizeObserver) {
      this._resizeObs = new ResizeObserver(() => this._map?.invalidateSize());
      this._resizeObs.observe(mapEl);
    }

    this._mapReady = true;
    await this._fetchAndRender();
    this._refreshTimer = setInterval(() => this._fetchAndRender(), 15 * 60 * 1000);
  }

  // ── Fetch ────────────────────────────────────────────────────────────────────

  async _fetchAndRender() {
    this._setOverlay("Fetching outage data…");
    try {
      const resp = await fetch(DATA_URL, {
        headers: { Authorization: `Bearer ${this._hass.auth.data.access_token}` },
      });
      if (!resp.ok) throw new Error(`API returned HTTP ${resp.status}`);
      const data = await resp.json();
      this._render(data);
    } catch (err) {
      console.error("[HQ Map Card] Fetch error:", err);
      this._setOverlay("⚠ " + err.message);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  _render(data) {
    if (!this._mapReady) { this._pendingData = data; return; }
    const L   = window.L;
    const cfg = this._config;
    Object.values(this._layers).forEach(l => l.clearLayers());

    const bisPolys = parseKmlPolygons(data.bis_kml);
    const aipPolys = parseKmlPolygons(data.aip_kml);

    // ── Active outage polygons
    bisPolys.forEach(({ name, desc, coords }) => {
      L.polygon(coords, {
        color: COLOR.outage.border, fillColor: COLOR.outage.fill,
        fillOpacity: 0.35, weight: 1.5,
      }).bindPopup(`<b>🔴 Active Outage</b>${name ? `<br>${name}` : ""}${desc ? `<br><small>${desc}</small>` : ""}`)
        .addTo(this._layers.outage);
    });

    // ── Planned interruption polygons
    aipPolys.forEach(({ name, desc, coords }) => {
      L.polygon(coords, {
        color: COLOR.planned.border, fillColor: COLOR.planned.fill,
        fillOpacity: 0.30, weight: 1.5, dashArray: "6 4",
      }).bindPopup(`<b>🟠 Planned Interruption</b>${name ? `<br>${name}` : ""}${desc ? `<br><small>${desc}</small>` : ""}`)
        .addTo(this._layers.planned);
    });

    // ── Outage point markers (one per marker JSON record)
    (data.outages ?? []).forEach(o => {
      if (o.latitude == null) return;
      L.circleMarker([o.latitude, o.longitude], {
        radius: 7, color: COLOR.outage.border,
        fillColor: COLOR.outage.fill, fillOpacity: 0.9, weight: 1.5,
      }).bindPopup(this._outagePopup(o)).addTo(this._layers.outage);
    });

    // ── Planned point markers
    (data.planned ?? []).forEach(p => {
      if (p.latitude == null) return;
      L.circleMarker([p.latitude, p.longitude], {
        radius: 7, color: COLOR.planned.border,
        fillColor: COLOR.planned.fill, fillOpacity: 0.9, weight: 1.5,
      }).bindPopup(this._plannedPopup(p)).addTo(this._layers.planned);
    });

    // ── Location pins + radius rings
    const locations = cfg.locations.length
      ? cfg.locations
      : cfg.latitude != null
        ? [{ name: "Location", latitude: cfg.latitude, longitude: cfg.longitude }]
        : [];

    locations.forEach(loc => {
      if (loc.latitude == null) return;
      const pin = L.divIcon({
        className: "",
        html: `<div style="width:14px;height:14px;border-radius:50%;
          background:${COLOR.locationPin};border:2px solid #fff;
          box-shadow:0 1px 4px rgba(0,0,0,0.4)"></div>`,
        iconAnchor: [7, 7],
      });
      L.marker([loc.latitude, loc.longitude], { icon: pin })
        .bindPopup(`<b>📍 ${loc.name ?? "Location"}</b>`)
        .addTo(this._layers.pins);

      if (loc.radius_km) {
        L.circle([loc.latitude, loc.longitude], {
          radius: loc.radius_km * 1000,
          color: COLOR.radius.border, fillColor: COLOR.radius.fill,
          fillOpacity: 1, weight: 1.5, dashArray: "5 5",
        }).bindTooltip(`${loc.name ?? "Location"} — ${loc.radius_km} km`, { sticky: true })
          .addTo(this._layers.radius);
      }
    });

    // ── Status bar timestamp
    const lu = data.last_updated
      ? new Date(data.last_updated + "Z").toLocaleTimeString()
      : "";
    const luEl = this.shadowRoot.getElementById("lu");
    if (luEl) luEl.textContent = lu ? `Updated: ${lu}` : "";

    this._setOverlay(null);

    // Auto-fit if we have polygons and no explicit centre
    if (cfg.latitude == null && bisPolys.length + aipPolys.length > 0) {
      try {
        const all = [...bisPolys, ...aipPolys].flatMap(p => p.coords);
        if (all.length) this._map.fitBounds(all, { padding: [30, 30] });
      } catch (_) {}
    }

    // One more invalidateSize after render (layer control may have shifted layout)
    requestAnimationFrame(() => this._map?.invalidateSize());
  }

  // ── Popup helpers ─────────────────────────────────────────────────────────────

  _outagePopup(o) {
    return `<b>🔴 Active Outage</b><br>
      <b>Customers:</b> ${o.customers_affected ?? "?"}<br>
      <b>Cause:</b> ${o.cause ?? "?"}<br>
      <b>Status:</b> ${o.status ?? "?"}<br>
      <b>Started:</b> ${o.start_time ?? "?"}<br>
      <b>Est. end:</b> ${o.estimated_end_time ?? "?"}`;
  }

  _plannedPopup(p) {
    return `<b>🟠 Planned Interruption</b><br>
      <b>Customers:</b> ${p.customers_affected ?? "?"}<br>
      <b>Cause:</b> ${p.cause ?? "?"}<br>
      <b>Status:</b> ${p.status ?? "?"}<br>
      <b>Start:</b> ${p.planned_start ?? "?"}<br>
      <b>End:</b> ${p.planned_end ?? "?"}`;
  }

  // ── Overlay helper ────────────────────────────────────────────────────────────

  _setOverlay(msg) {
    const el = this.shadowRoot.getElementById("overlay");
    if (!el) return;
    el.textContent    = msg ?? "";
    el.style.display  = msg ? "flex" : "none";
  }
}

customElements.define("hydroquebec-outages-map-card", HydroQuebecOutagesMapCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hydroquebec-outages-map-card",
  name: "Hydro-Québec Outages Map",
  description: "Map of active outages and planned interruptions from Hydro-Québec open data.",
  preview: false,
});

console.info(
  `%c HYDRO-QUÉBEC OUTAGES MAP CARD %c v${CARD_VERSION} `,
  "background:#003da5;color:#fff;font-weight:700;padding:2px 6px;border-radius:3px 0 0 3px",
  "background:#e53935;color:#fff;font-weight:700;padding:2px 6px;border-radius:0 3px 3px 0"
);
