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
from .const import DOMAIN, CONF_ADDRESS, CONF_LAT, CONF_LON, URL_VERSION, URL_MARKERS, URL_KMZ, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# [Dictionnaires de décodage STATUS_MAP, CAUSE_MAP, etc. - Inchangés]

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
            details_panne_locale = {}
            user_point = Point(self.lon, self.lat) # Attention: Longitude en premier pour Shapely

            for p in pannes:
                if len(p) > 4:
                    try:
                        coords = json.loads(p[4])
                        # Vérification rapide par proximité (1km)
                        if abs(coords[1] - self.lat) < 0.01 and abs(coords[0] - self.lon) < 0.01:
                            is_affected = True
                            details_panne_locale = {
                                "clients_touches": p[0],
                                "date_debut": p[1],
                                "retablissement": p[2],
                                "type": p[3],
                                "statut_travaux": p[5],
                                "cause": p[7],
                                "polygon_geojson": None # Sera rempli si trouvé
                            }
                    except: continue

            # SI UNE PANNE EST DÉTECTÉE, ON CHERCHE LE POLYGONE
            if is_affected:
                try:
                    async with self.session.get(URL_KMZ.format(version=version)) as r:
                        kmz_content = await r.read()
                    
                    with zipfile.ZipFile(io.BytesIO(kmz_content)) as z:
                        # Le fichier KML est généralement le seul fichier .kml dans le zip
                        kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                        with z.open(kml_filename) as f:
                            tree = ET.parse(f)
                            root = tree.getroot()
                    
                    # Namespace KML (nécessaire pour parser l'XML)
                    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                    
                    # On parcourt les Placemarks pour trouver celui qui contient notre point
                    for placemark in root.findall('.//kml:Placemark', ns):
                        coord_text = placemark.find('.//kml:coordinates', ns)
                        if coord_text is not None:
                            # Extraction et conversion des coordonnées KML (lon,lat,alt)
                            raw_coords = coord_text.text.strip().split()
                            poly_points = []
                            for c in raw_coords:
                                lon_val, lat_val, _ = map(float, c.split(','))
                                poly_points.append((lon_val, lat_val))
                            
                            # Test de collision
                            if len(poly_points) >= 3:
                                poly_shape = ShapePolygon(poly_points)
                                if poly_shape.contains(user_point):
                                    # On a trouvé le bon polygone ! On le stocke en format compatible Map
                                    details_panne_locale["polygon_geojson"] = poly_points
                                    break
                except Exception as e:
                    _LOGGER.warning("Impossible de récupérer le polygone: %s", e)

            return {
                "status": "Panne" if is_affected else "En service",
                "total_pannes": len(pannes),
                "total_clients": sum(p[0] for p in pannes if len(p) > 0),
                "version": version,
                "details": details_panne_locale
            }
        except Exception as e:
            _LOGGER.error("Erreur Coordinator: %s", e)
            return {"status": "Erreur", "details": {}}

# --- CAPTEUR DE STATUT MIS À JOUR ---
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
    def extra_state_attributes(self):
        details = self.coordinator.data.get("details", {})
        attr = {
            "latitude": self._lat,
            "longitude": self._lon,
            "derniere_mise_a_jour": self.coordinator.data.get("version")
        }
        # Si un polygone a été trouvé, on l'ajoute aux attributs
        if details.get("polygon_geojson"):
            attr["zone_geographique"] = details["polygon_geojson"]
            
        return attr

# [Reste des capteurs HQTotalOutagesSensor, etc. - Inchangés]
