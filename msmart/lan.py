"""Module for local network control of Midea AC devices."""
import asyncio
import logging
import struct
from datetime import datetime
from enum import IntEnum
from hashlib import md5, sha256
from typing import List, Optional, Union, cast

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util import Padding
from Crypto.Util.strxor import strxor

Token = Union[str, bytes, None]
Key = Union[str, bytes, None]

_LOGGER = logging.getLogger(__name__)


class ProtocolError(Exception):
    pass


class AuthenticationError(ProtocolError):
    pass


class _LanProtocol(asyncio.Protocol):
    """Midea LAN protocol."""

    # V2 Packet Overview
    #
    # Header: 40 bytes
    #  2 byte start of packet: 0x5A5A
    #  2 byte message type: 0x0111
    #  2 byte packet length
    #  2 byte magic bytes: Usually 0x2000, special responses differ
    #  4 byte message ID
    #  8 byte timestamp
    #  8 byte device ID
    #  12 byte ???
    #
    # Payload: N bytes
    #  N byte data payload contains encrypted frame
    #
    # Sign: 16 bytes
    #   16 byte MD5 of packet + fixed key
    #

    def __init__(self) -> None:
        self._transport = None

        self._peer = None
        self._queue = asyncio.Queue()

    @property
    def peer(self) -> Optional[str]:
        return self._peer

    @property
    def alive(self) -> bool:
        if self._transport is None or self._transport.is_closing():
            return False

        return True

    def _format_socket_name(self, sockname) -> str:
        def _format(addr, port):
            return f"{addr}:{port}"
        return _format(*sockname)

    def connection_made(self, transport) -> None:
        """Handle connection events."""

        transport = cast(asyncio.Transport, transport)

        # Save transport for later
        self._transport = transport

        # Save peer name for logging
        peername = transport.get_extra_info('peername')
        self._peer = self._format_socket_name(peername)

        _LOGGER.debug("Connected to %s.", self._peer)

    def data_received(self, data: bytes) -> None:
        """Handle data received events."""

        _LOGGER.debug("Received data from %s: %s", self.peer, data.hex())
        self._queue.put_nowait(data)

    def connection_lost(self, exc) -> None:
        """Log connection lost."""
        if exc:
            _LOGGER.error("Connection to %s lost. Error: %s", self.peer, exc)

    def disconnect(self) -> None:
        """Disconnect from the peer."""
        if self._transport is None:
            raise IOError()  # TODO better?

        _LOGGER.debug("Disconnecting from %s.", self.peer)
        self._transport.close()

    def write(self, data: bytes) -> None:
        """Send data to the peer."""

        if self._transport is None:
            raise IOError()  # TODO better

        if not self.alive:
            raise ProtocolError("Transport is closing or closed.")

        _LOGGER.debug("Sending data to %s: %s", self.peer, data.hex())
        self._transport.write(data)

    async def _read_queue(self, timeout: int = 2) -> bytes:
        """Read data from the receive queue."""

        if timeout == 0:
            return self._queue.get_nowait()

        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    async def read(self, timeout: int = 2) -> bytes:
        """Asynchronously read data from the peer via the queue."""

        # Fetch a packet from the queue
        return await self._read_queue(timeout=timeout)


