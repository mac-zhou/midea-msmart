"""Module for local network control of Midea AC devices."""
from Crypto.Cipher import AES
from Crypto.Util import Padding
from Crypto.Util.strxor import strxor
from Crypto.Random import get_random_bytes
from hashlib import md5, sha256
import logging
import socket
import time
from msmart.const import (
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_HANDSHAKE_REQUEST,
    MSGTYPE_ENCRYPTED_RESPONSE
)


_LOGGER = logging.getLogger(__name__)


class lan:
    def __init__(self, device_ip, device_id, device_port=6444):
        self.device_ip = device_ip
        self.device_id = device_id
        self.device_port = device_port
        self.security = Security()
        self._retries = 0
        self._socket = None
        self._token = None
        self._key = None
        self._timestamp = time.time()
        self._tcp_key = None
        self._local = None
        self._remote = device_ip + ":" + str(device_port)
        self._protocol_version = 2

    def _connect(self):
        if self._socket is None:
            self._disconnect()
            _LOGGER.debug("Attempting new connection to %s:%d",
                          self.device_ip, self.device_port)
            self._buffer = b''
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # set timeout
            self._socket.settimeout(2)
            try:
                self._socket.connect((self.device_ip, self.device_port))
                self._timestamp = time.time()
                self._local = ":".join(
                    '%s' % i for i in self._socket.getsockname())
            except Exception as error:
                _LOGGER.error("Connect Error: %s:%d %s",
                              self.device_ip, self.device_port, error)
                self._disconnect()

    def _disconnect(self):
        if self._socket:
            self._socket.close()
            self._socket = None
            self._tcp_key = None

    def get_socket_info(self):
        socket_time = round(time.time() - self._timestamp, 2)
        return "{} -> {} retries: {} time: {}".format(self._local, self._remote, self._retries, socket_time)

    def request(self, message):
        # Create a TCP/IP socket
        self._connect()
        if self._socket is None:
            _LOGGER.error("Sokcet is None: %s", self._remote)
            return bytearray(0), False
        _LOGGER.debug("Socket %s tcp_key: %s",
                      self.get_socket_info(), self._tcp_key)
        # Send data
        try:
            _LOGGER.debug(
                "Sending %s message: %s", self.get_socket_info(), message.hex())
            self._socket.sendall(message)
        except Exception as error:
            _LOGGER.error("Send %s Error: %s", self.get_socket_info(), error)
            self._disconnect()
            self._retries += 1
            return bytearray(0), True

        # Received data
        try:
            response = self._socket.recv(1024)
        except socket.timeout as error:
            if error.args[0] == 'timed out':
                _LOGGER.debug("Recv %s, timed out", self.get_socket_info())
                self._retries += 1
                return bytearray(0), True
            else:
                _LOGGER.debug("Recv %s TimeOut: %s",
                              self.get_socket_info(), error)
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
        except socket.error as error:
            _LOGGER.debug("Recv %s Error: %s", self.get_socket_info(), error)
            self._disconnect()
            self._retries += 1
            return bytearray(0), True
        else:
            _LOGGER.debug("Recv %s Response: %s",
                          self.get_socket_info(), response.hex())
            if len(response) == 0:
                _LOGGER.debug("Recv %s Server Closed Socket",
                              self.get_socket_info())
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
            else:
                self._retries = 0
                return response, True

    def authenticate(self, token: bytearray, key: bytearray):
        self._token, self._key = token, key
        if not self._token or not self._key:
            raise Exception('missing token key pair')
        request = self.security.encode_8370(
            self._token, MSGTYPE_HANDSHAKE_REQUEST)
        response, _ = self.request(request)
        response = response[8:72]

        tcp_key, success = self.security.tcp_key(response, self._key)
        if success:
            self._tcp_key = tcp_key.hex()
            _LOGGER.info('Got TCP key for %s tcp_key: %s',
                         self.get_socket_info(), tcp_key.hex())
            self._protocol_version = 3
            # After authentication, don’t send data immediately, so sleep 1s.
            time.sleep(1)
        else:
            _LOGGER.error('Authentication failed for %s %s',
                          self.get_socket_info(), tcp_key.hex())
        return success

    def _authenticate(self):
        if not self._token or not self._key:
            raise Exception('missing token key pair')
        return self.authenticate(self._token, self._key)

    def _send_v3(self, data, msgtype=MSGTYPE_ENCRYPTED_REQUEST):
        # socket_time = time.time() - self._timestamp
        # _LOGGER.debug("Data: {} msgtype: {} len: {} socket time: {}".format(data.hex(), msgtype, len(data), socket_time))
        if self._socket is None or self._tcp_key is None:
            _LOGGER.debug(
                "Socket %s invalid, Create New Socket and Get New tcp_key %s", self.get_socket_info(), self._tcp_key)
            self._disconnect()
            if self._authenticate() == False:
                return []
        # copy from data in order to resend data
        original_data = bytearray.copy(data)
        data = self.security.encode_8370(data, msgtype)
        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self.request(data)
        _LOGGER.debug("Got responses len: %d", len(responses))
        if responses[8:13] == b'ERROR':
            self._disconnect()
            return [b'ERROR']
        if responses == bytearray(0) and self._retries < 2 and b:
            packets = self._send_v3(original_data, msgtype)
            self._retries = 0
            return packets
        responses, self._buffer = self.security.decode_8370(
            self._buffer + responses)
        packets = []
        for response in responses:
            if len(response) > 40 + 16:
                response = Security.decrypt_aes(response[40:-16])
            # header lenght is 10
            if len(response) > 10:
                packets.append(response)
        return packets

    def _send(self, data):
        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self.request(data)
        _LOGGER.debug("Get responses len: %d", len(responses))
        if responses == bytearray(0) and self._retries < 2 and b:
            packets = self._send(data)
            self._retries = 0
            return packets
        packets = []
        if responses == bytearray(0):
            return packets
        dlen = len(responses)
        if responses[:2].hex() == "5a5a" and dlen > 5:
            i = 0
            # maybe multiple response
            while i < dlen:
                size = responses[i+4]
                data = Security.decrypt_aes(responses[i:i+size][40:-16])
                # header lenght is 10
                if len(data) > 10:
                    packets.append(data)
                i += size
        elif responses[0] == 0xaa and dlen > 2:
            i = 0
            while i < dlen:
                size = responses[i+1]
                data = responses[i:i+size+1]
                # header lenght is 10
                if len(data) > 10:
                    packets.append(data)
                i += size + 1
        else:
            _LOGGER.error("Unknown responses %s", responses.hex())
        return packets

    def send(self, data: bytes):
        if self._protocol_version == 3:
            return self._send_v3(data)
        else:
            return self._send(data)

    @property
    def protocol_version(self) -> int:
        return self._protocol_version


