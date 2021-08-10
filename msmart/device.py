
import logging
from enum import Enum

import msmart.crc8 as crc8
from msmart.lan import lan
from msmart.command import appliance_response
from msmart.command import base_command as request_status_command
from msmart.command import set_command
from msmart.packet_builder import packet_builder

VERSION = '0.1.27'

_LOGGER = logging.getLogger(__name__)


def convert_device_id_hex(device_id: int):
    return device_id.to_bytes(6, 'little').hex()


def convert_device_id_int(device_id: str):
    return int.from_bytes(bytes.fromhex(device_id), 'little')


class device:

    def __init__(self, device_ip: str, device_id: int, device_port: int):
        # device_id = convert_device_id_hex(device_id)
        self._lan_service = lan(device_ip, device_id, device_port)
        self._ip = device_ip
        self._id = device_id
        self._port = device_port
        self._keep_last_known_online_state = False
        self._type = 0xac
        self._updating = False
        self._defer_update = False
        self._half_temp_step = False
        self._support = False
        self._online = True
        self._active = True
        self._protocol_version = 2

    def authenticate(self, key: str, token: str):
        # compatible example.py
        if key != "YOUR_AC_K1" and token != "YOUR_AC_TOKEN":
            self._protocol_version = 3
            self._token = bytearray.fromhex(token)
            self._key = bytearray.fromhex(key)
            self._authenticate()

    def _authenticate(self):
        self._lan_service.authenticate(self._token, self._key)

    def set_device_detail(self, device_detail: dict):
        self._id = device_detail['id']
        self._name = device_detail['name']
        self._model_number = device_detail['modelNumber']
        self._serial_number = device_detail['sn']
        self._type = int(device_detail['type'], 0)
        self._active = device_detail['activeStatus'] == '1'
        self._online = device_detail['onlineStatus'] == '1'

    def refresh(self):
        pass

    def apply(self):
        pass

    @property
    def id(self):
        return self._id

    @property
    def ip(self):
        return self._ip

    @property
    def port(self):
        return self._ip

    @property
    def name(self):
        return self._name

    @property
    def model_number(self):
        return self._model_number

    @property
    def serial_number(self):
        return self._serial_number

    @property
    def type(self):
        return self._type

    @property
    def active(self):
        return self._active

    @property
    def online(self):
        return self._online

    @property
    def support(self):
        return self._support

    @property
    def keep_last_known_online_state(self):
        return self._keep_last_known_online_state

    @keep_last_known_online_state.setter
    def keep_last_known_online_state(self, feedback: bool):
        self._keep_last_known_online_state = feedback


