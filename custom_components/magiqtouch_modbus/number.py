import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import UnitOfTemperature

DOMAIN = "magiqtouch_modbus"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermostat configuration number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    zone_count = config_entry.data["Zones"]
    evap_enabled = config_entry.data["Evaporative Unit"]
    heater_enabled = config_entry.data["Heater Unit"]
    
    numbers = []
    
    # Create configuration numbers for each zone with thermostat
    for zone_index in range(zone_count):
        zone = zone_index + 1
        
        # Add cooling configuration if evaporative unit is enabled and it's zone 1
        if evap_enabled and zone == 1:
            numbers.append(ThermostatMaxFanSpeedNumber(
                coordinator,
                config_entry,
                zone,
                "cooling"
            ))
            numbers.append(ThermostatTargetTemperatureNumber(
                coordinator,
                config_entry,
                zone,
                "cooling"
            ))
        
        # Add heating configuration if heater is enabled
        if heater_enabled:
            numbers.append(ThermostatMaxFanSpeedNumber(
                coordinator,
                config_entry,
                zone,
                "heating"
            ))
            numbers.append(ThermostatTargetTemperatureNumber(
                coordinator,
                config_entry,
                zone,
                "heating"
            ))
    
    # Store numbers reference for switch access
    if 'thermostat_numbers' not in hass.data[DOMAIN]:
        hass.data[DOMAIN]['thermostat_numbers'] = {}
    hass.data[DOMAIN]['thermostat_numbers'][config_entry.entry_id] = numbers
    
    async_add_entities(numbers)


class ThermostatMaxFanSpeedNumber(CoordinatorEntity, NumberEntity):
    """Number entity for thermostat max fan speed configuration."""
    
    def __init__(self, coordinator, config_entry, zone, mode):
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self.zone = zone
        self._mode = mode  # "cooling" or "heating"
        self._attr_unique_id = f"magiqtouch_thermostat_{mode}_{zone}_max_fan_speed"
        self._attr_name = f"Zone {zone} Thermostat {mode.capitalize()} Max Fan Speed"
        self.api_url = config_entry.data["HVAC URL"]
        
        # Number configuration
        self._attr_native_min_value = 1
        self._attr_native_max_value = 10
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 10  # Default to maximum
    
    @property
    def unique_id(self):
        """Return unique ID."""
        return self._attr_unique_id
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.api_url)},
            name="Magiqtouch ESP32 Controller",
            model="Modbus ESP32 Interface",
            configuration_url=self.api_url
        )
    
    @property
    def icon(self):
        """Return the icon."""
        return "mdi:fan"
    
    @property
    def native_value(self):
        """Return the current value."""
        return self._attr_native_value
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        self._attr_native_value = int(value)
        
        # Find and update the corresponding thermostat switch
        switches = self.hass.data[DOMAIN].get('thermostat_switches', {}).get(self._config_entry.entry_id, [])
        for switch in switches:
            if switch.zone == self.zone and switch._mode == self._mode:
                switch.set_max_fan_speed(int(value))
                break
        
        self.async_write_ha_state()


class ThermostatTargetTemperatureNumber(CoordinatorEntity, NumberEntity):
    """Number entity for thermostat target temperature configuration."""
    
    def __init__(self, coordinator, config_entry, zone, mode):
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self.zone = zone
        self._mode = mode  # "cooling" or "heating"
        self._attr_unique_id = f"magiqtouch_thermostat_{mode}_{zone}_target_temp"
        self._attr_name = f"Zone {zone} Thermostat {mode.capitalize()} Target Temperature"
        self.api_url = config_entry.data["HVAC URL"]
        
        # Number configuration
        self._attr_native_min_value = 0
        self._attr_native_max_value = 35
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_native_value = 22  # Default to 22°C
    
    @property
    def unique_id(self):
        """Return unique ID."""
        return self._attr_unique_id
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.api_url)},
            name="Magiqtouch ESP32 Controller",
            model="Modbus ESP32 Interface",
            configuration_url=self.api_url
        )
    
    @property
    def icon(self):
        """Return the icon."""
        if self._mode == "cooling":
            return "mdi:thermometer-minus"
        else:
            return "mdi:thermometer-plus"
    
    @property
    def native_value(self):
        """Return the current value."""
        return self._attr_native_value
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        self._attr_native_value = value
        
        # Find and update the corresponding thermostat switch
        switches = self.hass.data[DOMAIN].get('thermostat_switches', {}).get(self._config_entry.entry_id, [])
        for switch in switches:
            if switch.zone == self.zone and switch._mode == self._mode:
                switch.set_target_temperature(value)
                break
        
        self.async_write_ha_state()
