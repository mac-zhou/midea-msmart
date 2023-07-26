
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import IntEnum
import logging
import math
import msmart.crc8 as crc8
import struct
from msmart.const import FRAME_TYPE
from msmart.base_command import command


_LOGGER = logging.getLogger(__name__)


class InvalidResponseException(Exception):
    pass


class ResponseId(IntEnum):
    State = 0xC0
    Capabilities = 0xB5


class CapabilityId(IntEnum):
    IndoorHumidity = 0x0015
    SilkyCool = 0x0018
    SmartEye = 0x0030
    WindOnMe = 0x0032
    WindOffMe = 0x0033
    ActiveClean = 0x0039
    OneKeyNoWindOnMe = 0x0042
    BreezeControl = 0x0043
    FanSpeedControl = 0x0210
    PresetEco = 0x0212
    PresetFreezeProtection = 0x0213
    Modes = 0x0214
    SwingModes = 0x0215
    Power = 0x0216
    Nest = 0x0217
    AuxElectricHeat = 0x0219
    PresetTurbo = 0x021A
    Humidity = 0x021F
    UnitChangeable = 0x0222
    LightControl = 0x0224
    Temperatures = 0x0225
    Buzzer = 0x022C


class temperature_type(IntEnum):
    Unknown = 0
    Indoor = 0x2
    Outdoor = 0x3


class get_capabilities_command(command):
    def __init__(self, device_type):
        super().__init__(device_type, FRAME_TYPE=FRAME_TYPE.Request)

    @property
    def payload(self):
        return bytes([
            # Get capabilities
            0xB5,
            # Unknown
            0x01, 0x11,
        ])


class get_state_command(command):
    def __init__(self, device_type):
        super().__init__(device_type, FRAME_TYPE=FRAME_TYPE.Request)

        self.temperature_type = temperature_type.Indoor

    @property
    def payload(self):
        return bytes([
            # Get state
            0x41,
            # Unknown
            0x81, 0x00, 0xFF, 0x03, 0xFF, 0x00,
            # Temperature request
            self.temperature_type,
            # Unknown
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            # Unknown
            0x03,
        ])


class set_state_command(command):
    def __init__(self, device_type):
        super().__init__(device_type, FRAME_TYPE=FRAME_TYPE.Set)

        self.beep_on = True
        self.power_on = False
        self.target_temperature = 25.0
        self.operational_mode = 0
        self.fan_speed = 0
        self.eco_mode = True
        self.swing_mode = 0
        self.turbo_mode = False
        self.fahrenheit = True
        self.sleep_mode = False
        self.freeze_protection_mode = False

    @property
    def payload(self):
        # Build prompt tone and power status byte
        beep = 0x42 if self.beep_on else 0
        power = 0x1 if self.power_on else 0

        # Build target temp and mode byte
        fractional, integral = math.modf(self.target_temperature)
        temperature = (int(integral) & 0xF) | (0x10 if fractional > 0 else 0)
        mode = (self.operational_mode & 0x7) << 5

        # Build swing mode byte
        swing_mode = 0x30 | (self.swing_mode & 0x3F)

        # Build eco mode byte
        eco_mode = 0x80 if self.eco_mode else 0

        # Build sleep, turbo and fahrenheit byte
        sleep = 0x01 if self.sleep_mode else 0
        turbo = 0x02 if self.turbo_mode else 0
        fahrenheit = 0x04 if self.fahrenheit else 0

        # Build alternate turbo byte
        turbo_alt = 0x20 if self.turbo_mode else 0

        # Build alternate turbo byte
        freeze_protect = 0x80 if self.freeze_protection_mode else 0

        return bytes([
            # Set state
            0x40,
            # Beep and power state
            beep | power,
            # Temperature and operational mode
            temperature | mode,
            # Fan speed
            self.fan_speed,
            # Unknown
            0x7F, 0x7F, 0x00,
            # Swing mode
            swing_mode,
            # Alternate turbo mode
            turbo_alt,
            # ECO mode
            eco_mode,
            # Sleep mode, turbo mode and fahrenheit
            sleep | turbo | fahrenheit,
            # Unknown
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00,
            # Frost/freeze protection
            freeze_protect,
            # Unknown
            0x00, 0x00,
        ])


