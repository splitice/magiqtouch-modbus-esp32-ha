import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import callback
import asyncio
from datetime import datetime, timedelta

DOMAIN = "magiqtouch_modbus"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the thermostat switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    zone_count = config_entry.data["Zones"]
    evap_enabled = config_entry.data["Evaporative Unit"]
    heater_enabled = config_entry.data["Heater Unit"]
    
    switches = []
    
    # Create thermostat switches for each zone
    for zone_index in range(zone_count):
        zone = zone_index + 1
        
        # Add cooling thermostat switch if evaporative unit is enabled and it's zone 1
        if evap_enabled and zone == 1:
            switches.append(ThermostatSwitch(
                coordinator,
                config_entry,
                zone,
                "cooling"
            ))
        
        # Add heating thermostat switch if heater is enabled
        if heater_enabled:
            switches.append(ThermostatSwitch(
                coordinator,
                config_entry,
                zone,
                "heating"
            ))
    
    # Store switches reference for service calls
    if not hasattr(hass.data[DOMAIN], 'thermostat_switches'):
        hass.data[DOMAIN]['thermostat_switches'] = {}
    hass.data[DOMAIN]['thermostat_switches'][config_entry.entry_id] = switches
    
    async_add_entities(switches)


class ThermostatSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Thermostat Switch."""
    
    def __init__(self, coordinator, config_entry, zone, mode):
        """Initialize the thermostat switch."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self.zone = zone
        self._mode = mode  # "cooling" or "heating"
        self._attr_unique_id = f"magiqtouch_thermostat_{mode}_{zone}"
        self._attr_name = f"Zone {zone} Thermostat {mode.capitalize()}"
        self.api_url = config_entry.data["HVAC URL"]
        
        # State tracking
        self._is_on = False
        self._target_temp = None
        self._max_fan_speed = None
        self._saved_fan_speed = None
        self._rampdown_task = None
        self._rampdown_start_time = None
        
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
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on
    
    @property
    def icon(self):
        """Return the icon for this switch."""
        if self._mode == "cooling":
            return "mdi:snowflake" if self._is_on else "mdi:snowflake-off"
        else:  # heating
            return "mdi:fire" if self._is_on else "mdi:fire-off"
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "zone": self.zone,
            "mode": self._mode,
        }
        # Always show max_fan_speed so users can see the configuration
        if self._max_fan_speed is not None:
            attrs["max_fan_speed"] = self._max_fan_speed
        else:
            attrs["max_fan_speed"] = 10  # Show default
            
        if self._is_on:
            if self._target_temp is not None:
                attrs["target_temperature"] = self._target_temp
            if self._saved_fan_speed is not None:
                attrs["saved_fan_speed"] = self._saved_fan_speed
        return attrs
    
    async def async_turn_on(self, **kwargs):
        """Turn the thermostat switch on."""
        if self._is_on:
            return
            
        # Get current state from coordinator
        if self.coordinator.data is None:
            _LOGGER.warning(f"Cannot turn on thermostat {self._mode} for zone {self.zone}: no data")
            return
        
        # Save current fan speed if in manual mode
        if self._mode == "cooling":
            current_fan_speed = self.coordinator.data.get('evap_fanspeed')
            if current_fan_speed and current_fan_speed > 0:
                self._saved_fan_speed = current_fan_speed
                _LOGGER.info(f"Saved fan speed {self._saved_fan_speed} for zone {self.zone}")
        
        # Get target temperature from climate entity
        if self.zone == 1:
            self._target_temp = self.coordinator.data.get('target_temp')
        else:
            self._target_temp = self.coordinator.data.get(f'target_temp_zone{self.zone}')
        
        # Default max fan speed if not set
        if self._max_fan_speed is None:
            self._max_fan_speed = 10  # Default to maximum
        
        self._is_on = True
        
        # Start thermostat control
        await self._start_thermostat_control()
        
        self.async_write_ha_state()
        
        _LOGGER.info(f"Thermostat {self._mode} turned on for zone {self.zone}")
    
    async def async_turn_off(self, **kwargs):
        """Turn the thermostat switch off."""
        if not self._is_on:
            return
            
        self._is_on = False
        
        # Cancel any ongoing rampdown
        if self._rampdown_task:
            self._rampdown_task.cancel()
            self._rampdown_task = None
            self._rampdown_start_time = None
        
        # Restore saved fan speed if available
        if self._saved_fan_speed is not None and self._mode == "cooling":
            from .climate import MagiqtouchZones
            # Find the climate entity for this zone and restore fan speed
            for climate_entity in MagiqtouchZones:
                if climate_entity.zone == self.zone:
                    await climate_entity.send_hvac_command(f"fanspeed={self._saved_fan_speed}")
                    _LOGGER.info(f"Restored fan speed {self._saved_fan_speed} for zone {self.zone}")
                    break
        
        self.async_write_ha_state()
        
        _LOGGER.info(f"Thermostat {self._mode} turned off for zone {self.zone}")
    
    async def _start_thermostat_control(self):
        """Start thermostat control loop."""
        from .climate import MagiqtouchZones
        
        # Find the climate entity for this zone
        climate_entity = None
        for entity in MagiqtouchZones:
            if entity.zone == self.zone:
                climate_entity = entity
                break
        
        if climate_entity is None:
            _LOGGER.error(f"Could not find climate entity for zone {self.zone}")
            return
        
        # Set the appropriate mode and fan speed
        if self._mode == "cooling":
            # Switch to cooling mode (manual fan control for thermostat)
            await climate_entity.send_hvac_command("mode=2")  # Mode 2 is cooler with manual fan
            # Set initial fan speed to max
            if self._max_fan_speed:
                await climate_entity.send_hvac_command(f"fanspeed={self._max_fan_speed}")
            _LOGGER.info(f"Started cooling thermostat for zone {self.zone} with max fan speed {self._max_fan_speed}")
        elif self._mode == "heating":
            # Switch to heating mode
            await climate_entity.send_hvac_command("mode=4")  # Mode 4 is heater mode
            await climate_entity.send_hvac_command(f"zone{self.zone}=on")
            _LOGGER.info(f"Started heating thermostat for zone {self.zone}")
        
        # Ensure system is powered on
        await climate_entity.send_hvac_command("power=on")
    
    async def check_temperature_and_rampdown(self):
        """Check temperature and start rampdown if target reached."""
        if not self._is_on:
            return
        
        if self.coordinator.data is None:
            return
        
        # Only for cooling mode
        if self._mode != "cooling":
            return
        
        # Get current temperature
        temp_key = f"zone{self.zone}_temp_sensor"
        current_temp = self.coordinator.data.get(temp_key)
        
        if current_temp is None or current_temp == 157:  # 157 is default when not reported
            return
        
        # Check if target temperature is reached
        if self._target_temp is not None and current_temp <= self._target_temp:
            # Start rampdown if not already running
            if self._rampdown_task is None:
                self._rampdown_task = asyncio.create_task(self._execute_rampdown())
                _LOGGER.info(f"Starting cooling rampdown for zone {self.zone} (current: {current_temp}°C, target: {self._target_temp}°C)")
        elif self._target_temp is not None and current_temp > self._target_temp:
            # Temperature is above target, cancel rampdown and restore max fan speed
            if self._rampdown_task is not None:
                _LOGGER.info(f"Temperature rose above target, cancelling rampdown and restoring max fan speed for zone {self.zone}")
                self._rampdown_task.cancel()
                self._rampdown_task = None
                self._rampdown_start_time = None
                
                # Restore max fan speed
                from .climate import MagiqtouchZones
                for entity in MagiqtouchZones:
                    if entity.zone == self.zone:
                        await entity.send_hvac_command(f"fanspeed={self._max_fan_speed}")
                        break
    
    async def _execute_rampdown(self):
        """Execute the cooling rampdown over 5 minutes in 3 steps."""
        try:
            if self._max_fan_speed is None:
                self._max_fan_speed = 10
            
            from .climate import MagiqtouchZones
            climate_entity = None
            for entity in MagiqtouchZones:
                if entity.zone == self.zone:
                    climate_entity = entity
                    break
            
            if climate_entity is None:
                _LOGGER.error(f"Could not find climate entity for zone {self.zone}")
                return
            
            self._rampdown_start_time = datetime.now()
            
            # Step 1: Ramp to half speed (wait ~100 seconds)
            half_speed = max(1, self._max_fan_speed // 2)
            _LOGGER.info(f"Rampdown step 1: Setting fan to {half_speed}")
            await climate_entity.send_hvac_command(f"fanspeed={half_speed}")
            await asyncio.sleep(100)
            
            if not self._is_on:
                return
            
            # Step 2: Ramp to speed 1 (wait ~100 seconds)
            _LOGGER.info(f"Rampdown step 2: Setting fan to 1")
            await climate_entity.send_hvac_command("fanspeed=1")
            await asyncio.sleep(100)
            
            if not self._is_on:
                return
            
            # Step 3: Turn off (wait ~100 seconds)
            _LOGGER.info(f"Rampdown step 3: Turning off")
            await climate_entity.send_hvac_command("power=off")
            
            # Clear rampdown task
            self._rampdown_task = None
            self._rampdown_start_time = None
            
        except asyncio.CancelledError:
            _LOGGER.info(f"Rampdown cancelled for zone {self.zone}")
            self._rampdown_task = None
            self._rampdown_start_time = None
        except Exception as e:
            _LOGGER.error(f"Error during rampdown for zone {self.zone}: {e}")
            self._rampdown_task = None
            self._rampdown_start_time = None
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check temperature and trigger rampdown if needed
        if self._is_on and self._mode == "cooling":
            asyncio.create_task(self.check_temperature_and_rampdown())
        
        self.async_write_ha_state()
    
    def set_max_fan_speed(self, speed: int):
        """Set the maximum fan speed for thermostat mode."""
        if speed < 1 or speed > 10:
            _LOGGER.error(f"Invalid fan speed {speed}. Must be between 1 and 10.")
            return
        self._max_fan_speed = speed
        _LOGGER.info(f"Set max fan speed to {speed} for zone {self.zone} {self._mode}")
        self.async_write_ha_state()
    
    def set_target_temperature(self, temp: float):
        """Set the target temperature for thermostat mode."""
        self._target_temp = temp
        _LOGGER.info(f"Set target temperature to {temp} for zone {self.zone} {self._mode}")
        self.async_write_ha_state()
