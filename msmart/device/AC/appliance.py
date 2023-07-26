
from enum import IntEnum
import logging
from .command import ResponseId, InvalidResponseException, response as base_response
from .command import state_response, capabilities_response
from .command import get_state_command, set_state_command, get_capabilities_command, toggle_display_command
from msmart.device.base import device


_LOGGER = logging.getLogger(__name__)


class IntEnumHelper(IntEnum):
    @staticmethod
    def names(enum):
        return list(map(lambda c: c.name, enum))

    @staticmethod
    def get(enum_class, value, default=None):
        try:
            return enum_class(value)
        except ValueError:
            _LOGGER.debug("Unknown %s: %d", enum_class, value)
            return default


class air_conditioning(device):

    class fan_speed_enum(IntEnumHelper):
        Auto = 102
        Full = 100
        High = 80
        Medium = 60
        Low = 40
        Silent = 20

        @staticmethod
        def list():
            return IntEnumHelper.names(__class__)

        @staticmethod
        def get(value):
            return IntEnumHelper.get(__class__, value, air_conditioning.fan_speed_enum.Auto)

    class operational_mode_enum(IntEnumHelper):
        auto = 1
        cool = 2
        dry = 3
        heat = 4
        fan_only = 5

        @staticmethod
        def list():
            return IntEnumHelper.names(__class__)

        @staticmethod
        def get(value):
            return IntEnumHelper.get(__class__, value, air_conditioning.operational_mode_enum.fan_only)

    class swing_mode_enum(IntEnumHelper):
        Off = 0x0
        Vertical = 0xC
        Horizontal = 0x3
        Both = 0xF

        @staticmethod
        def list():
            return IntEnumHelper.names(__class__)

        @staticmethod
        def get(value):
            return IntEnumHelper.get(__class__, value, air_conditioning.swing_mode_enum.Off)

    def __init__(self, *args, **kwargs):
        super(air_conditioning, self).__init__(*args, **kwargs)
        self._prompt_tone = False
        self._power_state = False
        self._target_temperature = 17.0
        self._operational_mode = air_conditioning.operational_mode_enum.auto
        self._fan_speed = air_conditioning.fan_speed_enum.Auto
        self._swing_mode = air_conditioning.swing_mode_enum.Off
        self._eco_mode = False
        self._turbo_mode = False
        self._freeze_protection_mode = False
        self._sleep_mode = False
        self._fahrenheit_unit = False  # Display temperature in Fahrenheit
        self._display_on = False
        self._filter_alert = False

        # Support all known modes initially
        self._supported_op_modes = air_conditioning.operational_mode_enum.list()
        self._supported_swing_modes = air_conditioning.swing_mode_enum.list()
        self._supports_eco = True
        self._supports_turbo = True
        self._supports_freeze_protection_mode = True
        self._supports_display_control = True
        self._min_target_temperature = 16
        self._max_target_temperature = 30

        self._on_timer = None
        self._off_timer = None
        self._online = False
        self._active = False
        self._indoor_temperature = None
        self._outdoor_temperature = None

    def __str__(self):
        return str(self.__dict__)

    def get_capabilities(self):
        cmd = get_capabilities_command(self.type)
        self.send_cmd(cmd)

    def toggle_display(self):
        if not self._supports_display_control:
            _LOGGER.warning("Device is not capable of display control.")

        cmd = toggle_display_command(self.type)
        self.send_cmd(cmd, True)

        # Force a refresh to get the updated display state
        self.refresh()

    def refresh(self):
        cmd = get_state_command(self.type)
        self.send_cmd(cmd)

    def send_cmd(self, cmd, ignore_response=False):
        responses = super().send_cmd(cmd)

        # Ignore responses if requested
        if ignore_response:
            return

        # Process each response
        for response in responses:
            self.process_response(response)

    def process_response(self, data):
        if super().process_response(data):
            # Construct response from data
            try:
                response = base_response.construct(data)
            except InvalidResponseException as e:
                _LOGGER.error(e)
                return

            self._support = True

            if response.id == ResponseId.State:
                self.update(response)
            elif response.id == ResponseId.Capabilities:
                self.update_capabilities(response)
            elif response.id == 0xa1 or response.id == 0xa0:
                _LOGGER.info("Ignored special response. %s:%d %s",
                             self.ip, self.port, response.payload.hex())
        elif not self._keep_last_known_online_state:
            self._online = False

    def apply(self):
        self._updating = True
        try:
            # Warn if trying to apply unsupported modes
            if self._operational_mode not in self._supported_op_modes:
                _LOGGER.warning(
                    "Device is not capable of operational mode %s.", self._operational_mode)

            if self._swing_mode not in self._supported_swing_modes:
                _LOGGER.warning(
                    "Device is not capable of swing mode %s.", self._swing_mode)

            if self._turbo_mode and not self._supports_turbo:
                _LOGGER.warning("Device is not capable of turbo mode.")

            if self._eco_mode and not self._supports_eco:
                _LOGGER.warning("Device is not capable of eco mode.")

            if self._freeze_protection_mode and not self._supports_freeze_protection_mode:
                _LOGGER.warning("Device is not capable of freeze protection.")

            cmd = set_state_command(self.type)
            cmd.beep_on = self._prompt_tone
            cmd.power_on = self._power_state
            cmd.target_temperature = self._target_temperature
            cmd.operational_mode = self._operational_mode
            cmd.fan_speed = self._fan_speed
            cmd.swing_mode = self._swing_mode
            cmd.eco_mode = self._eco_mode
            cmd.turbo_mode = self._turbo_mode
            cmd.freeze_protection_mode = self._freeze_protection_mode
            cmd.sleep_mode = self._sleep_mode
            cmd.fahrenheit = self._fahrenheit_unit
            self.send_cmd(cmd, self._defer_update)
        finally:
            self._updating = False
            self._defer_update = False

    def update(self, res: state_response):
        self._power_state = res.power_on

        self._target_temperature = res.target_temperature
        self._operational_mode = air_conditioning.operational_mode_enum.get(
            res.operational_mode)

        self._fan_speed = air_conditioning.fan_speed_enum.get(
            res.fan_speed)

        self._swing_mode = air_conditioning.swing_mode_enum.get(
            res.swing_mode)

        self._eco_mode = res.eco_mode
        self._turbo_mode = res.turbo_mode
        self._freeze_protection_mode = res.freeze_protection_mode
        self._sleep_mode = res.sleep_mode

        self._indoor_temperature = res.indoor_temperature
        self._outdoor_temperature = res.outdoor_temperature

        self._display_on = res.display_on
        self._fahrenheit_unit = res.fahrenheit

        self._filter_alert = res.filter_alert

        # self._on_timer = res.on_timer
        # self._off_timer = res.off_timer

    def update_capabilities(self, res: capabilities_response):
        # Build list of supported operation modes
        op_modes = [air_conditioning.operational_mode_enum.fan_only]
        if res.dry_mode:
            op_modes.append(air_conditioning.operational_mode_enum.dry)
        if res.cool_mode:
            op_modes.append(air_conditioning.operational_mode_enum.cool)
        if res.heat_mode:
            op_modes.append(air_conditioning.operational_mode_enum.heat)
        if res.auto_mode:
            op_modes.append(air_conditioning.operational_mode_enum.auto)

        self._supported_op_modes = op_modes

        # Build list of supported swing modes
        swing_modes = [air_conditioning.swing_mode_enum.Off]
        if res.swing_horizontal:
            swing_modes.append(air_conditioning.swing_mode_enum.Horizontal)
        if res.swing_vertical:
            swing_modes.append(air_conditioning.swing_mode_enum.Vertical)
        if res.swing_both:
            swing_modes.append(air_conditioning.swing_mode_enum.Both)

        self._supported_swing_modes = swing_modes

        self._supports_eco = res.eco_mode
        self._supports_turbo = res.turbo_mode
        self._supports_freeze_protection_mode = res.freeze_protection_mode

        self._supports_display_control = res.display_control

        self._min_target_temperature = res.min_temperature
        self._max_target_temperature = res.max_temperature

    @property
    def prompt_tone(self):
        return self._prompt_tone

    @prompt_tone.setter
    def prompt_tone(self, feedback: bool):
        if self._updating:
            self._defer_update = True
        self._prompt_tone = feedback

    @property
    def power_state(self):
        return self._power_state

    @power_state.setter
    def power_state(self, state: bool):
        if self._updating:
            self._defer_update = True
        self._power_state = state

    @property
    def target_temperature(self):
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, temperature_celsius: float):
        if self._updating:
            self._defer_update = True
        self._target_temperature = temperature_celsius

    @property
    def operational_mode(self):
        return self._operational_mode

    @operational_mode.setter
    def operational_mode(self, mode: operational_mode_enum):
        if self._updating:
            self._defer_update = True
        self._operational_mode = mode

    @property
    def fan_speed(self):
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, speed: fan_speed_enum):
        if self._updating:
            self._defer_update = True
        self._fan_speed = speed

    @property
    def swing_mode(self):
        return self._swing_mode

    @swing_mode.setter
    def swing_mode(self, mode: swing_mode_enum):
        if self._updating:
            self._defer_update = True
        self._swing_mode = mode

    @property
    def eco_mode(self):
        return self._eco_mode

    @eco_mode.setter
    def eco_mode(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._eco_mode = enabled

    @property
    def turbo_mode(self):
        return self._turbo_mode

    @turbo_mode.setter
    def turbo_mode(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._turbo_mode = enabled

    @property
    def supports_freeze_protection_mode(self):
        return self._supports_freeze_protection_mode

    @property
    def freeze_protection_mode(self):
        return self._freeze_protection_mode

    @freeze_protection_mode.setter
    def freeze_protection_mode(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._freeze_protection_mode = enabled

    @property
    def sleep_mode(self):
        return self._sleep_mode

    @sleep_mode.setter
    def sleep_mode(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._sleep_mode = enabled

    @property
    def fahrenheit(self):
        return self._fahrenheit_unit

    @fahrenheit.setter
    def fahrenheit(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._fahrenheit_unit = enabled

    @property
    def display_on(self):
        return self._display_on

    @property
    def filter_alert(self):
        return self._filter_alert

    @property
    def indoor_temperature(self):
        return self._indoor_temperature

    @property
    def outdoor_temperature(self):
        return self._outdoor_temperature

    @property
    def on_timer(self):
        return self._on_timer

    @property
    def off_timer(self):
        return self._off_timer

    @property
    def supported_operation_modes(self):
        return IntEnumHelper.names(self._supported_op_modes)

    @property
    def supported_swing_modes(self):
        return IntEnumHelper.names(self._supported_swing_modes)

    @property
    def min_target_temperature(self):
        return self._min_target_temperature

    @property
    def max_target_temperature(self):
        return self._max_target_temperature
