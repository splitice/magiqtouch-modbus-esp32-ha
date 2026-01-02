from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.helpers import entity_platform, config_validation as cv
from .coordinator import MTMODCoordinator
import logging
import voluptuous as vol

DOMAIN = "magiqtouch_modbus"
PLATFORMS = ["climate", "switch"]
_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_SET_MAX_FAN_SPEED_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_ids,
    vol.Required("max_fan_speed"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
})

SERVICE_SET_TARGET_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_ids,
    vol.Required("target_temperature"): vol.All(vol.Coerce(float), vol.Range(min=0, max=35)),
})

async def async_setup(hass: HomeAssistant, config: dict):
    return True  # Only needed for legacy YAML config

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry):
    try:
        coordinator = MTMODCoordinator(hass, config)
        hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
        
        # Register services - only register once
        # Wrap in try-except to prevent service registration from breaking entity setup
        try:
            if not hass.services.has_service(DOMAIN, "set_thermostat_max_fan_speed"):
                # Register services
                async def handle_set_max_fan_speed(call: ServiceCall):
                    """Handle the set_thermostat_max_fan_speed service call."""
                    try:
                        entity_ids = call.data.get("entity_id")
                        max_fan_speed = call.data.get("max_fan_speed")
                        
                        # Ensure entity_ids is a list
                        if isinstance(entity_ids, str):
                            entity_ids = [entity_ids]
                        
                        # Get the entity component for switch domain
                        component = hass.data.get("entity_components", {}).get("switch")
                        if component is None:
                            _LOGGER.error("Switch component not found")
                            return
                        
                        # Find and update the entities
                        for entity_id in entity_ids:
                            entity = component.get_entity(entity_id)
                            if entity and hasattr(entity, 'set_max_fan_speed'):
                                entity.set_max_fan_speed(max_fan_speed)
                            else:
                                _LOGGER.error(f"Entity {entity_id} not found or doesn't support set_max_fan_speed")
                    except Exception as ex:
                        _LOGGER.error(f"Error in set_thermostat_max_fan_speed service: {ex}")
                
                async def handle_set_target_temperature(call: ServiceCall):
                    """Handle the set_thermostat_target_temperature service call."""
                    try:
                        entity_ids = call.data.get("entity_id")
                        target_temperature = call.data.get("target_temperature")
                        
                        # Ensure entity_ids is a list
                        if isinstance(entity_ids, str):
                            entity_ids = [entity_ids]
                        
                        # Get the entity component for switch domain
                        component = hass.data.get("entity_components", {}).get("switch")
                        if component is None:
                            _LOGGER.error("Switch component not found")
                            return
                        
                        # Find and update the entities
                        for entity_id in entity_ids:
                            entity = component.get_entity(entity_id)
                            if entity and hasattr(entity, 'set_target_temperature'):
                                entity.set_target_temperature(target_temperature)
                            else:
                                _LOGGER.error(f"Entity {entity_id} not found or doesn't support set_target_temperature")
                    except Exception as ex:
                        _LOGGER.error(f"Error in set_thermostat_target_temperature service: {ex}")
                
                # Register the services with schemas
                hass.services.async_register(
                    DOMAIN,
                    "set_thermostat_max_fan_speed",
                    handle_set_max_fan_speed,
                    schema=SERVICE_SET_MAX_FAN_SPEED_SCHEMA
                )
                
                hass.services.async_register(
                    DOMAIN,
                    "set_thermostat_target_temperature",
                    handle_set_target_temperature,
                    schema=SERVICE_SET_TARGET_TEMPERATURE_SCHEMA
                )
                _LOGGER.info("Registered magiqtouch_modbus services")
        except Exception as ex:
            _LOGGER.error(f"Error registering services (entities will still work): {ex}")
        
        return True
    except Exception as ex:
        _LOGGER.error(f"Error setting up {DOMAIN}: {ex}")
        raise

async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry):
    # Unregister services only if no other instances exist
    # Count remaining entries
    remaining_entries = [
        entry for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != config.entry_id
    ]
    
    if not remaining_entries:
        # Only remove services if this is the last entry
        hass.services.async_remove(DOMAIN, "set_thermostat_max_fan_speed")
        hass.services.async_remove(DOMAIN, "set_thermostat_target_temperature")
    
    return await hass.config_entries.async_unload_platforms(config, PLATFORMS)