# Home Assistant Integration for the MagiqTouch Modbus ESP32 Interface

## Hardware Requirements
ESP Modbus Interface: https://github.com/mrhteriyaki/magiqtouch-modbus-esp32

## Installation
Add this repo to HACS: https://github.com/mrhteriyaki/magiqtouch-modbus-esp32-ha
Or manual install by copying custom_components folder.


## Configuration:

![config](Images/config.PNG)  

1. Set the URL of the HVAC ESP32 Module eg: http://192.168.20.112  
2. Set your zone count.  
3. Tick Evap / Heater modules for your supported setup.  

Dashboard display:  
![dash](Images/dash.PNG)

Details showing fan speed selection and option to use temperature mode:  
![z1detail](Images/z1detail.PNG)  

![z1detailfan](Images/fan.png)

Dashboard with Logbook:
![dashboardwithlog](Images/Dashboard_Log.PNG)

## Thermostat Control

The integration now includes thermostat switches for each zone to provide automatic temperature-based control:

### Features

- **Thermostat Cooling Switch**: Enables automatic cooling control for Zone 1 (if evaporative unit is enabled)
- **Thermostat Heating Switch**: Enables automatic heating control for each zone (if heater is enabled)
- **Configuration Number Entities**: Each thermostat has two number entities for easy configuration:
  - **Max Fan Speed**: Set the maximum fan speed (1-10) for thermostat mode
  - **Target Temperature**: Set the target temperature in Celsius (0-35°C)

### Behavior

When a thermostat switch is enabled:

1. **Cooling Mode**: 
   - Saves your current manual fan speed
   - Switches to cooling mode with the configured maximum fan speed
   - Monitors temperature continuously
   - When target temperature is reached, performs a "nice" ramp-down over 5 minutes in 3 steps:
     - Step 1: Reduce to half of max fan speed (~100 seconds)
     - Step 2: Reduce to speed 1 (~100 seconds)
     - Step 3: Turn off (~100 seconds)
   - If temperature rises above target during rampdown, cancels rampdown and restores max fan speed

2. **Heating Mode**:
   - Switches to heating mode and enables the zone

When disabled, the thermostat switch restores your previously saved manual fan speed.

### Configuration

Configuration is done through dedicated number entities for each thermostat:

- **Max Fan Speed Number**: Slider control (1-10) to set the maximum fan speed when thermostat is active
- **Target Temperature Number**: Slider control (0-35°C) to set the temperature threshold for ramp-down

These configuration entities appear alongside the thermostat switches in Home Assistant and can be:
- Adjusted through the UI
- Set via automations
- Controlled through dashboards

### Attributes

Each thermostat switch exposes the following attributes:
- `zone`: The zone number
- `mode`: Either "cooling" or "heating"
- `max_fan_speed`: The configured maximum fan speed (default: 10)
- `target_temperature`: The target temperature (when active)
- `saved_fan_speed`: The user's manual fan speed that will be restored when thermostat is disabled
