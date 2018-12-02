
import midea.crc8 as crc8

class base_command:

    def __init__(self, device_type=0xAC):
        # More magic numbers. I'm sure each of these have a purpose, but none of it is documented in english. I might make an effort to google translate the SDK
        self.data = bytearray([
            0xaa, 0x23, 0xAC, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x03, 0x02, 0x40, 0x81, 0x00, 0xff, 0x03, 0xff,
            0x00, 0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x03, 0xcc
        ])
        self.data[0x02] = device_type

    def finalize(self):
        # Add the CRC8
        self.data[0x1d] = crc8.calculate(self.data[16:])
        # Set the length of the command data
        self.data[0x01] = len(self.data)
        return self.data

class set_command(base_command):

    def __init__(self, device_type):
        base_command.__init__(self, device_type)

    @property
    def audible_feedback(self):
        return self.data[0x0b] & 0x42

    @audible_feedback.setter
    def audible_feedback(self, feedback_anabled: bool):
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
    def target_temperature(self, temperature_celsius: int):
        self.data[0x0c] &= ~ 0x1f  # Clear the temperature bits
        self.data[0x0c] |= (temperature_celsius & 0xf) | (
            (temperature_celsius << 4) & 0x10)
    
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
        self.data[0x11] &= ~ 0x0f  # Clear the mode bit
        self.data[0x11] |= mode & 0x0f

    @property
    def turbo_mode(self):
        return self.data[0x14] > 0

    @turbo_mode.setter
    def turbo_mode(self, turbo_mode_enabled: bool):
        self.data[0x14] = 0x02 if turbo_mode_enabled else 0

class appliance_response:

    def __init__(self, data: bytearray):
        # The response data from the appliance includes a packet header which we don't want
        self.data = data[0x28:]

    @property
    def audible_feedback(self):
        return self.data[0x0b] & 0x42 > 0

    @property
    def power_state(self):
        return (self.data[0x0b] & 0x1) > 0

    @property
    def target_temperature(self):
        return (self.data[0x0c] & 0xF) + 16

    @property
    def operational_mode(self):
        return (self.data[0x0c] & 0xe0) >> 5

    @property
    def fan_speed(self):
        return self.data[0x0d] & 0x7f

    @property
    def indoor_temperature(self):
        return (self.data[0x15] - 50) / 2.0

    @property
    def outdoor_temperature(self):
        return (self.data[0x16] - 50) / 2.0

    @property
    def eco_mode(self):
        return (self.data[0x13] & 0x10) > 0

    @property
    def swing_mode(self):
        return self.data[0x11] & 0x0f

    @property
    def turbo_mode(self):
        return (self.data[0x14] & 0x2) > 0

    @property
    def on_timer(self):
        on_timer_value = self.data[0x0e]
        return {
            'status': ((on_timer_value & 0x80) >> 7) > 0,
            'hour': ((on_timer_value & 0x7c) >> 2),
            'minutes': ((on_timer_value & 0x3) | ((on_timer_value & 0xf0)))
        }

    @property
    def off_timer(self):
        off_timer_value = self.data[0x0f]
        return {
            'status': ((off_timer_value & 0x80) >> 7) > 0,
            'hour': ((off_timer_value & 0x7c) >> 2),
            'minutes': ((off_timer_value & 0x3) | ((off_timer_value & 0xf0)))
        }
    
