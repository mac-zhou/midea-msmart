
import logging
import datetime
import msmart.crc8 as crc8

VERSION = '0.1.25'

_LOGGER = logging.getLogger(__name__)


class base_command:

    def __init__(self, device_type=0xAC):
        # More magic numbers. I'm sure each of these have a purpose, but none of it is documented in english. I might make an effort to google translate the SDK
        self.data = bytearray([
            0xaa,
            # request is 0x20; setting is 0x23
            0x20,
            # device type
            0xac,
            0x00, 0x00, 0x00, 0x00, 0x00,
            0x00,
            # request is 0x03; setting is 0x02
            0x03,
            # Byte0 - Data request/response type: 0x41 - check status; 0x40 - Set up
            0x41,
            # Byte1
            0x81,
            # Byte2 - operational_mode
            0x00,
            # Byte3
            0xff,
            # Byte4
            0x03,
            # Byte5
            0xff,
            # Byte6
            0x00,
            # Byte7 - Room Temperature Request: 0x02 - indoor_temperature, 0x03 - outdoor_temperature
            # when set, this is swing_mode
            0x02,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            # Message ID
            0x00
        ])
        self.data[-1] = datetime.datetime.now().second
        self.data[0x02] = device_type

    def checksum(self, data):
        c = (~ sum(data) + 1) & 0xff
        return (~ sum(data) + 1) & 0xff

    def finalize(self):
        # Add the CRC8
        self.data.append(crc8.calculate(self.data[10:]))
        # Set the length of the command data
        # self.data[0x01] = len(self.data)
        # Add cheksum
        self.data.append(self.checksum(self.data[1:]))
        _LOGGER.debug("Finalize request data: {}".format(self.data.hex()))
        return self.data


class set_command(base_command):

    def __init__(self, device_type):
        base_command.__init__(self, device_type)
        self.data[0x01] = 0x23
        self.data[0x09] = 0x02
        # Set up Mode
        self.data[0x0a] = 0x40
        # prompt_tone
        self.data[0x0b] = 0x40
        self.data.extend(bytearray([0x00, 0x00, 0x00]))

    @property
    def prompt_tone(self):
        return self.data[0x0b] & 0x42

    @prompt_tone.setter
    def prompt_tone(self, feedback_anabled: bool):
        self.data[0x0b] &= ~ 0x42  # Clear the audible bits
        self.data[0x0b] |= 0x42 if feedback_anabled else 0

    @property
    def power_state(self):
        return self.data[0x0b] & 0x01

    @power_state.setter
    def power_state(self, state: bool):
        self.data[0x0b] &= ~ 0x01  # Clear the power bit
        self.data[0x0b] |= 0x01 if state else 0

    @property
    def target_temperature(self):
        return self.data[0x0c] & 0x1f

    @target_temperature.setter
    def target_temperature(self, temperature_celsius: float):
        # Clear the temperature bits.
        self.data[0x0c] &= ~ 0x0f
        # Clear the temperature bits, except the 0.5 bit, which will be set properly in all cases
        self.data[0x0c] |= (int(temperature_celsius) & 0xf)
        # set the +0.5 bit
        self.temperature_dot5 = (int(round(temperature_celsius*2)) % 2 != 0)

    @property
    def operational_mode(self):
        return (self.data[0x0c] & 0xe0) >> 5

    @operational_mode.setter
    def operational_mode(self, mode: int):
        self.data[0x0c] &= ~ 0xe0  # Clear the mode bit
        self.data[0x0c] |= (mode << 5) & 0xe0

    @property
    def fan_speed(self):
        return self.data[0x0d]

    @fan_speed.setter
    def fan_speed(self, speed: int):
        self.data[0x0d] = speed

    @property
    def eco_mode(self):
        return self.data[0x13] > 0

    @eco_mode.setter
    def eco_mode(self, eco_mode_enabled: bool):
        self.data[0x13] = 0xFF if eco_mode_enabled else 0

    @property
    def swing_mode(self):
        return self.data[0x11]

    @swing_mode.setter
    def swing_mode(self, mode: int):
        self.data[0x11] = 0x30  # Clear the mode bit
        self.data[0x11] |= mode & 0x3f

    @property
    def turbo_mode(self):
        return self.data[0x14] > 0

    @turbo_mode.setter
    def turbo_mode(self, turbo_mode_enabled: bool):
        if (turbo_mode_enabled):
            self.data[0x14] |= 0x02
        else:
            self.data[0x14] &= (~0x02)

    @property
    def screen_display(self):
        return self.data[0x14] & 0x10 > 0

    @screen_display.setter
    def screen_display(self, screen_display_enabled: bool):
        # the LED lights on the AC. these display temperature and are often too bright during nights
        if screen_display_enabled:
            self.data[0x14] |= 0x10
        else:
            self.data[0x14] &= (~0x10)

    @property
    def temperature_dot5(self):
        return self.data[0x0c] & 0x10 > 0

    @temperature_dot5.setter
    def temperature_dot5(self, temperature_dot5_enabled: bool):
        # add 0.5C to the temperature value. not intended to be called directly. target_temperature setter calls this if needed
        if temperature_dot5_enabled:
            self.data[0x0c] |= 0x10
        else:
            self.data[0x0c] &= (~0x10)

    @property
    def fahrenheit(self):
        # is the temperature unit fahrenheit? (celcius otherwise)
        return self.data[0x14] & 0x04 > 0

    @fahrenheit.setter
    def fahrenheit(self, fahrenheit_enabled: bool):
        # set the unit to fahrenheit from celcius
        if fahrenheit_enabled:
            self.data[0x14] |= 0x04
        else:
            self.data[0x14] &= (~0x04)


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
            if  int((self.data[11] - 50) /2) < -19  or int((self.data[11] - 50) /2) > 50:
                return 0xff
            else:
                indoorTempInteger = int((self.data[11] - 50) /2)
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
                if int((self.data[13] - 50) /2) < -19 or int((self.data[13] - 50) /2) > 50:
                    return 0xff
                else:
                    indoorTempInteger = int((self.data[13] - 50) /2)
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


def getBit(pByte, pIndex):
    return (pByte >> pIndex) & 0x01


def getBits(pBytes,pIndex,pStartIndex,pEndIndex):
    if pStartIndex > pEndIndex: 
        StartIndex = pEndIndex
        EndIndex = pStartIndex
    else:
        StartIndex = pStartIndex
        EndIndex = pEndIndex
    tempVal = 0x00;
    i = StartIndex
    while (i <= EndIndex):
        tempVal = tempVal | getBit(pBytes[pIndex],i) << (i-StartIndex)
        i += 1 
    return tempVal