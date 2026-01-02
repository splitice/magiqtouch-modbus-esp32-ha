from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from .coordinator import MTMODCoordinator
import logging

DOMAIN = "magiqtouch_modbus"
PLATFORMS = ["climate", "switch"]
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True  # Only needed for legacy YAML config

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry):
    coordinator = MTMODCoordinator(hass, config)
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
    
    # Register services
    async def handle_set_max_fan_speed(call: ServiceCall):
        """Handle the set_thermostat_max_fan_speed service call."""
        entity_id = call.data.get("entity_id")
        max_fan_speed = call.data.get("max_fan_speed")
        
        # Find the entity
        for entry_id, switches in hass.data[DOMAIN].get('thermostat_switches', {}).items():
            for switch in switches:
                if switch.entity_id == entity_id:
                    switch.set_max_fan_speed(max_fan_speed)
                    return
        
        _LOGGER.error(f"Entity {entity_id} not found")
    
    async def handle_set_target_temperature(call: ServiceCall):
        """Handle the set_thermostat_target_temperature service call."""
        entity_id = call.data.get("entity_id")
        target_temperature = call.data.get("target_temperature")
        
        # Find the entity
        for entry_id, switches in hass.data[DOMAIN].get('thermostat_switches', {}).items():
            for switch in switches:
                if switch.entity_id == entity_id:
                    switch.set_target_temperature(target_temperature)
                    return
        
        _LOGGER.error(f"Entity {entity_id} not found")
    
    # Register the services
    hass.services.async_register(
        DOMAIN,
        "set_thermostat_max_fan_speed",
        handle_set_max_fan_speed
    )
    
    hass.services.async_register(
        DOMAIN,
        "set_thermostat_target_temperature",
        handle_set_target_temperature
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry):
    # Unregister services
    hass.services.async_remove(DOMAIN, "set_thermostat_max_fan_speed")
    hass.services.async_remove(DOMAIN, "set_thermostat_target_temperature")
    
    return await hass.config_entries.async_unload_platforms(config, PLATFORMS)