class toggle_display_command(command):
    def __init__(self, device_type):
        # For whatever reason, toggle display uses a request type...
        super().__init__(device_type, FRAME_TYPE=FRAME_TYPE.Request)

    @property
    def payload(self):
        # Payload taken directly from dudanov/MideaUART
        return bytes([
            # Get state
            0x41,
            # Unknown
            0x61, 0x00, 0xFF, 0x02,
            0x00, 0x02, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
        ])


class response():
    def __init__(self, payload: memoryview):
        # Set ID and copy the payload
        self._id = payload[0]
        self._payload = bytes(payload)

    @property
    def id(self):
        return self._id

    @property
    def payload(self):
        return self._payload

    @staticmethod
    def validate(frame: memoryview):
        # Validate frame checksum
        frame_checksum = command.checksum(frame[1:-1])
        if frame_checksum != frame[-1]:
            raise InvalidResponseException(
                f"Frame '{frame.hex()}' failed checksum. Received: 0x{frame[-1]:X}, Expected: 0x{frame_checksum:X}.")

        # Extract frame payload to validate CRC/checksum
        payload = frame[10:-1]

        # Some devices use a CRC others seem to use a 2nd checksum
        payload_crc = crc8.calculate(payload[0:-1])
        payload_checksum = command.checksum(payload[0:-1])

        if payload_crc != payload[-1] and payload_checksum != payload[-1]:
            raise InvalidResponseException(
                f"Payload '{payload.hex()}' failed CRC and checksum. Received: 0x{payload[-1]:X}, Expected: 0x{payload_crc:X} or 0x{payload_checksum:X}.")

    @staticmethod
    def construct(frame: bytes):
        # Build a memoryview of the frame for zero-copy slicing
        with memoryview(frame) as frame_mv:
            # Ensure frame is valid before parsing
            response.validate(frame_mv)

            # Parse frame depending on id
            id = frame_mv[10]
            payload = frame_mv[10:-2]
            if id == ResponseId.State:
                return state_response(payload)
            elif id == ResponseId.Capabilities:
                return capabilities_response(payload)
            else:
                return response(payload)


