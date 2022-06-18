
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import IntEnum
import logging
import math
import msmart.crc8 as crc8
from msmart.utils import getBits
import struct

VERSION = '0.2.3'

_LOGGER = logging.getLogger(__name__)


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


class frame_type(IntEnum):
    Unknown = 0
    Set = 0x2
    Request = 0x3


class command(ABC):
    _message_id = 0

    def __init__(self, device_type=0xAC, frame_type=frame_type.Request):
        self.device_type = device_type
        self.frame_type = frame_type
        self.protocol_version = 0

    def pack(self):
        # Create payload with message id
        payload = self.payload + bytes([self.message_id])

        # Create payload with CRC appended
        payload_crc = payload + bytes([crc8.calculate(payload)])

        # Length includes header, payload and CRC
        length = 10 + len(payload_crc)

        # Build frame header
        header = bytearray([
            # Start byte
            0xAA,
            # Length of payload and header
            length,
            # Device/appliance type
            self.device_type,
            # Frame checksum (sync?)
            self.device_type ^ length,
            # Reserved
            0x00, 0x00,
            # Frame ID
            0x00,
            # Frame protocol version
            0x00,
            # Device protocol version
            self.protocol_version,
            # Frame type
            self.frame_type
        ])

        # Build frame from header and payload with CRC
        frame = header + payload_crc

        # Calculate total frame checksum
        frame.append(command.checksum(frame))

        _LOGGER.debug("Frame data: {}".format(frame.hex()))

        return frame

    @staticmethod
    def checksum(frame):
        return (~sum(frame[1:]) + 1) & 0xFF

    @property
    def message_id(self):
        command._message_id += 1
        return command._message_id & 0xFF

    @property
    @abstractmethod
    def payload(self):
        return bytes()


class get_capabilities_command(command):
    def __init__(self, device_type):
        super().__init__(device_type, frame_type=frame_type.Request)

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
        super().__init__(device_type, frame_type=frame_type.Request)

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
        super().__init__(device_type, frame_type=frame_type.Set)

        self.beep_on = True
        self.power_on = False
        self.target_temperature = 25.0
        self.operational_mode = 0
        self.fan_speed = 0
        self.eco_mode = True
        self.swing_mode = 0
        self.turbo_mode = False
        self.display_on = True
        self.fahrenheit = True
        self.sleep = False

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
        eco_mode = 0xFF if self.eco_mode else 0

        # Build turbo, display and fahrenheit byte
        turbo = 0x02 if self.turbo_mode else 0
        display = 0x10 if self.display_on else 0
        fahrenheit = 0x04 if self.fahrenheit else 0

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
            # Unknown
            0x00,  # TODO Alternate turbo mode?
            # ECO mode
            eco_mode,
            # Turbo mode, display on and fahrenheit
            turbo | display | fahrenheit,  # TODO Sleep bit?
            # Unknown
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00,
        ])


class response(ABC):
    def __init__(self, frame: bytes):
        # Build a memoryview of the frame for zero-copy slicing
        frame_mv = memoryview(frame)

        # Validate frame checksum
        calc_checksum = command.checksum(frame_mv[0:-1])
        recv_checkum = frame_mv[-1]
        if recv_checkum != calc_checksum:
            _LOGGER.error("Frame '{}' failed checksum. Received: 0x{:X}, Expected: 0x{:X}.".format(
                frame_mv.hex(), recv_checkum, calc_checksum))
            frame_mv.release()
            return

        # Fetch frame payload and payload with CRC
        payload_crc = frame_mv[10:-1]
        payload = payload_crc[0:-1]

        # Validate payload CRC
        calc_crc = crc8.calculate(payload)
        recv_crc = payload_crc[-1]
        if recv_crc != calc_crc:
            _LOGGER.error("Payload '{}' failed CRC. Received: 0x{:X}, Expected: 0x{:X}.".format(
                payload_crc.hex(), recv_crc, calc_crc))
            frame_mv.release()
            return

        # Get ID
        self._id = payload[0]

        # Unpack the payload
        self.unpack(payload)

        # Free the memoryview
        frame_mv.release()

    @property
    def id(self):
        return self._id

    @abstractmethod
    def unpack(self, payload: memoryview):
        return


