
import logging
from msmart.command import base_command
from msmart.security import security
import datetime

VERSION = '0.1.17'

_LOGGER = logging.getLogger(__name__)


class packet_builder:

    def __init__(self, device_id):
        self.command = None
        self.security = security()
        # aa20ac00000000000003418100ff03ff000200000000000000000000000006f274
        # Init the packet with the header data.
        self.packet = bytearray([
            # 2 bytes - StaicHeader
            0x5a, 0x5a,
            # 2 bytes - mMessageType
            0x01, 0x11,
            # 1 bytes - PacketLenght
            0x68,
            # 3 bytes
            0x00, 0x20, 0x00,
            # 4 bytes - MessageId
            0x00, 0x00, 0x00, 0x00,
            # 8 bytes - Date&Time
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # 6 bytes - mDeviceID
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # 14 bytes
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        _LOGGER.debug("add packet_time")
        self.packet[12:20] = self.packet_time()
        self.packet[20:26] = bytearray.fromhex(device_id)

    def set_command(self, command: base_command):
        self.command = command.finalize()

    def finalize(self):
        # Add cheksum
        self.command.append(self.checksum(self.command[1:]))
        _LOGGER.debug("Finalize request data: {}".format(self.command.hex()))
        # Append the command data(48 bytes) to the packet
        self.packet.extend(self.security.aes_encrypt(self.command)[:48])
        # Set the packet length in the packet!
        self.packet[0x04] = len(self.packet) + 16
        # Append a basic checksum data(16 bytes) to the packet
        self.packet.extend(self.encode32(self.packet))
        return self.packet

    def encode32(self, data):
        # 16 bytes encode32
        return self.security.encode32_data(data)

    def checksum(self, data):
        return 255 - sum(data) % 256 + 1

    def packet_time(self):
        t = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[
            :16]
        b = bytearray()
        for i in range(0, len(t), 2):
            d = int(t[i:i+2])
            b.insert(0, d)
        return b