class capabilities_response(response):
    def __init__(self, payload: memoryview):
        super().__init__(payload)

        self._capabilities = {}

        _LOGGER.debug("Capabilities response payload: %s", payload.hex())

        self._parse_capabilities(payload)

        _LOGGER.debug("Supported capabilities: %s", self._capabilities)

    def _parse_capabilities(self, payload: memoryview):
        # Clear existing capabilities
        self._capabilities.clear()

        # Define some local functions to parse capability values
        def get_bool(v): return v != 0
        def get_value(w): return lambda v: v == w
        def get_no_value(w): return lambda v: v != w

        # Define a named tuple that represents a decoder
        reader = namedtuple("decoder", "name read")

        # Create a map of capability ID to decoders
        capability_readers = {
            CapabilityId.IndoorHumidity: reader("indoor_humidity", get_bool),
            CapabilityId.SilkyCool: reader("silky_cool", get_value(1)),
            CapabilityId.SmartEye:  reader("smart_eye", get_value(1)),
            CapabilityId.WindOnMe:  reader("wind_on_me", get_value(1)),
            CapabilityId.WindOffMe:  reader("wind_off_me", get_value(1)),
            CapabilityId.ActiveClean:  reader("active_clean", get_value(1)),
            CapabilityId.OneKeyNoWindOnMe: reader("one_key_no_wind_on_me", get_value(1)),
            CapabilityId.BreezeControl: reader("breeze_control", get_value(1)),
            # Fan speed control always seems to return false, even if unit can
            CapabilityId.FanSpeedControl: reader("fan_speed_control", get_no_value(1)),
            CapabilityId.PresetEco: [
                reader("eco_mode", get_value(1)),
                reader("eco_mode_2", get_value(2)),
            ],
            CapabilityId.PresetFreezeProtection: reader("freeze_protection", get_value(1)),
            CapabilityId.Modes: [
                reader("heat_mode", lambda v: v == 1 or v == 2),
                reader("cool_mode", lambda v: v != 2),
                reader("dry_mode", lambda v: v < 2),
                reader("auto_mode", lambda v: v < 3),
            ],
            CapabilityId.SwingModes: [
                reader("swing_horizontal", lambda v: v == 1 or v == 3),
                reader("swing_vertical", lambda v: v < 2),
            ],
            CapabilityId.Power: [
                reader("power_cal", lambda v: v == 2 or v == 3),
                reader("power_cal_setting", lambda v: v == 3),
            ],
            CapabilityId.Nest: [
                reader("nest_check", lambda v: v == 1 or v == 2 or v == 4),
                reader("nest_need_change", lambda v: v == 3 or v == 4),
            ],
            CapabilityId.AuxElectricHeat: reader("aux_electric_heat", get_bool),
            CapabilityId.PresetTurbo:  [
                reader("turbo_heat", lambda v: v == 1 or v == 3),
                reader("turbo_cool", lambda v: v < 2),
            ],
            CapabilityId.Humidity:
            [
                reader("humidity_auto_set", lambda v: v == 1 or v == 2),
                reader("humidity_manual_set", lambda v: v == 2 or v == 3),
            ],
            CapabilityId.UnitChangeable: reader("unit_changeable", get_value(0)),
            CapabilityId.LightControl: reader("light_control", get_bool),
            # Temperatures capability too complex to be handled here
            CapabilityId.Buzzer:  reader("buzzer", get_bool),
        }

        count = payload[1]
        caps = payload[2:]

        # Loop through each capability
        for i in range(0, count):
            # Stop if out of data
            if len(caps) < 3:
                break

            # Skip empty capabilities
            size = caps[2]
            if size == 0:
                continue

            # Unpack 16 bit ID
            (cap_id, ) = struct.unpack("<H", caps[0:2])

            # Covert ID to enumerate type
            try:
                id = CapabilityId(cap_id)
            except ValueError:
                _LOGGER.warning(
                    "Unknown capability. ID: 0x%4X, Size: %d.", cap_id, size)
                # Advanced to next capability
                caps = caps[3+size:]
                continue

            # Fetch first cap value
            value = caps[3]

            # Apply predefined capability reader if it exists
            if id in capability_readers:
                # Local function to apply a reader
                def apply(d): return {d.name: d.read(value)}

                reader = capability_readers[cap_id]
                if isinstance(reader, list):
                    # Apply each reader in the list
                    for r in reader:
                        self._capabilities.update(apply(r))
                else:
                    # Apply the single reader
                    self._capabilities.update(apply(reader))

            elif id == CapabilityId.Temperatures:
                # Skip if capability size is too small
                if size < 6:
                    continue

                self._capabilities["cool_min_temperature"] = caps[3] * 0.5
                self._capabilities["cool_max_temperature"] = caps[4] * 0.5
                self._capabilities["auto_min_temperature"] = caps[5] * 0.5
                self._capabilities["auto_max_temperature"] = caps[6] * 0.5
                self._capabilities["heat_min_temperature"] = caps[7] * 0.5
                self._capabilities["heat_max_temperature"] = caps[8] * 0.5

                self._capabilities["decimals"] = caps[9] == 0 if size > 6 else caps[2] == 0

            else:
                _LOGGER.warning(
                    "Unsupported capability. ID: 0x%04X, Size: %d.", id, size)

            # Advanced to next capability
            caps = caps[3+size:]

    @property
    def swing_horizontal(self):
        return self._capabilities.get("swing_horizontal", False)

    @property
    def swing_vertical(self):
        return self._capabilities.get("swing_vertical", False)

    @property
    def swing_both(self):
        return self.swing_vertical and self.swing_horizontal

    @property
    def dry_mode(self):
        return self._capabilities.get("dry_mode", False)

    @property
    def cool_mode(self):
        return self._capabilities.get("cool_mode", False)

    @property
    def heat_mode(self):
        return self._capabilities.get("heat_mode", False)

    @property
    def auto_mode(self):
        return self._capabilities.get("auto_mode", False)

    @property
    def eco_mode(self):
        return self._capabilities.get("eco_mode", False) or self._capabilities.get("eco_mode_2", False)

    @property
    def turbo_mode(self):
        return self._capabilities.get("turbo_heat", False) or self._capabilities.get("turbo_cool", False)

    @property
    def display_control(self):
        return self._capabilities.get("light_control", False)

    @property
    def min_temperature(self):
        mode = ["cool", "auto", "heat"]
        return min([self._capabilities.get(f"{m}_min_temperature", 16) for m in mode])

    @property
    def max_temperature(self):
        mode = ["cool", "auto", "heat"]
        return max([self._capabilities.get(f"{m}_max_temperature", 30) for m in mode])

    @property
    def freeze_protection_mode(self):
        return self._capabilities.get("freeze_protection", False)


