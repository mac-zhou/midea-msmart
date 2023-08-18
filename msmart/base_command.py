import logging
from abc import ABC, abstractmethod

import msmart.crc8 as crc8
from msmart.const import FrameType

_LOGGER = logging.getLogger(__name__)


class Command(ABC):
    _message_id = 0

    def __init__(self, device_type=0xAC, frame_type=FrameType.REQUEST):
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
        frame.append(Command.checksum(frame[1:]))

        _LOGGER.debug("Frame data: %s", frame.hex())

        return frame

    @staticmethod
    def checksum(frame):
        return (~sum(frame) + 1) & 0xFF

    @property
    def message_id(self):
        Command._message_id += 1
        return Command._message_id & 0xFF

    @property
    @abstractmethod
    def payload(self):
        return bytes()
