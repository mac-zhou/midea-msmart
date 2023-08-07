"""Module for local network control of Midea AC devices."""
import asyncio
from Crypto.Cipher import AES
from Crypto.Util import Padding
from Crypto.Util.strxor import strxor
from Crypto.Random import get_random_bytes
from enum import IntEnum
from hashlib import md5, sha256
import logging
from typing import cast

_LOGGER = logging.getLogger(__name__)

# Define a type for a token or key
TokenKey = str | bytes | None


class ProtocolError(Exception):
    pass


class _LanProtocol(asyncio.Protocol):
    """Midea LAN protocol."""

    def __init__(self):
        self._transport = None

        self._peer = None
        self._queue = asyncio.Queue()

    @property
    def peer(self):
        return self._peer

    def _format_socket_name(self, sockname) -> str:
        def _format(addr, port):
            return f"{addr}:{port}"
        return _format(*sockname)

    def connection_made(self, transport) -> None:
        """Handle connection events."""

        # Save transport for later
        self._transport = transport

        # Save peer name for logging
        peername = transport.get_extra_info('peername')
        self._peer = self._format_socket_name(peername)

        _LOGGER.debug("Connected to %s.", self._peer)

    def data_received(self, data) -> None:
        """Handle data received events."""

        _LOGGER.debug("Received data from %s: %s", self.peer, data.hex())
        self._queue.put_nowait(data)

    def error_received(self, ex):
        """Log received errors."""
        _LOGGER.error("Received error: %s.", ex)

    def connection_lost(self, ex):
        """Log connection lost."""
        if ex:
            _LOGGER.error("Connection to %s lost. Error: %s.", self.peer, ex)

    def disconnect(self) -> None:
        """Disconnect from the peer."""
        if self._transport is None:
            raise IOError()  # TODO better?

        _LOGGER.debug("Disconnecting from %s.", self.peer)
        self._transport.close()

    def _write(self, data: bytes) -> None:
        """Send data to the peer."""

        if self._transport is None:
            raise IOError()  # TODO better

        _LOGGER.debug("Sending data to %s: %s", self.peer, data.hex())
        self._transport.write(data)

    async def _read(self, timeout=2) -> bytes:
        """Asynchronously read data from the peer via the queue."""

        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    async def request(self, *args, **kwargs) -> bytes:
        """Send data to the peer and wait for a response."""

        self._write(*args, **kwargs)
        return await self._read()


