
import midea.crc8 as crc8
import base64

class base_command:
    
    def __init__(self, device_type = 0xAC):
        self.data = bytearray([
          0xaa, 0x23, 0xAC, 0x00, 0x00, 0x00, 0x00, 0x00,
          0x03, 0x02, 0xff, 0x81, 0x00, 0xff, 0x03, 0xff,
          0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00
        ])
        self.data[0x02] = device_type

        self.fill()

    def finalize(self):
        self.data.extend([3])
        self.data.extend([crc8.calculate(self.data[16:])])
        self.data[1] = len(self.data)
        return self.data

    def fill(self):
        pass


class request_status_command(base_command):
    def fill(self):
        self.data[0xa] = 0x40