class _LanProtocolV3(_LanProtocol):
    """Midea LAN protocol V3."""

    class PacketType(IntEnum):
        HANDSHAKE_REQUEST = 0x0
        HANDSHAKE_RESPONSE = 0x1
        ENCRYPTED_RESPONSE = 0x3
        ENCRYPTED_REQUEST = 0x6
        ERROR = 0xF

    # V3 Packet Overview
    #
    # Header: 6 bytes
    #  2 byte start of packet: 0x8370
    #  2 byte size of data payload, padding and sign
    #  1 special byte: 0x20
    #  1 padding and type byte: pad << 4 | type
    #
    # Payload: N + 2 bytes
    #  2 byte request ID/count
    #  N byte data payload
    #
    # Sign: 32 bytes
    #   32 byte SHA256 of header + unencrypted payload
    #
    # Notes
    #  - For padding purposes the 2 byte request ID is included in size,
    #    but not in the size field
    #  - When used for device command/response, the payload contains a V2 packet

    def __init__(self) -> None:
        super().__init__()

        self._packet_id = 0
        self._buffer = bytearray(0)
        self._local_key = None

    def data_received(self, data: bytes) -> None:
        """Handle data received events."""

        _LOGGER.debug("Received data from %s: %s", self.peer, data.hex())

        # Add incoming data to buffer
        self._buffer += data

        # Process buffer until empty
        while len(self._buffer) > 0:
            # Find start of packet
            start = self._buffer.find(b"\x83\x70")
            if start == -1:
                _LOGGER.warning(
                    "No start of packet found. Buffer: %s", self._buffer.hex())
                return

            # Create a memoryview for zero copy slicing
            with memoryview(self._buffer) as buf:
                if start != 0:
                    _LOGGER.warning(
                        "Ignoring data before packet: %s", buf[:start].hex())

                # Trim any leading data
                buf = buf[start:]

                # Check if the header has been received
                if len(buf) < 6:
                    _LOGGER.warning("Buffer too short. Buffer: %s", buf.hex())
                    return

                # 6 byte header + 2 packet id + padded encrypted payload
                total_size = int.from_bytes(buf[2:4], "big") + 8

                # Ensure entire packet is received
                if len(buf) < total_size:
                    _LOGGER.warning(
                        "Partial packet received. Buffer: %s", buf.hex())
                    return

                # Extract the packet from the buffer
                packet, self._buffer = buf[:total_size], bytearray(
                    buf[total_size:])

                # Queue the received packet
                self._queue.put_nowait(packet.tobytes())

    def _decode_encrypted_response(self, packet: memoryview) -> bytes:
        """Decode an encrypted response packet."""

        # We should always have a key by the time we're received data
        assert self._local_key is not None

        # Extract header, encrypted payload and hash
        header = packet[:6]
        payload = packet[6:-32]
        rx_hash = packet[-32:]

        # Decrypt payload
        decrypted_payload = Security.decrypt_aes_cbc(self._local_key, payload)

        # TODO could padding module handle this padding?

        # Verify hash
        if sha256(bytes(header) + decrypted_payload).digest() != rx_hash:
            raise ProtocolError(
                "Calculated and received SHA256 digest do not match.")

        with memoryview(decrypted_payload) as payload:
            # Decrypted payload consists of 2 byte packet ID + actual payload + padding

            # Get pad count from header
            pad = header[5] >> 4

            # Get the frame from payload
            return payload[2:-pad].tobytes()

    def _decode_handshake_response(self, packet: memoryview) -> bytes:
        """Decode a handshake response packet."""

        # Get payload from packet
        payload = packet[6:]

        # Return remaining raw payload
        return payload[2:].tobytes()

    def _process_packet(self, packet: memoryview) -> bytes:
        """Process a received packet based on its type."""

        if packet[:2] != b"\x83\x70":
            raise ProtocolError(
                f"Invalid start of packet: {packet[:2].hex()}")

        if packet[4] != 0x20:
            raise ProtocolError(
                f"Invalid magic byte: 0x{packet[4]:X}")

        # Handle packet based on type
        packet_type = packet[5] & 0xF
        if packet_type == self.PacketType.ENCRYPTED_RESPONSE:
            return self._decode_encrypted_response(packet)
        elif packet_type == self.PacketType.HANDSHAKE_RESPONSE:
            return self._decode_handshake_response(packet)
        elif packet_type == self.PacketType.ERROR:
            raise ProtocolError("Error packet received.")
        else:
            raise ProtocolError(f"Unexpected type: {packet_type}")

    async def read(self, timeout: int = 2) -> bytes:
        """Asynchronously read data from the peer via the queue."""

        # Fetch a packet from the queue
        packet = await self._read_queue(timeout=timeout)

        with memoryview(packet) as packet_mv:
            return self._process_packet(packet_mv)

    def _build_header(self, length: int, extra: bytes) -> bytes:
        # Build header
        header = b"\x83\x70"
        header += length.to_bytes(2, "big")
        header += b"\x20"
        header += extra

        return header

    def _encode_encrypted_request(self, packet_id: int, data: bytes) -> bytes:
        """Encode an encrypted request packet."""

        # We should always have a key before sending data
        assert self._local_key is not None

        # Compute required padding for 16 byte alignment
        # Include 2 bytes for packet ID in total length
        remainder = (len(data) + 2) % 16
        pad = 16 - remainder if remainder != 0 else 0

        # Compute total length of payload, pad and hash
        length = len(data) + pad + 32

        # Build header
        header = self._build_header(length, bytes(
            [pad << 4 | self.PacketType.ENCRYPTED_REQUEST]))

        # Build payload to encrypt
        payload = packet_id.to_bytes(2, "big") + data + get_random_bytes(pad)

        calc_hash = sha256(header + payload).digest()
        return header + Security.encrypt_aes_cbc(self._local_key, payload) + calc_hash

    def _encode_handshake_request(self, packet_id: int, data: bytes) -> bytes:
        """Encode a handshake request packet."""

        # Build header
        header = self._build_header(len(data), bytes(
            [self.PacketType.HANDSHAKE_REQUEST]))

        # Build payload to encrypt
        payload = packet_id.to_bytes(2, "big") + data

        return header + payload

    def write(self, data: bytes, *, packet_type=PacketType.ENCRYPTED_REQUEST) -> None:
        """Send a packet of the specified type to the peer."""

        # Raise an error if attempting to send an encrypted request without authenticating
        if packet_type == self.PacketType.ENCRYPTED_REQUEST and self._local_key is None:
            raise ProtocolError("Protocol has not been authenticated.")

        # Encode the data according to the supplied type
        if packet_type == self.PacketType.ENCRYPTED_REQUEST:
            packet = self._encode_encrypted_request(self._packet_id, data)
        elif packet_type == self.PacketType.HANDSHAKE_REQUEST:
            packet = self._encode_handshake_request(self._packet_id, data)
        else:
            raise TypeError(f"Unknown type: {packet_type}")

        # Write to the peer
        super().write(packet)

        # Increment packet ID and handle rollover
        self._packet_id += 1
        self._packet_id &= 0xFFF  # Mask to 12 bits

    def _get_local_key(self, key: bytes, data: memoryview) -> bytes:

        if len(data) != 64:
            raise AuthenticationError(
                "Invalid data length for key handshake.")

        # Extract payload and hash
        payload = data[:32]
        rx_hash = data[32:]

        # Decrypt the payload with the provided key
        decrypted_payload = Security.decrypt_aes_cbc(key, payload)

        if sha256(decrypted_payload).digest() != rx_hash:
            raise AuthenticationError(
                "Calculated and received SHA256 digest do not match.")

        # Construct the local key
        return strxor(decrypted_payload, key)

    async def authenticate(self, token: Optional[bytes], key: Optional[bytes]) -> None:

        # Raise an exception if trying to auth without any token or key
        if not token or not key:
            raise AuthenticationError("Token and key must be supplied.")

        try:
            self.write(token, packet_type=self.PacketType.HANDSHAKE_REQUEST)
            response = await self.read()
        except ProtocolError as e:
            # Promote any protocol error to auth error
            raise AuthenticationError(e) from e

        # Generate local key from cloud key
        with memoryview(response) as response_mv:
            self._local_key = self._get_local_key(key, response_mv)

        _LOGGER.info("Authentication successful. Local key: %s",
                     self._local_key.hex())


