
from enum import IntEnum
import logging
from abc import ABC, abstractmethod
import math
import msmart.crc8 as crc8
from msmart.utils import getBits

VERSION = '0.2.3'

_LOGGER = logging.getLogger(__name__)


class temperature_type(IntEnum):
    Unknown = 0
    Indoor = 0x2
    Outdoor = 0x3


class frame_type(IntEnum):
    Unknown = 0
    Set = 0x2
    Request = 0x3


class command(ABC):
    device_type = 0
    protocol_version = 0
    frame_type = frame_type.Unknown

    _message_id = 0

    def __init__(self, device_type=0xAC, frame_type=frame_type.Request):
        self.device_type = device_type
        self.frame_type = frame_type

    def pack(self):
        # Create payload with CRC appended
        payload_crc = self.payload + bytes([crc8.calculate(self.payload)])

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
        self._message_id = (self._message_id + 1) & 0xFF
        return self._message_id

    @property
    @abstractmethod
    def payload(self):
        return bytes()


class get_state_command(command):
    temperature_type = temperature_type.Indoor

    def __init__(self, device_type):
        super().__init__(device_type, frame_type=frame_type.Request)

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
            # Message ID
            self.message_id
        ])


class set_state_command(command):
    beep_on = True
    power_on = False
    target_temperature = 25.0
    operational_mode = 0
    fan_speed = 0
    eco_mode = True
    swing_mode = 0
    turbo_mode = False
    display_on = True
    fahrenheit = True

    def __init__(self, device_type):
        super().__init__(device_type, frame_type=frame_type.Set)

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
            # Message ID
            self.message_id
        ])


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
