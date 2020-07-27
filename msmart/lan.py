# -*- coding: UTF-8 -*-
import logging
import socket
from msmart.security import security, get_random_bytes, sha256

VERSION = '0.1.20'

_LOGGER = logging.getLogger(__name__)

MSGTYPE_HANDSHAKE_REQUEST = 0x0
MSGTYPE_HANDSHAKE_RESPONSE = 0x1
MSGTYPE_ENCRYPTED_RESPONSE = 0x3
MSGTYPE_ENCRYPTED_REQUEST = 0x6
MSGTYPE_TRANSPARENT = 0xf

class lan:
    def __init__(self, device_ip, device_id):
        self.device_ip = device_ip
        self.device_id = device_id
        self.device_port = 6444
        self.security = security()
        self._retries = 0
        self._socket = None
        self._token = None
        self._key = None
        self._tcp_key = None
        self._request_count = 0
        self._response_count = 0

    def _connect(self):
        if self._socket == None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(8)
            try:
                self._socket.connect((self.device_ip, self.device_port))
            except:
                self._socket = None

    def request(self, message):
        # Create a TCP/IP socket
        self._connect()

        try:
            # Send data
            _LOGGER.debug("Sending to {}:{} {}".format(
                self.device_ip, self.device_port, message.hex()))
            self._socket.send(message)

            # Received data
            response = self._socket.recv(512)
        except socket.error:
            _LOGGER.info("Couldn't connect with Device {}:{}".format(
                self.device_ip, self.device_port))
            self._socket = None
            return bytearray(0)
        except socket.timeout:
            _LOGGER.info("Connect the Device %s:%s TimeOut for 8s. don't care about a small amount of this. if many maybe not support".format(
                self.device_ip, self.device_port))
            self._socket = None
            return bytearray(0)
        _LOGGER.debug("Received from {}:{} {}".format(
            self.device_ip, self.device_port, response.hex()))
        return response

    def authenticate(self, mac: str, ssid: str, pw: str):
        if not self._token or not self._key:
            self._token, self._key = self.security.token_key_pair(mac, ssid, pw)
        request = self.encode_8370(self._token, MSGTYPE_HANDSHAKE_REQUEST)
        response = self.request(request)[8:]
        if response == b'ERROR':
            raise Exception('authentication failed')
        self._tcp_key = self.security.tcp_key(response, self._key)
        _LOGGER.debug('Got TCP key for {}:{} {}'.format(self.device_ip, self.device_port, self._tcp_key.hex()))
        self._request_count = 0
        self._response_count = 0

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
        data = self._request_count.to_bytes(2, 'big') + data
        self._request_count += 1
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = sha256(header + data).digest()
            data = self.security.aes_cbc_encrypt(data, self._tcp_key) + sign
        return header + data

    def decode_8370(self, data):
        assert not len(data) < 6, 'not enough data'
        header = data[:6]
        assert not header[0] != 0x83 or header[1] != 0x70, 'not an 8370 message'
        size = int.from_bytes(header[2:4], 'big')
        leftover = None
        if len(data) != size + 8:
            leftover = data[size + 8:]
            data = data[:size + 8]
        assert not header[4] != 0x20, 'missing byte 4'
        padding = header[5] >> 4
        msgtype = header[5] & 0xf
        data = data[6:]
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = data[-32:]
            data = data[:-32]
            data = self.security.aes_cbc_decrypt(data, self._tcp_key)
            assert not sha256(header + data).digest() != sign, 'sign does not match'
            if padding:
                data = data[:-padding]
        self._response_count = int.from_bytes(data[:2], 'big')
        data = data[2:]
        if leftover:
            return [data] + self.decode_8370(leftover)
        return [data]

    def appliance_transparent_send_8370(self, data, msgtype=MSGTYPE_ENCRYPTED_REQUEST):
        data = self.encode_8370(data, msgtype)
        responses = self.decode_8370(self.request(data))
        packets = []
        for response in responses:
            if len(response) > 40 + 16:
                response = self.security.aes_decrypt(response[40:-16])
            packets.append(response)
        return packets

    def appliance_transparent_send(self, data):
        response = self.request(data)
        if len(response) > 40 + 16:
            return self.security.aes_decrypt(response[40:-16])
        return [response]