class _LanProtocolV3(_LanProtocol):
    """Midea LAN protocol V3."""

    class PacketType(IntEnum):
        HANDSHAKE_REQUEST = 0x0
        HANDSHAKE_RESPONSE = 0x1
        ENCRYPTED_RESPONSE = 0x3
        ENCRYPTED_REQUEST = 0x6
        ERROR = 0xF

    class AuthenticationError(ProtocolError):
        pass

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

    def __init__(self):
        super().__init__()

        self._packet_id = 0
        self._buffer = bytearray(0)
        self._local_key = None

    def data_received(self, data) -> None:
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
                total_size = int.from_bytes(buf[2:4]) + 8

                # Ensure entire packet is received
                if len(buf) < total_size:
                    _LOGGER.warning(
                        "Partial packet received. Buffer: %s", buf.hex())
                    return

                # Extract the packet from the buffer
                packet, self._buffer = buf[:total_size], bytearray(
                    buf[total_size:])

                # Queue the received packet
                _LOGGER.debug("Received packet: %s", packet.hex())
                self._queue.put_nowait(packet.tobytes())

    def _decode_encrypted_response(self, packet: memoryview):
        """Decode an encrypted response packet."""

        # Extract header, encrypted payload and hash
        header = packet[:6]
        payload = packet[6:-32]
        hash = packet[-32:]

        # Decrypt payload
        decrypted_payload = Security.decrypt_aes_cbc(self._local_key, payload)

        # TODO could padding module handle this padding?

        # Verify hash
        if sha256(bytes(header) + decrypted_payload).digest() != hash:
            raise ProtocolError(
                "Calculated and received SHA256 digest do not match.")

        with memoryview(decrypted_payload) as payload:
            # Decrypted payload consists of 2 byte packet ID + actual payload + padding

            # Get pad count from header
            pad = header[5] >> 4

            # Return actual payload without padding
            return payload[2:-pad].tobytes()

    def _decode_handshake_response(self, packet: memoryview):
        """Decode a handshake response packet."""

        # Get payload from packet
        payload = packet[6:]

        # Return remaining raw payload
        return payload[2:].tobytes()

    def _process_packet(self, packet: memoryview):
        """Process a received packet based on its type."""

        if packet[:2] != b"\x83\x70":
            raise ProtocolError(
                f"Invalid start of packet: {packet[:2].hex()}")

        if packet[4] != 0x20:
            raise ProtocolError(
                f"Invalid magic byte: 0x{packet[4]:X}")

        # Handle packet based on type
        type = packet[5] & 0xF
        if type == self.PacketType.ENCRYPTED_RESPONSE:
            return self._decode_encrypted_response(packet)
        elif type == self.PacketType.HANDSHAKE_RESPONSE:
            return self._decode_handshake_response(packet)
        elif type == self.PacketType.ERROR:
            raise ProtocolError("Error packet received.")
        else:
            raise ProtocolError(f"Unexpected type: {type}")

    async def _read(self, timeout=2) -> bytes:
        """Asynchronously read data from the peer via the queue."""

        # Fetch a packet from the queue
        packet = await super()._read(timeout=timeout)

        with memoryview(packet) as packet_mv:
            return self._process_packet(packet_mv)

    def _encode_encrypted_request(self, packet_id: int, data: bytes):
        """Encode an encrypted request packet."""

        # Compute required padding for 16 byte alignment
        # Include 2 bytes for packet ID in total length
        pad = 16 - ((len(data) + 2) & 0xF)

        # Compute total length of payload, pad and hash
        length = len(data) + pad + 32

        # Build header
        header = b"\x83\x70" + \
            length.to_bytes(2) + b"\x20" + \
            bytes([pad << 4 | self.PacketType.ENCRYPTED_REQUEST])

        # Build payload to encrypt
        payload = packet_id.to_bytes(2) + data + get_random_bytes(pad)

        hash = sha256(header + payload).digest()
        return header + Security.encrypt_aes_cbc(self._local_key, payload) + hash

    def _encode_handshake_request(self, packet_id: int, data: bytes):
        """Encode a handshake request packet."""

        # Build header
        header = b"\x83\x70" + len(data).to_bytes(2) + \
            b"\x20" + bytes([self.PacketType.HANDSHAKE_REQUEST])

        # Build payload to encrypt
        payload = packet_id.to_bytes(2) + data

        return header + payload

    def _write(self, data: bytes, *, type=PacketType.ENCRYPTED_REQUEST) -> None:
        """Send a packet of the specified type to the peer."""

        # Raise an error if attempting to send an encryptd request without authenticating
        if type == self.PacketType.ENCRYPTED_REQUEST and self._local_key is None:
            raise self.AuthenticationError(
                "Protocol has not been authenticated successfully.")

        # Encode the data according to the supplied type
        if type == self.PacketType.ENCRYPTED_REQUEST:
            packet = self._encode_encrypted_request(self._packet_id, data)
        elif type == self.PacketType.HANDSHAKE_REQUEST:
            packet = self._encode_handshake_request(self._packet_id, data)
        else:
            raise TypeError(f"Unknown type: {type}")

        # Write to the peer
        super()._write(packet)

        # Increment packet ID and handle rollover
        self._packet_id += 1
        self._packet_id &= 0xFFF  # Mask to 12 bits

    def _get_local_key(self, key, data: memoryview):

        if len(data) != 64:
            raise self.AuthenticationError(
                "Invalid data length for key handshake.")

        # Extract payload and hash
        payload = data[:32]
        hash = data[32:]

        # Decrypt the payload with the provided key
        decrypted_payload = Security.decrypt_aes_cbc(key, payload)

        if sha256(decrypted_payload).digest() != hash:
            raise _LanProtocolV3.AuthenticationError(
                "Calculated hash does not match received hash.")

        # Construct the local key
        return strxor(decrypted_payload, key)

    async def authenticate(self, token, key):
        # Send request
        try:
            response = await self.request(token, type=self.PacketType.HANDSHAKE_REQUEST)
        except ProtocolError as e:
            raise self.AuthenticationError(e)

        # Generate local key from cloud key
        with memoryview(response) as response_mv:
            self._local_key = self._get_local_key(key, response_mv)

        _LOGGER.info("Local key: %s", self._local_key.hex())


