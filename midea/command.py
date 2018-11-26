
import midea.crc8 as crc8
import base64

class base_command:
    
    def __init__(self, device_type = 0xAC):
        # More magic numbers. I'm sure each of these have a purpose, but none of it is documented in english. I might make an effort to google translate the SDK
        self.data = bytearray([
          0xaa, 0x23, 0xAC, 0x00, 0x00, 0x00, 0x00, 0x00,
          0x03, 0x02, 0xff, 0x81, 0x00, 0xff, 0x03, 0xff,
          0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00
        ])
        self.data[0x02] = device_type

        # Fill the data with the actual command data
        self.fill()

    def finalize(self):
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
        # Luckily a request status command is obviously a 0x40 and only that at position 0x0A. I think that position hold the command type
        self.data[0xa] = 0x40