class LAN:
    RETRIES = 3

    def __init__(self, ip: str, port: int, device_id: int) -> None:
        self._ip = ip
        self._port = port
        self._device_id = device_id

        self._token = None
        self._key = None
        self._protocol_version = 2
        self._protocol = None

    @property
    def token(self) -> Optional[bytes]:
        return self._token

    @property
    def key(self) -> Optional[bytes]:
        return self._key

    async def _connect(self) -> None:
        _LOGGER.info("Creating new connection to %s:%s", self._ip, self._port)

        protocol_class = _LanProtocolV3 if self._protocol_version == 3 else _LanProtocol

        # TODO throws OSError and ???
        loop = asyncio.get_event_loop()
        _transport, protocol = await loop.create_connection(
            lambda: protocol_class(), self._ip, self._port)  # pylint: disable=unnecessary-lambda

        if self._protocol_version == 3:
            self._protocol = cast(_LanProtocolV3, protocol)
        else:
            self._protocol = cast(_LanProtocol, protocol)

    def _disconnect(self) -> None:
        if self._protocol:
            self._protocol.disconnect()
            self._protocol = None

    async def authenticate(self, token: Token = None, key: Key = None, retries: int = RETRIES) -> None:
        """Authenticate against a V3 device. Use cached token and key unless provided a new token and key."""

        # Use existing token and key if none provided
        if token is None or key is None:
            token = self._token
            key = self._key
        else:
            # Define a lambda to convert hex strings to bytes
            def convert(x: Union[Token, Key]) -> Optional[bytes]:
                return bytes.fromhex(x) if isinstance(x, str) else x

            # Ensure passed token and key are in byte form
            token = convert(token)
            key = convert(key)

        # Disconnect any existing V2 protocol
        if self._protocol_version == 2:
            self._disconnect()

        if self._protocol is None or not self._protocol.alive:
            self._disconnect()
            self._protocol_version = 3
            await self._connect()

        # A protocol should exist at this point
        assert self._protocol is not None

        _LOGGER.info("Authenticating with %s.", self._protocol.peer)

        # Attempt to authenticate
        while retries > 0:
            try:
                await cast(_LanProtocolV3, self._protocol).authenticate(token, key)
                break
            except (TimeoutError, asyncio.TimeoutError) as e:
                if retries > 1:
                    _LOGGER.debug("Authentication timeout. Resending.")
                    retries -= 1
                else:
                    raise TimeoutError("No response from host.") from e

        # Update stored token and key if successful
        self._token = token
        self._key = key

        # Sleep briefly before requesting more data
        await asyncio.sleep(1)

    async def _read(self, **kwargs) -> bytes:
        """Read and decode a frame from the protocol."""

        # A protocol should exist at this point
        assert self._protocol is not None

        # Await a response
        packet = await self._protocol.read(**kwargs)
        _LOGGER.debug("Received packet from %s: %s",
                      self._protocol.peer, packet.hex())

        # Decode packet to frame
        response = _Packet.decode(packet)
        _LOGGER.debug("Received response from %s: %s",
                      self._protocol.peer, response.hex())

        return response

    async def send(self, data: bytes, retries: int = RETRIES) -> List[bytes]:
        """Send data via the LAN protocol. Connecting to the peer if necessary."""

        # Connect if protocol doesn't exist or is dead
        if self._protocol is None or not self._protocol.alive:
            self._disconnect()
            await self._connect()

            # Reauthenticate if needed
            if self._protocol_version == 3:
                await self.authenticate()

        # A protocol should exist at this point
        assert self._protocol is not None

        # Encode frame to packet
        packet = _Packet.encode(self._device_id, data)

        responses = []
        while retries > 0:
            # Send the request
            _LOGGER.debug("Sending packet to %s: %s",
                          self._protocol.peer, packet.hex())
            self._protocol.write(packet)

            try:
                # Await a response
                responses.append(await self._read())
                break
            except (TimeoutError, asyncio.TimeoutError) as e:
                if retries > 1:
                    _LOGGER.debug("Request timeout. Resending.")
                    retries -= 1
                else:
                    self._disconnect()
                    raise TimeoutError("No response from host.") from e
            except ProtocolError as e:
                # Disconnect on protocol errors and reraise
                # TODO could add a fatal flag to exception to trigger disconnect
                self._disconnect()
                raise e

        # Attempt to read any additional responses without blocking
        while True:
            try:
                responses.append(await self._read(timeout=0))
            except asyncio.QueueEmpty:
                break

        return responses