class Security:
    SIGN_KEY = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S".encode()
    ENC_KEY = md5(SIGN_KEY).digest()

    def __init__(self):
        self._tcp_key = None
        self._request_count = 0
        self._response_count = 0

    def _aes_cbc_decrypt(self, raw, key):
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).decrypt(raw)

    def _aes_cbc_encrypt(self, raw, key):
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).encrypt(raw)

    def tcp_key(self, response, key):
        if response == b'ERROR':
            _LOGGER.error('authentication failed')
            return b'', False
        if len(response) != 64:
            _LOGGER.error('unexpected data length')
            return b'', False
        payload = response[:32]
        sign = response[32:]
        plain = self._aes_cbc_decrypt(payload, key)
        if sha256(plain).digest() != sign:
            _LOGGER.error("sign does not match")
            return b'', False
        self._tcp_key = strxor(plain, key)
        self._request_count = 0
        self._response_count = 0
        return self._tcp_key, True

    def encode_8370(self, data, msgtype):
        header = bytes([0x83, 0x70])
        size, padding = len(data), 0
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            if (size + 2) % 16 != 0:
                padding = 16 - (size + 2 & 0xf)
                size += padding + 32
                data += get_random_bytes(padding)
        header += size.to_bytes(2, 'big')
        header += bytes([0x20, padding << 4 | msgtype])
        if self._request_count >= 0xfff:
            _LOGGER.info("request_count is too big to convert: %d",
                         self._request_count)
            self._request_count = 0
        data = self._request_count.to_bytes(2, 'big') + data
        self._request_count += 1
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = sha256(header + data).digest()
            data = self._aes_cbc_encrypt(data, self._tcp_key) + sign
        return header + data

    def decode_8370(self, data):
        if len(data) < 6:
            return [], data
        header = data[:6]
        if header[0] != 0x83 or header[1] != 0x70:
            raise Exception('not an 8370 message')
        size = int.from_bytes(header[2:4], 'big') + 8
        leftover = None
        if len(data) < size:
            return [], data
        elif len(data) > size:
            leftover = data[size:]
            data = data[:size]
        if header[4] != 0x20:
            raise Exception('missing byte 4')
        padding = header[5] >> 4
        msgtype = header[5] & 0xf
        data = data[6:]
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = data[-32:]
            data = data[:-32]
            data = self._aes_cbc_decrypt(data, self._tcp_key)
            if sha256(header + data).digest() != sign:
                raise Exception('sign does not match')
            if padding:
                data = data[:-padding]
        self._response_count = int.from_bytes(data[:2], 'big')
        data = data[2:]
        if leftover:
            packets, incomplete = self.decode_8370(leftover)
            return [data] + packets, incomplete
        return [data], b''

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
            return bytes(a ^ b for a, b in zip(hash[:16], hash[16:]))
