import logging
import json
import io
import zipfile
import xml.etree.ElementTree as ET
from shapely.geometry import Point, Polygon as ShapePolygon

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

# Assure-toi que URL_KMZ est bien dans ton fichier const.py !
from .const import DOMAIN, CONF_ADDRESS, CONF_LAT, CONF_LON, URL_VERSION, URL_MARKERS, URL_KMZ, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# --- DICTIONNAIRES DE DÉCODAGE ---
STATUS_MAP = {
    "A": "Travaux assignés",
    "L": "Équipe au travail",
    "R": "Équipe en route",
    "E": "En évaluation"
}

TYPE_MAP = {
    "P": "Panne",
    "I": "Interruption planifiée"
}

def decode_cause(code):
    """Traduit le code numérique en texte lisible."""
    code_str = str(code)
    if code_str in ["11", "12", "13", "14", "15", "58", "70", "72", "73", "74", "79", "defaut"]:
        return "Bris d'équipement"
    elif code_str in ["21", "22", "24", "25", "26"]:
        return "Conditions météorologiques"
    elif code_str in ["31", "32", "33", "34", "41", "42", "43", "44", "54", "55", "56", "57"]:
        return "Accident ou incident"
    elif code_str == "51":
        return "Dommages dus à la végétation"
    elif code_str in ["52", "53"]:
        return "Dommages dus à un animal"
    return f"Code inconnu ({code_str})"


# --- FONCTION D'INITIALISATION OBLIGATOIRE ---
async def async_setup_entry(hass, entry, async_add_entities):
    address = entry.data[CONF_ADDRESS]
    lat = entry.data[CONF_LAT]
    lon = entry.data[CONF_LON]
    session = async_get_clientsession(hass)

    coordinator = HQDataUpdateCoordinator(hass, session, address, lat, lon)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        HQStatusSensor(coordinator, entry.entry_id, address, lat, lon),
        HQTotalOutagesSensor(coordinator, entry.entry_id, address),
        HQTotalCustomersSensor(coordinator, entry.entry_id, address),
        HQLocalCustomersSensor(coordinator, entry.entry_id, address),
        HQTypeSensor(coordinator, entry.entry_id, address),
        HQCauseSensor(coordinator, entry.entry_id, address),
        HQWorkStatusSensor(coordinator, entry.entry_id, address),
        HQRestorationSensor(coordinator, entry.entry_id, address)
    ], True)


# --- LE COORDINATEUR (Avec logique KMZ/MultiPolygon GeoJSON) ---
class HQDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, session, address, lat, lon):
        super().__init__(hass, _LOGGER, name=f"HQ_{address}", update_interval=SCAN_INTERVAL)
        self.session = session
        self.lat = lat
        self.lon = lon

    async def _async_update_data(self):
        try:
            async with self.session.get(URL_VERSION) as r:
                version = json.loads(await r.text())
            
            async with self.session.get(URL_MARKERS.format(version=version)) as r:
                data = await r.json(content_type=None)
            
            pannes = data.get("pannes", [])
            is_affected = False
            total_clients_qc = 0
            details_panne_locale = {}
            user_point = Point(self.lon, self.lat) # Longitude en premier pour Shapely

            for p in pannes:
                clients = p[0] if len(p) > 0 else 0
                total_clients_qc += clients

                if len(p) > 4:
                    try:
                        coords = json.loads(p[4])
                        # Vérification rapide par proximité
                        if abs(coords[1] - self.lat) < 0.01 and abs(coords[0] - self.lon) < 0.01:
                            is_affected = True
                            
                            details_panne_locale = {
                                "clients_touches": clients,
                                "date_debut": p[1] if len(p) > 1 else "Inconnu",
                                "retablissement": p[2] if len(p) > 2 else "En évaluation",
                                "type": TYPE_MAP.get(p[3], "Inconnu") if len(p) > 3 else "Inconnu",
                                "statut_travaux": STATUS_MAP.get(p[5], "Non assigné") if len(p) > 5 else "Non assigné",
                                "cause": decode_cause(p[7]) if len(p) > 7 else "En évaluation",
                                "polygon_geojson": None # Sera rempli par le KMZ si trouvé
                            }
                    except Exception:
                        continue

            # SI UNE PANNE EST DÉTECTÉE, ON CHERCHE LE POLYGONE KMZ COMPLET
            if is_affected:
                try:
                    async with self.session.get(URL_KMZ.format(version=version)) as r:
                        kmz_content = await r.read()
                    
                    with zipfile.ZipFile(io.BytesIO(kmz_content)) as z:
                        kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                        with z.open(kml_filename) as f:
                            tree = ET.parse(f)
                            root = tree.getroot()
                    
                    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                    
                    for placemark in root.findall('.//kml:Placemark', ns):
                        all_polys = []
                        
                        # On récupère TOUS les fragments de la zone (MultiGeometry)
                        for coord_text in placemark.findall('.//kml:coordinates', ns):
                            raw_coords = coord_text.text.strip().split()
                            poly_points = []
                            for c in raw_coords:
                                lon_val, lat_val, _ = map(float, c.split(','))
                                poly_points.append((lon_val, lat_val))
                            
                            if len(poly_points) >= 3:
                                all_polys.append(poly_points)
                        
                        # Vérifie si le point de l'utilisateur est dans l'un des fragments
                        is_inside = False
                        for p_points in all_polys:
                            if ShapePolygon(p_points).contains(user_point):
                                is_inside = True
                                break
                        
                        if is_inside:
                            # Formatage en GeoJSON valide (Polygon ou MultiPolygon)
                            if len(all_polys) == 1:
                                details_panne_locale["polygon_geojson"] = {
                                    "type": "Polygon",
                                    "coordinates": [all_polys[0]]
                                }
                            else:
                                details_panne_locale["polygon_geojson"] = {
                                    "type": "MultiPolygon",
                                    "coordinates": [[p] for p in all_polys]
                                }
                            break
                except Exception as e:
                    _LOGGER.warning("Impossible de récupérer le polygone KMZ: %s", e)

            return {
                "status": "Panne" if is_affected else "En service",
                "total_pannes": len(pannes),
                "total_clients": total_clients_qc,
                "version": version,
                "details": details_panne_locale
            }
        except Exception as e:
            _LOGGER.error("Erreur Coordinator HQ: %s", e)
            return {"status": "Erreur", "total_pannes": 0, "total_clients": 0, "version": "N/A", "details": {}}


