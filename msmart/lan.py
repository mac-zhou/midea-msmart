# -*- coding: UTF-8 -*-
import logging
import socket
from msmart.security import security, MSGTYPE_HANDSHAKE_REQUEST, MSGTYPE_ENCRYPTED_REQUEST

VERSION = '0.1.20'

_LOGGER = logging.getLogger(__name__)

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

    def _connect(self):
        if self._socket == None:
            _LOGGER.debug("Attempting new connection to {}:{}".format(
                self.device_ip, self.device_port))
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(8)
            try:
                self._socket.connect((self.device_ip, self.device_port))
            except:
                self._disconnect()

    def _disconnect(self):
        if self._socket:
            self._socket.close()
            self._socket = None

    def request(self, message):
        # Create a TCP/IP socket
        self._connect()

        try:
            if self._socket == None:
                raise socket.error
            # Send data
            _LOGGER.debug("Sending to {}:{} {}".format(
                self.device_ip, self.device_port, message.hex()))
            self._socket.send(message)

            # Received data
            response = self._socket.recv(512)
        except socket.error:
            _LOGGER.info("Couldn't connect with Device {}:{}".format(
                self.device_ip, self.device_port))
            self._disconnect()
            return bytearray(0)
        except socket.timeout:
            _LOGGER.info("Connect the Device %s:%s TimeOut for 8s. don't care about a small amount of this. if many maybe not support".format(
                self.device_ip, self.device_port))
            self._disconnect()
            return bytearray(0)
        _LOGGER.debug("Received from {}:{} {}".format(
            self.device_ip, self.device_port, response.hex()))
        return response

    def authenticate(self, mac: str, ssid: str, pw: str):
        if not self._token or not self._key:
            self._token, self._key = self.security.token_key_pair(mac, ssid, pw)
        request = self.security.encode_8370(self._token, MSGTYPE_HANDSHAKE_REQUEST)
        response = self.request(request)[8:72]
        if response == b'ERROR':
            raise Exception('authentication failed')
        tcp_key = self.security.tcp_key(response, self._key)
        _LOGGER.debug('Got TCP key for {}:{} {}'.format(self.device_ip, self.device_port, tcp_key.hex()))

    def appliance_transparent_send_8370(self, data, msgtype=MSGTYPE_ENCRYPTED_REQUEST):
        data = self.security.encode_8370(data, msgtype)
        responses = self.security.decode_8370(self.request(data))
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
