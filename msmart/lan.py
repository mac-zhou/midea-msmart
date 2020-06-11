import logging
import requests
import datetime
import json
import socket
import sys

from msmart.security import security

# The Midea cloud client is by far the more obscure part of this library, and without some serious reverse engineering
# this would not have been possible. Thanks Yitsushi for the ruby implementation. This is an adaptation to Python 3

VERSION = '0.1.17'

_LOGGER = logging.getLogger(__name__)


class lan:
    def __init__(self, device_ip, device_id):
        # Get this from any of the Midea based apps, you can find one on Yitsushi's github page
        self.device_ip = device_ip
        self.device_id = device_id
        self.device_port = 6444
        self.security = security()
        self._retries = 0

    def request(self, message):
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)

        # Connect the Device
        device_address = (self.device_ip, self.device_port)
        sock.connect(device_address)

        try:
            # Send data
            _LOGGER.debug("Sending to %s:%s %s." %
                          (self.device_ip, self.device_port, message.hex()))
            sock.sendall(message)

            # Received data
            response = sock.recv(512)
        except socket.timeout:
            _LOGGER.info("Connect the Device %s:%s TimeOut for 10s. don't care about a small amount of this. if many maybe not support." % (
                self.device_ip, self.device_port))
            return bytearray(0)
        finally:
            sock.close()
        _LOGGER.debug("Received from %s:%s %s." %
                      (self.device_ip, self.device_port, message.hex()))
        if response.hex() == message.hex():
            _LOGGER.debug("Something wrong! reply is same. %s:%s %s." % (
                self.device_ip, self.device_port, message.hex()))
            return bytearray(0)
        return response

    def encode(self, data: bytearray):
        normalized = []
        for b in data:
            if b >= 128:
                b = b - 256
            normalized.append(str(b))

        string = ','.join(normalized)
        return bytearray(string.encode('ascii'))

    def decode(self, data: bytearray):
        data = [int(a) for a in data]
        for i in range(len(data)):
            if data[i] < 0:
                data[i] = data[i] + 256
        return bytearray(data)

    def appliance_transparent_send(self, data):
        response = bytearray(self.request(data))
        if len(response) > 0:
            if len(response) == 88:
                reply = self.decode(self.security.aes_decrypt(response[40:72]))
            else:
                reply = self.decode(self.security.aes_decrypt(response[40:88]))
            return reply
        else:
            return bytearray(0)
