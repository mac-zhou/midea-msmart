
from enum import IntEnum
import logging
from msmart.command import ResponseId, response as base_response
from msmart.command import state_response, capabilities_response
from msmart.command import get_state_command, set_state_command, get_capabilities_command
from msmart.packet_builder import packet_builder
from msmart.device.base import device
import time

VERSION = '0.2.4'

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
            _LOGGER.debug("Unknown {}: {}".format(enum_class, value))
            return default


class air_conditioning(device):

    class fan_speed_enum(IntEnumHelper):
        P0 = 0
        P1 = 1
        P2 = 2
        P3 = 3
        P4 = 4
        P5 = 5
        P6 = 6
        P7 = 7
        P8 = 8
        P9 = 9
        P10 = 10
        P11 = 11
        P12 = 12
        P13 = 13
        P14 = 14
        P15 = 15
        P16 = 16
        P17 = 17
        P18 = 18
        P19 = 19
        P21 = 21
        P22 = 22
        P23 = 23
        P24 = 24
        P25 = 25
        P26 = 26
        P27 = 27
        P28 = 28
        P29 = 29
        P30 = 30
        P31 = 31
        P32 = 32
        P33 = 33
        P34 = 34
        P35 = 35
        P36 = 36
        P37 = 37
        P38 = 38
        P39 = 39
        P41 = 41
        P42 = 42
        P43 = 43
        P44 = 44
        P45 = 45
        P46 = 46
        P47 = 47
        P48 = 48
        P49 = 49
        P50 = 50
        P51 = 51
        P52 = 52
        P53 = 53
        P54 = 54
        P55 = 55
        P56 = 56
        P57 = 57
        P58 = 58
        P59 = 59
        P61 = 61
        P62 = 62
        P63 = 63
        P64 = 64
        P65 = 65
        P66 = 66
        P67 = 67
        P68 = 68
        P69 = 69
        P70 = 70
        P71 = 71
        P72 = 72
        P73 = 73
        P74 = 74
        P75 = 75
        P76 = 76
        P77 = 77
        P78 = 78
        P79 = 79
        P81 = 81
        P82 = 82
        P83 = 83
        P84 = 84
        P85 = 85
        P86 = 86
        P87 = 87
        P88 = 88
        P89 = 89
        P90 = 90
        P91 = 91
        P92 = 92
        P93 = 93
        P94 = 94
        P95 = 95
        P96 = 96
        P97 = 97
        P98 = 98
        P99 = 99
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
        self._fahrenheit_unit = False  # Display temperature in Fahrenheit

        # Support all known modes initially
        self._supported_op_modes = air_conditioning.operational_mode_enum.list()
        self._supported_swing_modes = air_conditioning.swing_mode_enum.list()
        self._supports_eco = True
        self._supports_turbo = True

        self._on_timer = None
        self._off_timer = None
        self._online = True
        self._active = True
        self._indoor_temperature = 0.0
        self._outdoor_temperature = 0.0

    def __str__(self):
        return str(self.__dict__)

    def get_capabilities(self):
        cmd = get_capabilities_command(self.type)
        self._send_cmd(cmd)

    def refresh(self):
        cmd = get_state_command(self.type)
        self._send_cmd(cmd)

    def _send_cmd(self, cmd):
        pkt_builder = packet_builder(self.id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        _LOGGER.debug(
            "pkt_builder: {}:{} len: {} data: {}".format(self.ip, self.port, len(data), data.hex()))
        send_time = time.time()
        if self._protocol_version == 3:
            responses = self._lan_service.appliance_transparent_send_8370(data)
        else:
            responses = self._lan_service.appliance_transparent_send(data)
        request_time = round(time.time() - send_time, 2)
        _LOGGER.debug(
            "Got responses from {}:{} Version: {} Count: {} Spend time: {}".format(self.ip, self.port, self._protocol_version, len(responses), request_time))
        if len(responses) == 0:
            _LOGGER.warn(
                "Got Null from {}:{} Version: {} Count: {} Spend time: {}".format(self.ip, self.port, self._protocol_version, len(responses), request_time))
            self._active = False
            self._support = False
        for response in responses:
            self._process_response(response)

    def _process_response(self, data):
        _LOGGER.debug(
            "Update from {}:{} {}".format(self.ip, self.port, data.hex()))
        if len(data) > 0:
            self._online = True
            self._active = True
            if data == b'ERROR':
                self._support = False
                _LOGGER.warn(
                    "Got ERROR from {}, {}".format(self.ip, self.id))
                return

            # Construct response from data
            response = base_response.construct(data)

            self._defer_update = False
            self._support = True
            if not self._defer_update:
                if response.id == ResponseId.State:
                    self.update(response)
                elif response.id == ResponseId.Capabilities:
                    self.update_capabilities(response)
                elif response.id == 0xa1 or response.id == 0xa0:
                    _LOGGER.warn("Ignored special response. {}:{} {}".format(
                        self.ip, self.port, response.payload.hex()))
                    return

                self._defer_update = False
        elif not self._keep_last_known_online_state:
            self._online = False

    def apply(self):
        self._updating = True
        try:
            # Warn if trying to apply unsupported modes
            if self._operational_mode not in self._supported_op_modes:
                _LOGGER.warn("Device is not capable of operational mode {}.".format(
                    self._operational_mode))

            if self._swing_mode not in self._supported_swing_modes:
                _LOGGER.warn(
                    "Device is not capable of swing mode {}.".format(self._swing_mode))

            if self._turbo_mode and not self._supports_turbo:
                _LOGGER.warn("Device is not capable of turbo mode.")

            if self._eco_mode and not self._supports_eco:
                _LOGGER.warn("Device is not capable of eco mode.")

            cmd = set_state_command(self.type)
            cmd.beep_on = self._prompt_tone
            cmd.power_on = self._power_state
            cmd.target_temperature = self._target_temperature
            cmd.operational_mode = self._operational_mode
            cmd.fan_speed = self._fan_speed
            cmd.on_timer = self._on_timer
            cmd.off_timer = self._off_timer
            cmd.swing_mode = self._swing_mode
            cmd.eco_mode = self._eco_mode
            cmd.turbo_mode = self._turbo_mode
            cmd.fahrenheit = self._fahrenheit_unit
            self._send_cmd(cmd)
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
        self._fahrenheit_unit = res.fahrenheit

        if res.indoor_temperature != 0xff:
            self._indoor_temperature = res.indoor_temperature

        if res.outdoor_temperature != 0xff:
            self._outdoor_temperature = res.outdoor_temperature

        self._on_timer = res.on_timer
        self._off_timer = res.off_timer

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
    def fahrenheit(self):
        return self._fahrenheit_unit

    @fahrenheit.setter
    def fahrenheit(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._fahrenheit_unit = enabled

    @property
    def indoor_temperature(self):
        return self._indoor_temperature

    @property
    def outdoor_temperature(self):
        return self._outdoor_temperature

    @property
    def on_timer(self):
        return self._on_timer

    @on_timer.setter
    def on_timer(self, dtime):
        if self._updating:
            self._defer_update = True
        self._on_timer = dtime

    @property
    def off_timer(self):
        return self._off_timer

    @off_timer.setter
    def off_timer(self, dtime):
        if self._updating:
            self._defer_update = True
        self._off_timer = dtime

    @property
    def supported_operation_modes(self):
        return IntEnumHelper.names(self._supported_op_modes)

    @property
    def supported_swing_modes(self):
        return IntEnumHelper.names(self._supported_swing_modes)
