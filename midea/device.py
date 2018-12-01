from enum import Enum

pointer = 0x33

class fan_speed(Enum):
    UNSET = 101
    AUTO = 102
    HIGH = 80
    MEDIUM = 60
    LOW = 40
    SILENT = 20

class operational_mode(Enum):
    AUTO = 1
    COOL = 2
    DRY = 3
    HEAT = 4
    FAN = 5

# There should be more option possible, but my AC only has one setting for vertical
class swing_mode(Enum):
    OFF = 0
    ON = 0x3C

class device:

    def __init__(self, data: bytes):
        self.update(data)
    
    def update(self, data):
        self.data = data
        self.status = {
            'power_status': self.power_status(),
            'target_temperature': self.target_temperature(),
            'operational_mode': self.operational_mode(),
            'fan_speed': self.fan_speed(),
            'indoor_temperature': self.indoor_temperature(),
            'outdoor_temperature': self.outdoor_temperature(),
            'eco_mode': self.eco_mode(),
            'swing_mode': self.swing_mode(),
            'turbo_mode': self.turbo_mode(),
            'on_timer': self.on_timer(),
            'off_timer': self.off_timer()
        }

    def power_status(self):
        return (self.data[pointer] & 0x1) > 0

    def target_temperature(self):
        return (self.data[pointer + 1] & 0xF) + 16

    def operational_mode(self):
        return operational_mode((self.data[pointer + 1] & 0xe0) >> 5)

    def fan_speed(self):
        return fan_speed(self.data[pointer + 2] & 0x7f)

    def indoor_temperature(self):
        return (self.data[pointer + 10] - 50) / 2.0

    def outdoor_temperature(self):
        return (self.data[pointer + 11] - 50) / 2.0

    def eco_mode(self):
        return (self.data[pointer + 8] & 0x10) >> 4

    def swing_mode(self):
        return swing_mode(self.data[pointer + 6] & 0xff)

    def turbo_mode(self):
        return (self.data[pointer + 9] & 0x2) > 0

    def on_timer(self):
        value = self.data[pointer + 3]

        return {
            'status': ((value & 0x80) >> 7) > 0,
            'hour': ((value & 0x7c) >> 2),
            'minutes': ((value & 0x3) | ((value & 0xf0)))
        }
        
    def off_timer(self):
        value = self.data[pointer + 4]

        return {
            'status': ((value & 0x80) >> 7) > 0,
            'hour': ((value & 0x7c) >> 2),
            'minutes': ((value & 0x3) | ((value & 0xf0)))
        }