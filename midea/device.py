
from enum import Enum

import midea.crc8 as crc8
from midea.cloud import cloud
from midea.command import appliance_response
from midea.command import base_command as request_status_command
from midea.command import set_command
from midea.packet_builder import packet_builder


class fan_speed_enum(Enum):
    Auto = 102
    High = 80
    Medium = 60
    Low = 40
    Silent = 20

    @staticmethod
    def list():
        return list(map(lambda c: c.name, fan_speed_enum))


class operational_mode_enum(Enum):
    auto = 1
    cool = 2
    dry = 3
    heat = 4
    fan_only = 5

    @staticmethod
    def list():
        return list(map(lambda c: c.name, operational_mode_enum))


class swing_mode_enum(Enum):
    Off = 0
    On = 0x3C

    @staticmethod
    def list():
        return list(map(lambda c: c.name, swing_mode_enum))


class device:

    def __init__(self, cloud_client: cloud, status: dict):
        self._cloud_client = cloud_client
        self.set_status(status)

        self._audible_feedback = False
        self._power_state = False
        self._target_temperature = 17
        self._operational_mode = operational_mode_enum.auto
        self._fan_speed = fan_speed_enum.Auto
        self._swing_mode = swing_mode_enum.Off
        self._eco_mode = False
        self._turbo_mode = False

        self._on_timer = None
        self._off_timer = None
        self._indoor_temperature = 0.0
        self._outdoor_temperature = 0.0

    def set_status(self, status: dict):
        self.id = status['id']
        self.name = status['name']
        self.model_number = status['modelNumber']
        self.serial_number = status['sn']
        self.type = int(status['type'], 0)
        self.active = status['activeStatus'] == '1'
        self.online = status['onlineStatus'] == '1'

    def refresh(self):
        cmd = request_status_command(self.type)
        pkt_builder = packet_builder()
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        data = self._cloud_client.appliance_transparent_send(self.id, data)
        response = appliance_response(data)
        self.update(response)

    def apply(self):
        cmd = set_command(self.type)
        cmd.audible_feedback = self._audible_feedback
        cmd.power_state = self._power_state
        cmd.target_temperature = self._target_temperature
        cmd.operational_mode = self._operational_mode.value
        cmd.fan_speed = self._fan_speed.value
        cmd.swing_mode = self._swing_mode.value
        cmd.eco_mode = self._eco_mode
        cmd.turbo_mode = self._turbo_mode

        pkt_builder = packet_builder()
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        data = self._cloud_client.appliance_transparent_send(self.id, data)
        response = appliance_response(data)
        self.update(response)

    def update(self, res: appliance_response):
        self._power_state = res.power_state
        self._target_temperature = res.target_temperature
        self._operational_mode = operational_mode_enum(res.operational_mode)
        self._fan_speed = fan_speed_enum(res.fan_speed)
        self._swing_mode = swing_mode_enum(res.swing_mode)
        self._eco_mode = res.eco_mode
        self._turbo_mode = res.turbo_mode
        self._indoor_temperature = res.indoor_temperature
        self._outdoor_temperature = res.outdoor_temperature
        self._timer_on = res.on_timer
        self._timer_off = res.off_timer

    @property
    def audible_feedback(self):
        return self._audible_feedback
        
    @audible_feedback.setter
    def audible_feedback(self, feedback: bool):
        self._audible_feedback = feedback

    @property
    def power_state(self):
        return self._power_state

    @power_state.setter
    def power_state(self, state: bool):
        self._power_state = state

    @property
    def target_temperature(self):
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, temperature: int):
        self._target_temperature = temperature

    @property
    def operational_mode(self):
        return self._operational_mode

    @operational_mode.setter
    def operational_mode(self, mode: operational_mode_enum):
        self._operational_mode = mode

    @property
    def fan_speed(self):
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, speed: fan_speed_enum):
        self._fan_speed = speed

    @property
    def swing_mode(self):
        return self._swing_mode

    @swing_mode.setter
    def swing_mode(self, mode: swing_mode_enum):
        self._swing_mode = mode

    @property
    def eco_mode(self):
        return self._eco_mode

    @eco_mode.setter
    def eco_mode(self, enabled: bool):
        self._eco_mode = enabled

    @property
    def turbo_mode(self):
        return self._turbo_mode

    @turbo_mode.setter
    def turbo_mode(self, enabled: bool):
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
