
from enum import Enum

import midea.crc8 as crc8
from midea.cloud import cloud
from midea.command import appliance_response
from midea.command import base_command as request_status_command
from midea.command import set_command
from midea.packet_builder import packet_builder


class device:

    def __init__(self, cloud_service: cloud):
        self._cloud_service = cloud_service

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


class air_conditioning_device(device):

    class fan_speed_enum(Enum):
        Auto = 102
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
            print("Unknown Fan Speed: {}".format(value))
            return air_conditioning_device.fan_speed_enum.Auto

    class operational_mode_enum(Enum):
        auto = 1
        cool = 2
        dry = 3
        heat = 4
        fan_only = 5
        super_test = 6

        @staticmethod
        def list():
            return list(map(lambda c: c.name, air_conditioning_device.operational_mode_enum))

        @staticmethod
        def get(value):
            if(value in air_conditioning_device.operational_mode_enum._value2member_map_):
                return air_conditioning_device.operational_mode_enum(value)
            print("Unknown Operational Mode: {}".format(value))
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
            print("Unknown Swing Mode: {}".format(value))
            return air_conditioning_device.swing_mode_enum.Off

    def __init__(self, cloud_service: cloud):
        super().__init__(cloud_service)

        self._audible_feedback = False
        self._power_state = False
        self._target_temperature = 17
        self._operational_mode = air_conditioning_device.operational_mode_enum.auto
        self._fan_speed = air_conditioning_device.fan_speed_enum.Auto
        self._swing_mode = air_conditioning_device.swing_mode_enum.Off
        self._eco_mode = False
        self._turbo_mode = False

        self._on_timer = None
        self._off_timer = None
        self._indoor_temperature = 0.0
        self._outdoor_temperature = 0.0

    def refresh(self):
        cmd = request_status_command(self.type)
        pkt_builder = packet_builder()
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        data = self._cloud_service.appliance_transparent_send(self.id, data)
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
        data = self._cloud_service.appliance_transparent_send(self.id, data)
        response = appliance_response(data)
        self.update(response)

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


class unknown_device(device):

    def __init__(self, cloud_service: cloud):
        super().__init__(cloud_service)

    def refresh(self):
        cmd = request_status_command(self.type)
        pkt_builder = packet_builder()
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        data = self._cloud_service.appliance_transparent_send(self.id, data)
        response = appliance_response(data)
        print("Decoded Data: {}".format({
            'audible_feedback': response.audible_feedback,
            'target_temperature': response.target_temperature,
            'indoor_temperature': response.indoor_temperature,
            'outdoor_temperature': response.outdoor_temperature,
            'operational_mode': response.operational_mode,
            'fan_speed': response.fan_speed,
            'swing_mode': response.swing_mode,
            'eco_mode': response.eco_mode,
            'turbo_mode': response.turbo_mode
        }))

    def apply(self):
        print("Cannot apply, device not fully supported yet")


class dehumidifier_device(unknown_device):

    def __init__(self, cloud_service: cloud):
        super().__init__(cloud_service)
