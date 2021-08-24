# -*- coding: UTF-8 -*-
import logging
import socket
import time
from msmart.security import security, MSGTYPE_HANDSHAKE_REQUEST, MSGTYPE_ENCRYPTED_REQUEST

VERSION = '0.1.30'

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
        self._timestamp = time.time()
        self._tcp_key = None
        self._local = None
        self._remote = device_ip + ":" + str(device_port)

    def _connect(self):
        if self._socket is None:
            self._disconnect()
            _LOGGER.debug("Attempting new connection to {}:{}".format(
                self.device_ip, self.device_port))
            self._buffer = b''
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # set timeout
            self._socket.settimeout(8)
            try:
                self._socket.connect((self.device_ip, self.device_port))
                self._timestamp = time.time()
                self._local = ":".join(
                    '%s' % i for i in self._socket.getsockname())
            except Exception as error:
                _LOGGER.error("Connect Error: {}:{} {}".format(
                    self.device_ip, self.device_port, error))
                self._disconnect()

    def _disconnect(self):
        if self._socket:
            self._socket.close()
            self._socket = None
            self._tcp_key = None

    def request(self, message):
        # Create a TCP/IP socket
        self._connect()

        try:
            if self._socket is None:
                _LOGGER.error("Sokcet is None: {}:{}".format(
                    self.device_ip, self.device_port))
                return bytearray(0), False
            _LOGGER.debug("Socket {} -> {} tcp_key: {}".format(
                self._local, self._remote, self._tcp_key))
            # Send data
            _LOGGER.debug(
                "Sending to {} -> {} retries: {} message: {}".format(self._local, self._remote, self._retries, message.hex()))
            self._socket.sendall(message)

            # Received data
            response = self._socket.recv(1024)
        except socket.error as error:
            self._disconnect()
            self._retries += 1
            if self._retries < 2:
                _LOGGER.warn("About to send data again with Device {}:{} error: {}".format(
                    self.device_ip, self.device_port, error))
            else:
                _LOGGER.error("Couldn't connect with Device {}:{} retries: {} error: {}".format(
                    self.device_ip, self.device_port, self._retries, error))
            return bytearray(0), True
        except socket.timeout:
            _LOGGER.error("Connect the Device {}:{} TimeOut for 8s. don't care about a small amount of this. if many maybe not support".format(
                self.device_ip, self.device_port))
            self._disconnect()
            return bytearray(0), True
        _LOGGER.debug("Received from {}:{} {}".format(
            self.device_ip, self.device_port, response.hex()))
        if response == bytearray(0):
            _LOGGER.warn("About to send data again with Device {}:{} response is null".format(
                    self.device_ip, self.device_port))
            self._disconnect()
            self._retries += 1
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
            _LOGGER.info('Got TCP key for {}:{} {}'.format(
            self.device_ip, self.device_port, tcp_key.hex()))
            # After authentication, don’t send data immediately, so sleep 1s.
            time.sleep(1)
        return success


    def _authenticate(self):
        if not self._token or not self._key:
            raise Exception('missing token key pair')
        self.authenticate(self._token, self._key)

    def appliance_transparent_send_8370(self, data, msgtype=MSGTYPE_ENCRYPTED_REQUEST):
        socket_time = time.time() - self._timestamp
        _LOGGER.debug("Data: {} msgtype: {} len: {} socket time: {}".format(data.hex(), msgtype, len(data), socket_time))
        if self._socket is None or socket_time > 120:
            if socket_time > 120:
                _LOGGER.debug("Socket {} -> {} is TimeOut, Create New Socket ".format(self._local, self._remote))
            self._disconnect()
            self._authenticate()
        # copy from data in order to resend data
        original_data = bytearray.copy(data)
        data = self.security.encode_8370(data, msgtype)
        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self.request(data)
        _LOGGER.debug("Got responses len: {}".format(len(responses)))
        if responses == bytearray(0) and self._retries < 2 and b:
            packets = self.appliance_transparent_send_8370(original_data, msgtype)
            self._retries = 0
            return packets
        responses, self._buffer = self.security.decode_8370(
            self._buffer + responses)
        packets = []
        for response in responses:
            if len(response) > 40 + 16:
                response = self.security.aes_decrypt(response[40:-16])
            packets.append(response)
        return packets

    def appliance_transparent_send(self, data):
        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self.request(data)
        _LOGGER.debug("Got responses len: {}".format(len(responses)))
        if responses == bytearray(0) and self._retries < 2 and b:
            packets = self.appliance_transparent_send(data)
            self._retries = 0
            return packets
        packets = []
        if responses == bytearray(0):
            return packets
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