class LAN:
    RETRIES = 3

    def __init__(self, ip, port=6444):
        self._ip = ip
        self._port = port

        self._token = None
        self._key = None
        self._protocol_version = 2
        self._protocol = None

    async def _connect(self):
        _LOGGER.debug("Creating new connection to %s:%s", self._ip, self._port)

        protocol_class = _LanProtocolV3 if self._protocol_version == 3 else _LanProtocol

        loop = asyncio.get_event_loop()
        _transport, protocol = await loop.create_connection(
            lambda: protocol_class(), self._ip, self._port)

        if self._protocol_version == 3:
            self._protocol = cast(_LanProtocolV3, protocol)
        else:
            self._protocol = cast(_LanProtocol, protocol)

    def _disconnect(self):
        if self._protocol:
            self._protocol.disconnect()
            self._protocol = None

    async def authenticate(self, token: TokenKey = None, key: TokenKey = None, retries=RETRIES):
        """Authenticate against a V3 device. Use cached token and key unless provided a new token and key."""

        # Use existing token and key if none provided
        if token is None or key is None:
            token = self._token
            key = self._key
        else:
            # Define a lambda to convert hex strings to bytes
            def convert(x):
                return bytes.fromhex(x) if isinstance(x, str) else x

            # Ensure passed token and key are in byte form
            token = convert(token)
            key = convert(key)

        # Disconnect any existing V2 protocol
        if self._protocol_version == 2:
            self._disconnect()

        if self._protocol is None:
            self._protocol_version = 3
            await self._connect()

        # Attempt to authenticate
        while retries > 0:
            try:
                await self._protocol.authenticate(token, key)
                break
            except TimeoutError as e:
                _LOGGER.warning("Authentication timeout.")
                retries -= 1
                if retries == 0:
                    raise e  # Rethrow the exception after retries expire
            except _LanProtocolV3.AuthenticationError as e:
                _LOGGER.error("Authentication failed. Error: %s", e)
                return False

        # Update stored token and key if successful
        self._token = token
        self._key = key

        # Sleep briefly before requesting more data
        await asyncio.sleep(1)

        return True

    def _process_response(self, response: memoryview):
        """Process a response into a decrypted frame."""

        if len(response) < 6:
            raise ProtocolError(f"Response is too short: {response.hex()}")

        if response[:2] == b"\x5a\x5a":
            length = int.from_bytes(response[4:6], "little")

            if len(response) < length:
                raise ProtocolError(
                    f"Response is truncated. Expected {length} bytes, only have {len(response)} bytes: {response.hex()}")

            response = response[:length]
            encrypted_frame = response[40:-16]
            frame = Security.decrypt_aes(encrypted_frame)

            # TODO check frame hash/sign

            return frame

        # TODO old code handled raw frames? e.g start = 0xAA
        raise ProtocolError(f"Unsupported response: %s", response.hex())

    async def send(self, data, retries=RETRIES):
        """Send data via the LAN protocol. Connecting to the peer if necessary."""

        # Connect if protocol doesn't exist
        if self._protocol is None:
            await self._connect()

        while retries > 0:
            try:
                # Send the request and await a response
                _LOGGER.debug("Sending request to %s: %s",
                              self._protocol.peer, data.hex())
                response = await self._protocol.request(data)
                break
            except TimeoutError as e:
                _LOGGER.warning("Request timeout.")
                retries -= 1
                if retries == 0:
                    raise e  # Rethrow the exception after retries expire

        _LOGGER.debug("Received response from %s: %s",
                      self._protocol.peer, response.hex())

        try:
            with memoryview(response) as response_mv:
                # TODO return array for compat
                return [self._process_response(response_mv)]
        except ProtocolError as e:
            _LOGGER.error(e)
            return []

    @property
    def protocol_version(self) -> int:
        return self._protocol_version


class Security:
    SIGN_KEY = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S".encode()
    ENC_KEY = md5(SIGN_KEY).digest()

    @classmethod
    def decrypt_aes_cbc(cls, key, data):
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).decrypt(data)

    @classmethod
    def encrypt_aes_cbc(cls, key, data):
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).encrypt(data)

    @classmethod
    def decrypt_aes(cls, data: bytes):
        cipher = AES.new(Security.ENC_KEY, AES.MODE_ECB)

        # Decrypt and remove padding
        return Padding.unpad(cipher.decrypt(data), 16)

    @classmethod
    def encrypt_aes(cls, data: bytes):
        cipher = AES.new(Security.ENC_KEY, AES.MODE_ECB)

        # Encrypt the padded data
        return cipher.encrypt(Padding.pad(data, 16))

    @classmethod
    def encode32(cls, data: bytes):
        return md5(data + Security.SIGN_KEY).digest()

    @classmethod
    def udpid(cls, id: bytes):
        with memoryview(sha256(id).digest()) as hash:
            return strxor(hash[:16], hash[16:])
