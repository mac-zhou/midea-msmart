
import midea.crc8 as crc8
from midea.device import operational_mode as operational_mode_enum
from midea.device import fan_speed as fan_speed_enum
from midea.device import swing_mode as swing_mode_enum
import base64


class base_command:

    def __init__(self, device_type=0xAC):
        # More magic numbers. I'm sure each of these have a purpose, but none of it is documented in english. I might make an effort to google translate the SDK
        self.data = bytearray([
            0xaa, 0x23, 0xAC, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x03, 0x02, 0x40, 0x81, 0x00, 0xff, 0x03, 0xff,
            0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00
        ])
        self.data[0x02] = device_type

    def finalize(self):
        # Fill the data with the actual command data
        self.fill()

        print(self.data[0x0b])
        # Magic 3!
        self.data.extend([3])
        # Add the CRC8
        self.data.extend([crc8.calculate(self.data[16:])])
        # Set the length of the command data
        self.data[1] = len(self.data)
        return self.data

    def fill(self):
        pass


class request_status_command(base_command):
    def fill(self):
        return


class set_command(base_command):

    def __init__(self):
        base_command.__init__(self, device_type=0xAC)
        # It seems that at a minimum, the AC needs the Power Status, Temperature, Mode and fan speed set before it responds to anything.
        self._power_status = False
        self._target_temperature = 21
        self._operational_mode = operational_mode_enum.AUTO
        self._fan_speed = fan_speed_enum.AUTO
        self._swing_mode = None
        self._eco_mode = None
        self._turbo_mode = None

        # I love this bit. My AC is so noisy via the app and the remote, if this is set to false, the changes will be applied SILENTLY!
        # Default this to false, those sounds are annoying as hell!
        self._audible_feedback = False
        # TBD: Timer setting

    def power_status(self, state: bool):
        self._power_status = state

    def target_temperature(self, temperature_celsius: int):
        self._target_temperature = temperature_celsius

    def operational_mode(self, mode: operational_mode_enum):
        self._operational_mode = mode

    def fan_speed(self, speed: fan_speed_enum):
        self._fan_speed = speed

    def eco_mode(self, eco_mode_enabled: bool):
        self._eco_mode = eco_mode_enabled

    def swing_mode(self, mode: swing_mode_enum):
        self._swing_mode = mode

    def turbo_mode(self, turbo_mode_enabled: bool):
        self._turbo_mode = turbo_mode_enabled

    def audible_feedback(self, feedback_anabled: bool):
        self._audible_feedback = feedback_anabled

    def fill(self):
        data = self.data

        data[0x0b] &= ~ 0x01  # Clear the power bit
        if self._power_status:
            data[0x0b] |= 0x01

        data[0x0b] &= ~ 0x42  # Clear the audible bits
        if self._audible_feedback:
            data[0x0b] |= 0x42

        print(data[0x0c])

        data[0x0c] &= ~ 0xe0  # Clear the mode bit
        data[0x0c] |= (self._operational_mode.value << 5) & 0xE0

        data[0x0c] &= ~ 0x1f  # Clear the temperature bits
        data[0x0c] |= (self._target_temperature & 0xf) | (
            (self._target_temperature << 4) & 0x10)

        data[0x0d] = self._fan_speed.value

        data[0x11] = self._swing_mode.value if self._swing_mode else 0

        data[0x13] = 0xFF if self._eco_mode else 0

        data[0x14] = 0x02 if self._turbo_mode else 0

        return
