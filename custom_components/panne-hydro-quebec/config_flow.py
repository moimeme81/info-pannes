import logging
import voluptuous as vol
from homeassistant import config_entries
from geopy.geocoders import ArcGIS
from .const import DOMAIN, CONF_ADDRESS, CONF_LAT, CONF_LON

# Ajout du système de log pour ne plus être à l'aveugle !
_LOGGER = logging.getLogger(__name__)

class HQTestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._search_results = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        
        if user_input is not None:
            has_data = any(val.strip() for val in user_input.values() if isinstance(val, str))
            
            if not has_data:
                errors["base"] = "empty_form"
            else:
                parts = []
                if user_input.get("civic_number"):
                    parts.append(str(user_input["civic_number"]))
                if user_input.get("street"):
                    parts.append(user_input["street"])
                if user_input.get("city"):
                    parts.append(user_input["city"])
                
                parts.append("QC")
                parts.append("Canada")
                
                if user_input.get("postal_code"):
                    parts.append(user_input["postal_code"])

                search_query = ", ".join(parts)

                def _geocode():
                    geolocator = ArcGIS(user_agent="ha_hq_test_mvp")
                    # On retire tout argument superflu. On laisse ArcGIS faire sa magie par défaut.
                    return geolocator.geocode(search_query, exactly_one=False)

                # LE BLOC DE SÉCURITÉ
                try:
                    results = await self.hass.async_add_executor_job(_geocode)

                    if results:
                        self._search_results = {
                            res.address: (res.latitude, res.longitude) 
                            for res in results
                        }
                        return await self.async_step_select()
                    else:
                        errors["base"] = "no_results"
                        
                except Exception as e:
                    # Si une erreur survient, on l'écrit DE FORCE dans les logs de Home Assistant
                    _LOGGER.error("Erreur critique lors du géocodage ArcGIS : %s", e)
                    # On affiche l'erreur générique dans l'interface au lieu de faire planter la fenêtre
                    errors["base"] = "unknown"

        schema = vol.Schema({
            vol.Optional("civic_number", default=""): str,
            vol.Optional("street", default=""): str,
            vol.Optional("city", default=""): str,
            vol.Optional("postal_code", default=""): str,
        })
        
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select(self, user_input=None):
        errors = {}

        if user_input is not None:
            selected_address = user_input["selected_address"]
            
            await self.async_set_unique_id(selected_address)
            self._abort_if_unique_id_configured()

            lat, lon = self._search_results[selected_address]

            return self.async_create_entry(
                title=selected_address, 
                data={
                    CONF_ADDRESS: selected_address,
                    CONF_LAT: lat,
                    CONF_LON: lon,
                }
            )

        address_list = list(self._search_results.keys())

        schema = vol.Schema({
            vol.Required("selected_address"): vol.In(address_list)
        })
        
        return self.async_show_form(step_id="select", data_schema=schema, errors=errors)
