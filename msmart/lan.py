# -*- coding: UTF-8 -*-
import logging
import socket
from msmart.security import security, MSGTYPE_HANDSHAKE_REQUEST, MSGTYPE_ENCRYPTED_REQUEST

VERSION = '0.1.29'

_LOGGER = logging.getLogger(__name__)


class lan:
    def __init__(self, device_ip, device_id, device_port=6444):
        self.device_ip = device_ip
        self.device_id = device_id
        self.device_port = device_port
        self.security = security()
        self._retries = 0
        self._socket = None
        self._token = None
        self._key = None

    def _connect(self):
        if self._socket is None:
            _LOGGER.debug("Attempting new connection to {}:{}".format(
                self.device_ip, self.device_port))
            self._buffer = b''
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(8)
            try:
                self._socket.connect((self.device_ip, self.device_port))
            except Exception as error:
                _LOGGER.error("Connect Error: {}:{} {}".format(
                    self.device_ip, self.device_port, error))
                self._disconnect()

    def _disconnect(self):
        if self._socket:
            self._socket.close()
            self._socket = None

    def request(self, message):
        # Create a TCP/IP socket
        self._connect()

        try:
            if self._socket is None:
                _LOGGER.error("Sokcet is None: {}:{}".format(
                    self.device_ip, self.device_port))
                return bytearray(0)
            # Send data
            _LOGGER.debug("Sending to {}:{} {}".format(
                self.device_ip, self.device_port, message.hex()))
            self._socket.send(message)

            # Received data
            response = self._socket.recv(1024)
        except socket.error as error:
            _LOGGER.error("Couldn't connect with Device {}:{} {}".format(
                self.device_ip, self.device_port, error))
            self._disconnect()
            return bytearray(0)
        except socket.timeout:
            _LOGGER.error("Connect the Device {}:{} TimeOut for 8s. don't care about a small amount of this. if many maybe not support".format(
                self.device_ip, self.device_port))
            self._disconnect()
            return bytearray(0)
        _LOGGER.debug("Received from {}:{} {}".format(
            self.device_ip, self.device_port, response.hex()))
        return response

    def authenticate(self, token: bytearray, key: bytearray):
        self._token, self._key = token, key
        if not self._token or not self._key:
            raise Exception('missing token key pair')
        request = self.security.encode_8370(
            self._token, MSGTYPE_HANDSHAKE_REQUEST)
        response = self.request(request)[8:72]
        try:
            tcp_key = self.security.tcp_key(response, self._key)
            _LOGGER.info('Got TCP key for {}:{} {}'.format(
                self.device_ip, self.device_port, tcp_key.hex()))
        except Exception as error:
            self._disconnect()
            raise error

    def _authenticate(self):
        if not self._token or not self._key:
            raise Exception('missing token key pair')
        self.authenticate(self._token, self._key)

    def appliance_transparent_send_8370(self, data, msgtype=MSGTYPE_ENCRYPTED_REQUEST):
        if self._socket is None:
            self._authenticate()
        data = self.security.encode_8370(data, msgtype)
        responses, self._buffer = self.security.decode_8370(
            self._buffer + self.request(data))
        packets = []
        for response in responses:
            if len(response) > 40 + 16:
                response = self.security.aes_decrypt(response[40:-16])
            packets.append(response)
        return packets

    def appliance_transparent_send(self, data):
        responses = self.request(data)
        _LOGGER.debug("Got responses len: {}".format(len(responses)))
        if responses == bytearray(0):
            return responses
        packets = []
        if responses[:2].hex() == "5a5a":
            # maybe multiple response
            for response in responses.split(bytearray.fromhex('5a5a')):
                # 5a5a been removed, so (40-2)+16
                if len(response) > 38 + 16:
                    packets.append(self.security.aes_decrypt(response[38:-16]))
        elif responses[0] == 0xaa:
            for response in responses.split(bytearray.fromhex('aa')):
                packets.append(bytearray.fromhex('aa') + response)
        else:
            _LOGGER.error("Unknown responses {}".format(responses.hex()))
        return packets