class capabilities_response(response):
    def __init__(self, frame: bytes):
        super().__init__(frame)

    def unpack(self, payload: memoryview):
        if self.id != 0xB5:
            # TODO throw instead?
            _LOGGER.error(
                "Invalid capabilities response ID.")
            return

        _LOGGER.debug(
            "Capabilities response payload: {}".format(payload.hex()))

        self.read_capabilities(payload)

    def read_capabilities(self, payload: memoryview):
        # Clear existing capabilities
        self.capabilities = {}

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
            CapabilityId.FanSpeedControl: reader("fan_speed_control", get_no_value(1)),
            CapabilityId.PresetEco: [
                reader("eco_mode", get_value(1)),
                reader("eco_mode_2", get_value(2)),
            ],
            CapabilityId.PresetFreezeProtection: reader("freeze_protection", get_value(1)),
            CapabilityId.Modes: [
                reader("heat_mode", lambda v: v == 1 or v == 2),
                reader("cool_mode", lambda v: v == 0 or v == 3),
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

            # Covert ID to enumerate type
            try:
                # Unpack 16 bit ID
                (cap_id, ) = struct.unpack("<H", caps[0:2])
                id = CapabilityId(cap_id)
            except ValueError:
                _LOGGER.warn(
                    "Unknown capability. ID: 0x{:04X}, Size: {}.".format(id, size))
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
                        self.capabilities.update(apply(r))
                else:
                    # Apply the single reader
                    self.capabilities.update(apply(reader))

            elif id == CapabilityId.Temperatures:
                # Skip if capability size is too small
                if size < 6:
                    continue

                self.capabilities["min_cool_temperature"] = caps[3] * 0.5
                self.capabilities["max_cool_temperature"] = caps[4] * 0.5
                self.capabilities["min_auto_temperature"] = caps[5] * 0.5
                self.capabilities["max_auto_temperature"] = caps[6] * 0.5
                self.capabilities["min_heat_temperature"] = caps[7] * 0.5
                self.capabilities["max_heat_temperature"] = caps[8] * 0.5

                self.capabilities["decimals"] = caps[9] == 0 if size > 6 else caps[2] == 0

            else:
                _LOGGER.warn(
                    "Unsupported capability. ID: 0x{:04X}, Size: {}.".format(id, size))

            # Advanced to next capability
            caps = caps[3+size:]


class appliance_response:

    def __init__(self, data: bytearray):
        # The response data from the appliance includes a packet header which we don't want
        self.data = data[0xa:]
        _LOGGER.debug("Appliance response data: {}".format(self.data.hex()))

    # Byte 0x01
    @property
    def power_state(self):
        return (self.data[0x01] & 0x1) > 0

    @property
    def imode_resume(self):
        return (self.data[0x01] & 0x4) > 0

    @property
    def timer_mode(self):
        return (self.data[0x01] & 0x10) > 0

    @property
    def appliance_error(self):
        return (self.data[0x01] & 0x80) > 0

    # Byte 0x02
    @property
    def target_temperature(self):
        return (self.data[0x02] & 0xf) + 16.0 + (0.5 if self.data[0x02] & 0x10 > 0 else 0.0)

    @property
    def operational_mode(self):
        return (self.data[0x02] & 0xe0) >> 5

    # Byte 0x03
    @property
    def fan_speed(self):
        return self.data[0x03] & 0x7f

    # Byte 0x04 + 0x06
    @property
    def on_timer(self):
        on_timer_value = self.data[0x04]
        on_timer_minutes = self.data[0x06]
        return {
            'status': ((on_timer_value & 0x80) >> 7) > 0,
            'hour': (on_timer_value & 0x7c) >> 2,
            'minutes': (on_timer_value & 0x3) | ((on_timer_minutes & 0xf0) >> 4)
        }

    # Byte 0x05 + 0x06
    @property
    def off_timer(self):
        off_timer_value = self.data[0x05]
        off_timer_minutes = self.data[0x06]
        return {
            'status': ((off_timer_value & 0x80) >> 7) > 0,
            'hour': (off_timer_value & 0x7c) >> 2,
            'minutes': (off_timer_value & 0x3) | (off_timer_minutes & 0xf)
        }

    # Byte 0x07
    @property
    def swing_mode(self):
        return self.data[0x07] & 0x0f

    # Byte 0x08
    @property
    def cozy_sleep(self):
        return self.data[0x08] & 0x03

    @property
    def save(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x08] & 0x08) > 0

    @property
    def low_frequency_fan(self):
        return (self.data[0x08] & 0x10) > 0

    @property
    def super_fan(self):
        return (self.data[0x08] & 0x20) > 0

    @property
    def feel_own(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x08] & 0x80) > 0

    # Byte 0x09
    @property
    def child_sleep_mode(self):
        return (self.data[0x09] & 0x01) > 0

    @property
    def exchange_air(self):
        return (self.data[0x09] & 0x02) > 0

    @property
    def dry_clean(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x09] & 0x04) > 0

    @property
    def aux_heat(self):
        return (self.data[0x09] & 0x08) > 0

    @property
    def eco_mode(self):
        return (self.data[0x09] & 0x10) > 0

    @property
    def clean_up(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x09] & 0x20) > 0

    @property
    def temp_unit(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x09] & 0x80) > 0

    # Byte 0x0a
    @property
    def sleep_function(self):
        return (self.data[0x0a] & 0x01) > 0

    @property
    def turbo_mode(self):
        return (self.data[0x0a] & 0x02) > 0

    @property
    def catch_cold(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x08) > 0

    @property
    def night_light(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x10) > 0

    @property
    def peak_elec(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x20) > 0

    @property
    def natural_fan(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x40) > 0

    # Byte 0x0b
    @property
    def indoor_temperature(self):
        if self.data[0] == 0xc0:
            if int((self.data[11] - 50) / 2) < -19 or int((self.data[11] - 50) / 2) > 50:
                return 0xff
            else:
                indoorTempInteger = int((self.data[11] - 50) / 2)
            indoorTemperatureDot = getBits(self.data, 15, 0, 3)
            indoorTempDecimal = indoorTemperatureDot * 0.1
            if self.data[11] > 49:
                return indoorTempInteger + indoorTempDecimal
            else:
                return indoorTempInteger - indoorTempDecimal
        if self.data[0] == 0xa0 or self.data[0] == 0xa1:
            if self.data[0] == 0xa0:
                if (self.data[1] >> 2) - 4 == 0:
                    indoorTempInteger = -1
                else:
                    indoorTempInteger = (self.data[1] >> 2) + 12
                if (self.data[1] >> 1) & 0x01 == 1:
                    indoorTempDecimal = 0.5
                else:
                    indoorTempDecimal = 0
            if self.data[0] == 0xa1:
                if int((self.data[13] - 50) / 2) < -19 or int((self.data[13] - 50) / 2) > 50:
                    return 0xff
                else:
                    indoorTempInteger = int((self.data[13] - 50) / 2)
                indoorTempDecimal = (self.data[18] & 0x0f) * 0.1
            if int(self.data[13]) > 49:
                return indoorTempInteger + indoorTempDecimal
            else:
                return indoorTempInteger - indoorTempDecimal
        return 0xff

    # Byte 0x0c
    @property
    def outdoor_temperature(self):
        return (self.data[0x0c] - 50) / 2.0

    # Byte 0x0d
    @property
    def humidity(self):
        return (self.data[0x0d] & 0x7f)