class air_conditioning_device(device):

    class fan_speed_enum(Enum):
        Auto = 102
        Full = 100
        High = 80
        Medium = 60
        Low = 40
        Silent = 20

        @staticmethod
        def list():
            return list(map(lambda c: c.name, air_conditioning_device.fan_speed_enum))

        @staticmethod
        def get(value):
            if(value in air_conditioning_device.fan_speed_enum._value2member_map_):
                return air_conditioning_device.fan_speed_enum(value)
            _LOGGER.debug("Unknown Fan Speed: {}".format(value))
            return air_conditioning_device.fan_speed_enum.Auto

    class operational_mode_enum(Enum):
        auto = 1
        cool = 2
        dry = 3
        heat = 4
        fan_only = 5

        @staticmethod
        def list():
            return list(map(lambda c: c.name, air_conditioning_device.operational_mode_enum))

        @staticmethod
        def get(value):
            if(value in air_conditioning_device.operational_mode_enum._value2member_map_):
                return air_conditioning_device.operational_mode_enum(value)
            _LOGGER.debug("Unknown Operational Mode: {}".format(value))
            return air_conditioning_device.operational_mode_enum.fan_only

    class swing_mode_enum(Enum):
        Off = 0x0
        Vertical = 0xC
        Horizontal = 0x3
        Both = 0xF

        @staticmethod
        def list():
            return list(map(lambda c: c.name, air_conditioning_device.swing_mode_enum))

        @staticmethod
        def get(value):
            if(value in air_conditioning_device.swing_mode_enum._value2member_map_):
                return air_conditioning_device.swing_mode_enum(value)
            _LOGGER.debug("Unknown Swing Mode: {}".format(value))
            return air_conditioning_device.swing_mode_enum.Off

    def __init__(self, *args, **kwargs):
        super(air_conditioning_device, self).__init__(*args, **kwargs)
        self._prompt_tone = False
        self._power_state = False
        self._target_temperature = 17.0
        self._operational_mode = air_conditioning_device.operational_mode_enum.auto
        self._fan_speed = air_conditioning_device.fan_speed_enum.Auto
        self._swing_mode = air_conditioning_device.swing_mode_enum.Off
        self._eco_mode = False
        self._turbo_mode = False
        self.farenheit_unit = False  # default unit is Celcius. this is just to control the temperatue unit of the AC's display. the target_temperature setter always expects a celcius temperature (resolution of 0.5C), as does the midea API

        self._on_timer = None
        self._off_timer = None
        self._online = True
        self._active = True
        self._indoor_temperature = 0.0
        self._outdoor_temperature = 0.0

    def refresh(self):
        cmd = request_status_command(self.type)
        self._send_cmd(cmd)

    def _send_cmd(self, cmd):
        pkt_builder = packet_builder(self.id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        if self._protocol_version == 3:
            responses = self._lan_service.appliance_transparent_send_8370(data)
        else:
            responses = self._lan_service.appliance_transparent_send(data)
        for response in responses:
            self._process_response(response)

    def _process_response(self, data):
        _LOGGER.debug(
            "Update from {}:{} {}".format(self.ip, self.port, data.hex()))
        if len(data) > 0:
            self._online = True
            if data == b'ERROR':
                _LOGGER.debug(
                    "got ERROR from {}, {}".format(self.ip, self.id))
                # self._authenticate()
                return
            response = appliance_response(data)
            self._defer_update = False
            self._support = True
            if not self._defer_update:
                if data[0xa] == 0xc0:
                    self.update(response)
                if data[0xa] == 0xa1 or data[0xa] == 0xa0:
                    '''only update indoor_temperature and outdoor_temperature'''
                    _LOGGER.debug("Update - Special Respone. {}:{} {}".format(
                        self.ip, self.port, data[0xa:].hex()))
                    pass
                    # self.update_special(response)
                self._defer_update = False
        elif not self._keep_last_known_online_state:
            self._online = False

    def apply(self):
        self._updating = True
        try:
            cmd = set_command(self.type)
            cmd.prompt_tone = self._prompt_tone
            cmd.power_state = self._power_state
            cmd.target_temperature = self._target_temperature
            cmd.operational_mode = self._operational_mode.value
            cmd.fan_speed = self._fan_speed.value
            cmd.swing_mode = self._swing_mode.value
            cmd.eco_mode = self._eco_mode
            cmd.turbo_mode = self._turbo_mode
            # pkt_builder = packet_builder(self.id)
#            cmd.night_light = False
            cmd.fahrenheit = self.farenheit_unit
            self._send_cmd(cmd)
        finally:
            self._updating = False
            self._defer_update = False

    def update(self, res: appliance_response):
        self._power_state = res.power_state
        self._target_temperature = res.target_temperature
        self._operational_mode = air_conditioning_device.operational_mode_enum.get(
            res.operational_mode)
        self._fan_speed = air_conditioning_device.fan_speed_enum.get(
            res.fan_speed)
        self._swing_mode = air_conditioning_device.swing_mode_enum.get(
            res.swing_mode)
        self._eco_mode = res.eco_mode
        self._turbo_mode = res.turbo_mode
        indoor_temperature = res.indoor_temperature
        if indoor_temperature != 0xff:
            self._indoor_temperature = indoor_temperature
        outdoor_temperature = res.outdoor_temperature
        if outdoor_temperature != 0xff:
            self._outdoor_temperature = outdoor_temperature
        self._on_timer = res.on_timer
        self._off_timer = res.off_timer

    def update_special(self, res: appliance_response):
        indoor_temperature = res.indoor_temperature
        if indoor_temperature != 0xff:
            self._indoor_temperature = indoor_temperature
        outdoor_temperature = res.outdoor_temperature
        if outdoor_temperature != 0xff:
            self._outdoor_temperature = outdoor_temperature

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
    def target_temperature(self, temperature_celsius: float): # the implementation later rounds the temperature down to the nearest 0.5'C resolution.
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


class unknown_device(device):

    def __init__(self, lan_service: lan):
        super().__init__(lan_service)

    def refresh(self):
        cmd = request_status_command(self.type)
        pkt_builder = packet_builder()
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        data = self._lan_service.appliance_transparent_send(self.id, data)
        if len(data) > 0:
            self._online = True
            response = appliance_response(data)
            _LOGGER.debug("Decoded Data: {}".format({
                'prompt_tone': response.prompt_tone,
                'target_temperature': response.target_temperature,
                'indoor_temperature': response.indoor_temperature,
                'outdoor_temperature': response.outdoor_temperature,
                'operational_mode': response.operational_mode,
                'fan_speed': response.fan_speed,
                'swing_mode': response.swing_mode,
                'eco_mode': response.eco_mode,
                'turbo_mode': response.turbo_mode
            }))
        elif not self._keep_last_known_online_state:
            self._online = False

    def apply(self):
        _LOGGER.debug("Cannot apply, device not fully supported yet")


class dehumidifier_device(unknown_device):

    def __init__(self, lan_service: lan):
        super().__init__(lan_service)
