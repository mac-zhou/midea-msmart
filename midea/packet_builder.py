import midea.crc8 as crc8
from midea.command import base_command

class packet_builder:

    def __init__(self):
        self.command = None

        # Init the packet with the header data. Weird magic numbers (packet length at 0x4)
        self.packet = bytearray([
            0x5a, 0x5a, 0x01, 0x11, 0x5c, 0x00, 0x20, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x0e, 0x03, 0x12, 0x14, 0xc6, 0x79, 0x00, 0x00, 
            0x00, 0x05, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 
            0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00
        ])
        
    def set_command(self, command: base_command):
        self.command = command.finalize()

    def finalize(self):
        self.packet.extend(self.command)
         #$## This is not supposed to be a CRC, its another type of checksum FFS
        self.packet.extend([self.checksum(self.command[1:])])
        self.packet.extend([0] * (46 - len(self.command))) # MORE WTF...
        self.packet[0x04] = len(self.packet)
        print("PACKET OUTPUT ------------------------------------------>")
        print(self.packet.hex())
        return self.packet

    def checksum(self, data):
        return 255 - sum(data) % 256 + 1