# --- CLASSE DE BASE ---
class HQBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry_id, address):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._address = address

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._address,
            manufacturer="Hydro-Québec",
            model="Surveillance réseau"
        )


# ==========================================
# LES CAPTEURS
# ==========================================

class HQStatusSensor(HQBaseSensor):
    def __init__(self, coordinator, entry_id, address, lat, lon):
        super().__init__(coordinator, entry_id, address)
        self._lat = lat
        self._lon = lon

    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_status"
    
    @property
    def name(self): return "Statut"
    
    @property
    def native_value(self): return self.coordinator.data["status"]
    
    @property
    def icon(self): return "mdi:home-lightning-bolt" if self.native_value == "En service" else "mdi:power-plug-off"

    @property
    def extra_state_attributes(self):
        details = self.coordinator.data.get("details", {})
        attr = {
            "latitude": self._lat,
            "longitude": self._lon,
            "derniere_mise_a_jour": self.coordinator.data.get("version")
        }
        # Injecte le polygone dans les attributs s'il a été trouvé par le KMZ
        if details.get("polygon_geojson"):
            attr["zone_geographique"] = details["polygon_geojson"]
            
        return attr

class HQTotalOutagesSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_total_pannes"
    @property
    def name(self): return "Total pannes (QC)"
    @property
    def native_value(self): return self.coordinator.data["total_pannes"]
    @property
    def native_unit_of_measurement(self): return "pannes"
    @property
    def icon(self): return "mdi:flash-alert"

class HQTotalCustomersSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_total_clients"
    @property
    def name(self): return "Clients affectés (QC)"
    @property
    def native_value(self): return self.coordinator.data["total_clients"]
    @property
    def native_unit_of_measurement(self): return "clients"
    @property
    def icon(self): return "mdi:account-group"

class HQLocalCustomersSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_local_clients"
    @property
    def name(self): return "Clients affectés (Local)"
    @property
    def native_value(self): return self.coordinator.data["details"].get("clients_touches", 0)
    @property
    def native_unit_of_measurement(self): return "clients"
    @property
    def icon(self): return "mdi:account-alert" if self.native_value > 0 else "mdi:account-check"

class HQTypeSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_type"
    @property
    def name(self): return "Type de panne"
    @property
    def native_value(self): return self.coordinator.data["details"].get("type", "Aucune")
    @property
    def icon(self): return "mdi:alert-decagram-outline"

class HQCauseSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_cause"
    @property
    def name(self): return "Cause de la panne"
    @property
    def native_value(self): return self.coordinator.data["details"].get("cause", "Aucune")
    @property
    def icon(self): return "mdi:information-outline"

class HQWorkStatusSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_work_status"
    @property
    def name(self): return "Statut des travaux"
    @property
    def native_value(self): return self.coordinator.data["details"].get("statut_travaux", "Aucune panne")
    @property
    def icon(self):
        val = self.native_value
        if val == "Équipe en route": return "mdi:truck-fast"
        if val == "Équipe au travail": return "mdi:hard-hat"
        return "mdi:tools"

class HQRestorationSensor(HQBaseSensor):
    @property
    def unique_id(self): return f"{DOMAIN}_{self._entry_id}_restauration"
    @property
    def name(self): return "Rétablissement prévu"
    @property
    def native_value(self): return self.coordinator.data["details"].get("retablissement", "N/A")
    @property
    def icon(self): return "mdi:clock-outline"
