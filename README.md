# Hydro-Québec Outages — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Monitor **Hydro-Québec power outages and planned service interruptions** near any location, directly inside Home Assistant. Data is sourced from the official [Hydro-Québec open data API](https://donnees.hydroquebec.com/explore/dataset/pannes-interruptions/information/) and refreshed every 15 minutes.

---

## Features

- 🔴 **Active outage detection** — binary sensor turns `on` when an outage is found within your configured radius
- 📅 **Planned interruption detection** — binary sensor turns `on` for upcoming scheduled work
- 📊 **Count sensors** — number of nearby outages, planned interruptions, and total customers affected
- 📍 **Multiple locations** — monitor your home, cottage, office, or any address
- 🇫🇷 **Bilingual UI** — English and French config flow
- ⚡ **Rich attributes** — distance, cause, status, estimated restoration time, affected customers, coordinates of all nearby events

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/moimeme81/info-pannes` as an **Integration**
3. Search for **Hydro-Québec Outages** and install
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/hydroquebec_outages` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Hydro-Québec Outages**
3. Enter:
   - **Location name** — a friendly label (e.g. "Home", "Chalet")
   - **Latitude / Longitude** — defaults to your HA home location
   - **Search radius (km)** — how far to look (default: 5 km)
4. Click **Submit**

### Adding more locations

Go to **Settings → Devices & Services → Hydro-Québec Outages → Configure** and choose **Add a location**.

---

## Entities Created Per Location

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.hydroquebec_<name>_active_outage` | Binary Sensor | `on` = active outage nearby |
| `binary_sensor.hydroquebec_<name>_planned_interruption` | Binary Sensor | `on` = planned interruption nearby |
| `sensor.hydroquebec_<name>_nearby_outages` | Sensor | Count of active outages in radius |
| `sensor.hydroquebec_<name>_nearby_planned_interruptions` | Sensor | Count of planned interruptions in radius |
| `sensor.hydroquebec_<name>_customers_affected_nearby` | Sensor | Total customers affected nearby |

### Attribute examples (active outage binary sensor)

```yaml
location_name: Home
monitored_latitude: 45.5017
monitored_longitude: -73.5673
radius_km: 5.0
outage_count: 2
closest_outage_distance_km: 1.3
closest_outage_customers_affected: 44
closest_outage_start_time: "2024-01-15 08:24:30"
closest_outage_estimated_end: "2024-01-15 12:15:00"
closest_outage_cause: "Equipment failure"
closest_outage_status: "Crew at work"
closest_outage_latitude: 45.4987
closest_outage_longitude: -73.5512
all_outages:
  - distance_km: 1.3
    customers_affected: 44
    ...
```

---

## Automation Examples

### Notify on new outage

```yaml
automation:
  - alias: "Notify on Hydro-Québec outage nearby"
    trigger:
      - platform: state
        entity_id: binary_sensor.hydroquebec_home_active_outage
        to: "on"
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "⚡ Power Outage Nearby"
          message: >
            {{ state_attr('binary_sensor.hydroquebec_home_active_outage', 'closest_outage_customers_affected') }}
            customers affected. Cause: {{ state_attr('binary_sensor.hydroquebec_home_active_outage', 'closest_outage_cause') }}.
            Est. restoration: {{ state_attr('binary_sensor.hydroquebec_home_active_outage', 'closest_outage_estimated_end') }}.
```

### Notify on planned interruption tomorrow

```yaml
automation:
  - alias: "Notify on planned interruption"
    trigger:
      - platform: state
        entity_id: binary_sensor.hydroquebec_home_planned_interruption
        to: "on"
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "🔧 Planned Power Interruption"
          message: >
            Scheduled work nearby. Start: {{ state_attr('binary_sensor.hydroquebec_home_planned_interruption', 'closest_planned_start') }},
            End: {{ state_attr('binary_sensor.hydroquebec_home_planned_interruption', 'closest_planned_end') }}.
```

### Dashboard Lovelace card

```yaml
type: entities
title: Hydro-Québec Status
entities:
  - entity: binary_sensor.hydroquebec_home_active_outage
    name: Active Outage
  - entity: binary_sensor.hydroquebec_home_planned_interruption
    name: Planned Interruption
  - entity: sensor.hydroquebec_home_nearby_outages
    name: Outages Nearby
  - entity: sensor.hydroquebec_home_customers_affected_nearby
    name: Customers Affected
```

---

## Data Source & Update Frequency

- **API**: [Hydro-Québec Open Data](https://donnees.hydroquebec.com/explore/dataset/pannes-interruptions/information/)
- **Update frequency**: Every 15 minutes (matching Hydro-Québec's own refresh rate)
- **Coverage**: All of Québec

