# -*- coding: UTF-8 -*-
import logging
import datetime
import socket
from msmart.security import security

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


    def appliance_transparent_send(self, data):
        response = self.request(data)
        if len(response) > 40 + 16:
            return self.security.aes_decrypt(response[40:-16])
        return response