class state_response(response):
    def __init__(self, payload: memoryview):
        super().__init__(payload)

        self.power_on = None
        self.target_temperature = None
        self.operational_mode = None
        self.fan_speed = None
        self.swing_mode = None
        self.turbo_mode = None
        self.eco_mode = None
        self.sleep_mode = None
        self.fahrenheit = None
        self.indoor_temperature = None
        self.outdoor_temperature = None
        self.filter_alert = None
        self.display_on = None
        self.freeze_protection_mode = None

        _LOGGER.debug("State response payload: %s", payload.hex())

        self._parse(payload)

    def _parse(self, payload: memoryview):

        self.power_on = bool(payload[1] & 0x1)
        # self.imode_resume = payload[1] & 0x4
        # self.timer_mode = (payload[1] & 0x10) > 0
        # self.appliance_error = (payload[1] & 0x80) > 0

        # Unpack target temp and mode byte
        self.target_temperature = (payload[2] & 0xF) + 16.0
        self.target_temperature += 0.5 if payload[2] & 0x10 else 0.0
        self.operational_mode = (payload[2] >> 5) & 0x7

        # Fan speed
        # TODO Fan speed can be auto = 102, or value from 0 - 100
        # On my unit, Low == 40 (LED < 40), Med == 60 (LED < 60), High == 100 (LED < 100)
        self.fan_speed = payload[3]

        # on_timer_value = payload[4]
        # on_timer_minutes = payload[6]
        # self.on_timer = {
        #     'status': ((on_timer_value & 0x80) >> 7) > 0,
        #     'hour': (on_timer_value & 0x7c) >> 2,
        #     'minutes': (on_timer_value & 0x3) | ((on_timer_minutes & 0xf0) >> 4)
        # }

        # off_timer_value = payload[5]
        # off_timer_minutes = payload[6]
        # self.off_timer = {
        #     'status': ((off_timer_value & 0x80) >> 7) > 0,
        #     'hour': (off_timer_value & 0x7c) >> 2,
        #     'minutes': (off_timer_value & 0x3) | (off_timer_minutes & 0xf)
        # }

        # Swing mode
        self.swing_mode = payload[7] & 0xF

        # self.cozy_sleep = payload[8] & 0x03
        # self.save = (payload[8] & 0x08) > 0
        # self.low_frequency_fan = (payload[8] & 0x10) > 0
        self.turbo_mode = bool(payload[8] & 0x20)
        # self.feel_own = (payload[8] & 0x80) > 0

        self.eco_mode = bool(payload[9] & 0x10)
        # self.child_sleep_mode = (payload[9] & 0x01) > 0
        # self.exchange_air = (payload[9] & 0x02) > 0
        # self.dry_clean = (payload[9] & 0x04) > 0
        # self.aux_heat = (payload[9] & 0x08) > 0
        # self.clean_up = (payload[9] & 0x20) > 0
        # self.temp_unit = (payload[9] & 0x80) > 0

        self.sleep_mode = bool(payload[10] & 0x1)
        self.turbo_mode |= bool(payload[10] & 0x2)
        self.fahrenheit = bool(payload[10] & 0x4)
        # self.catch_cold = (payload[10] & 0x08) > 0
        # self.night_light = (payload[10] & 0x10) > 0
        # self.peak_elec = (payload[10] & 0x20) > 0
        # self.natural_fan = (payload[10] & 0x40) > 0

        self.indoor_temperature = (
            payload[11] - 50) / 2.0 if payload[11] != 0xff else None

        self.outdoor_temperature = (
            payload[12] - 50) / 2.0 if payload[12] != 0xff else None

        # self.humidity = (payload[13] & 0x7F)

        self.filter_alert = bool(payload[13] & 0x20)

        self.display_on = (payload[14] != 0x70)

        # TODO dudanov/MideaUART humidity set point in byte 19, mask 0x7F

        # TODO Some payloads are shorter than expected. Unsure what, when or why
        # This length was picked arbitrarily from one user's shorter payload
        if len(payload) < 22:
            return

        self.freeze_protection_mode = bool(payload[21] & 0x80)