class Security:
    SIGN_KEY = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S".encode()
    ENC_KEY = md5(SIGN_KEY).digest()

    @classmethod
    def decrypt_aes_cbc(cls, key: bytes, data: bytes) -> bytes:
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).decrypt(data)

    @classmethod
    def encrypt_aes_cbc(cls, key: bytes, data: bytes) -> bytes:
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).encrypt(data)

    @classmethod
    def decrypt_aes(cls, data: bytes) -> bytes:
        cipher = AES.new(Security.ENC_KEY, AES.MODE_ECB)

        # Decrypt and remove padding
        return Padding.unpad(cipher.decrypt(data), 16)

    @classmethod
    def encrypt_aes(cls, data: bytes) -> bytes:
        cipher = AES.new(Security.ENC_KEY, AES.MODE_ECB)

        # Encrypt the padded data
        return cipher.encrypt(Padding.pad(data, 16))

    @classmethod
    def sign(cls, data: bytes) -> bytes:
        return md5(data + Security.SIGN_KEY).digest()

    @classmethod
    def udpid(cls, device_id: bytes) -> bytes:
        with memoryview(sha256(device_id).digest()) as mv_hash:
            return strxor(mv_hash[:16], mv_hash[16:])


class _Packet:
    """Class to encode/decode command frames to packets."""

    @classmethod
    def encode(cls, device_id: int, command: bytes) -> bytes:
        """Encode a command frame to a LAN packet."""
        # Encrypt command
        encrypted_payload = Security.encrypt_aes(command)

        # Compute total length
        length = 40 + len(encrypted_payload) + 16

        header = b"\x5A\x5A"  # Start of packet
        header += b"\x01\x11"  # Message type
        header += length.to_bytes(2, 'little')  # Packet size
        header += b"\x20\x00"  # Magic bytes
        header += bytes(4)  # Message ID
        header += cls._timestamp()  # Timestamp
        header += device_id.to_bytes(8, 'little')  # Device ID
        header += bytes(12)  # ???

        packet = header + encrypted_payload

        # Append hash
        return packet + Security.sign(packet)

    @classmethod
    def decode(cls, data: bytes) -> bytes:
        """Decode a LAN packet to a command frame."""

        with memoryview(data) as packet:
            if len(packet) < 6:
                raise ProtocolError(f"Packet is too short: {packet.hex()}")

            if packet[:2] != b"\x5a\x5a":
                # TODO old code handled raw frames? e.g start = 0xAA
                raise ProtocolError(f"Unsupported packet: {packet.hex()}")

            length = int.from_bytes(packet[4:6], "little")

            if len(packet) < length:
                raise ProtocolError(
                    f"Packet is truncated. Expected {length} bytes, only have {len(packet)} bytes: {packet.hex()}")

            packet = packet[:length]
            encrypted_frame = packet[40:-16]
            rx_hash = packet[-16:]

            # Check that received hash matches
            if Security.sign(bytes(packet[:-16])) != rx_hash:
                raise ProtocolError(
                    "Calculated and received MD5 digest do not match.")

            # Decrypt frame
            return Security.decrypt_aes(encrypted_frame)

    @classmethod
    def _timestamp(cls) -> bytes:
        now = datetime.utcnow()

        # Each byte is a 2 digit component of the timestamp
        # YYYYMMDDHHMMSSmm
        return struct.pack("BBBBBBBB",
                           int(now.microsecond / 10000),
                           now.second,
                           now.minute,
                           now.hour,
                           now.day,
                           now.month,
                           now.year % 100,
                           int(now.year / 100)
                           )
