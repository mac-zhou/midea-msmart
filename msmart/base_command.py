import logging
from abc import ABC, abstractmethod

import msmart.crc8 as crc8
from msmart.const import DeviceType, FrameType

_LOGGER = logging.getLogger(__name__)


class Command(ABC):
    _message_id = 0

    def __init__(self, device_type: DeviceType, frame_type: FrameType) -> None:
        self._device_type = device_type
        self._frame_type = frame_type
        self._protocol_version = 0

    def tobytes(self) -> bytes:
        # Create payload with message id
        payload = self.payload + bytes([self._next_message_id()])

        # Create payload with CRC appended
        payload_crc = payload + bytes([crc8.calculate(payload)])

        # Length includes header, payload and CRC
        length = 10 + len(payload_crc)

        # Build frame header
        header = bytes([
            # Start byte
            0xAA,
            # Length of payload and header
            length,
            # Device/appliance type
            self._device_type,
            # Frame checksum (sync?)
            self._device_type ^ length,
            # Reserved
            0x00, 0x00,
            # Frame ID
            0x00,
            # Frame protocol version
            0x00,
            # Device protocol version
            self._protocol_version,
            # Frame type
            self._frame_type
        ])

        # Build frame from header and payload with CRC
        frame = bytearray(header + payload_crc)

        # Calculate total frame checksum
        frame.append(Command.checksum(frame[1:]))

        return bytes(frame)

    def _next_message_id(self) -> int:
        Command._message_id += 1
        return Command._message_id & 0xFF

    @property
    @abstractmethod
    def payload(self) -> bytes:
        return bytes()

    @classmethod
    def checksum(cls, frame: bytes) -> int:
        return (~sum(frame) + 1) & 0xFF
