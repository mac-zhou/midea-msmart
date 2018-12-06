"""
A climate platform that adds support for Midea air conditioning units.

For more details about this platform, please refer to the documentation
https://github.com/NeoAcheron/midea-ac-py

This is still early work in progress
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (
    ClimateDevice,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_AWAY_MODE, SUPPORT_FAN_MODE, SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,
    SUPPORT_ON_OFF, PLATFORM_SCHEMA)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE

REQUIREMENTS = ['midea==0.1.1', 'pycryptodome==3.7.0']
VERSION = '0.1.1'

_LOGGER = logging.getLogger(__name__)

CONF_APP_KEY = 'app_key'
CONF_TEMP_STEP = 'temp_step'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_APP_KEY): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_TEMP_STEP, default=1.0): vol.Coerce(float)
})

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE | SUPPORT_FAN_MODE | SUPPORT_OPERATION_MODE | SUPPORT_SWING_MODE | SUPPORT_ON_OFF


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Midea cloud service and query appliances."""

    from midea.client import client as midea_client

    app_key = config.get(CONF_APP_KEY)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    temp_step = config.get(CONF_TEMP_STEP)

    client = midea_client(app_key, username, password)
    devices = client.devices()
    entities = []
    for device in devices:
        if(device.type == 0xAC):
            entities.append(MideaClimateACDevice(device, temp_step))
        else:
            _LOGGER.error(
                "Unsupported device type: 0x{:02x}".format(device.type))

    async_add_entities(entities)


class MideaClimateACDevice(ClimateDevice):
    """Representation of a Midea climate AC device."""

    def __init__(self, device, temp_step: float):
        """Initialize the climate device."""
        from midea.device import air_conditioning_device as ac

        # Not a great place to have this, but if we don't refresh the state, 
        # bad state values are logged in the state timeline.
        device.refresh()

        self._support_flags = SUPPORT_FLAGS
        self._device = device
        self._unit_of_measurement = TEMP_CELSIUS
        self._target_temperature_step = temp_step

        self._operation_list = ac.operational_mode_enum.list()
        self._fan_list = ac.fan_speed_enum.list()
        self._swing_list = ac.swing_mode_enum.list()

    def update(self):
        """Retrieve latest state from the appliance."""
        # This cannot be async, the API doesn't like it at all.
        self._device.refresh()

    @property
    def available(self):
        """Checks if the appliance is available for commands."""
        return self._device.online

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    @property
    def should_poll(self):
        """Poll the appliance for changes, there is no notification capability in the Midea API"""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return "midea_{}".format(self._device.id)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.indoor_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._device.operational_mode.name

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._device.fan_speed.name

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._device.swing_mode.name

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._device.eco_mode

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._device.power_state

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.target_temperature = int(kwargs.get(ATTR_TEMPERATURE))

        self._device.apply()
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        from midea.device import air_conditioning_device as ac
        self._device.swing_mode = ac.swing_mode_enum[swing_mode]
        self._device.apply()
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        from midea.device import air_conditioning_device as ac
        self._device.fan_speed = ac.fan_speed_enum[fan_mode]
        self._device.apply()
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        from midea.device import air_conditioning_device as ac
        self._device.operational_mode = ac.operational_mode_enum[operation_mode]
        self._device.apply()
        self.schedule_update_ha_state()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._device.eco_mode = True
        self._device.apply()
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._device.eco_mode = False
        self._device.apply()
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on."""
        self._device.power_state = True
        self._device.apply()
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        self._device.power_state = False
        self._device.apply()
        self.schedule_update_ha_state()
