# -*- coding: UTF-8 -*-
import logging
import socket
import time
from msmart.const import MSGTYPE_ENCRYPTED_REQUEST, MSGTYPE_HANDSHAKE_REQUEST
from msmart.security import security

VERSION = '0.1.36'

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
            self._socket.settimeout(2)
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
    
    def get_socket_info(self):
        socket_time = round(time.time() - self._timestamp, 2)
        return "{} -> {} retries: {} time: {}".format(self._local, self._remote, self._retries, socket_time)

    def request(self, message):
        # Create a TCP/IP socket
        self._connect()
        if self._socket is None:
            _LOGGER.error("Sokcet is None: {}".format(self._remote))
            return bytearray(0), False
        _LOGGER.debug("Socket {} tcp_key: {}".format(self.get_socket_info(), self._tcp_key))
        # Send data
        try:
            _LOGGER.debug(
                "Sending {} message: {}".format(self.get_socket_info(), message.hex()))
            self._socket.sendall(message)
        except Exception as error:
            _LOGGER.error("Send {} Error: {}".format(self.get_socket_info(), error))
            self._disconnect()
            self._retries += 1
            return bytearray(0), True

        # Received data
        try:
            response = self._socket.recv(1024)
        except socket.timeout as error:
            if error.args[0] == 'timed out':
                _LOGGER.debug("Recv {}, timed out".format(self.get_socket_info()))
                self._retries += 1
                return bytearray(0), True
            else:
                _LOGGER.debug("Recv {} TimeOut: {}".format(self.get_socket_info(), error))
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
        except socket.error as error:
            _LOGGER.debug("Recv {} Error: {}".format(self.get_socket_info(), error))
            self._disconnect()
            self._retries += 1
            return bytearray(0), True
        else:
            _LOGGER.debug("Recv {} Response: {}".format(self.get_socket_info(), response.hex()))
            if len(response) == 0:
                _LOGGER.debug("Recv {} Server Closed Socket".format(self.get_socket_info()))
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
            _LOGGER.info('Got TCP key for {} {}'.format(self.get_socket_info(), tcp_key.hex()))
            # After authentication, don’t send data immediately, so sleep 1s.
            time.sleep(1)
        return success

    def _authenticate(self):
        if not self._token or not self._key:
            raise Exception('missing token key pair')
        self.authenticate(self._token, self._key)

    def appliance_transparent_send_8370(self, data, msgtype=MSGTYPE_ENCRYPTED_REQUEST):
        # socket_time = time.time() - self._timestamp
        # _LOGGER.debug("Data: {} msgtype: {} len: {} socket time: {}".format(data.hex(), msgtype, len(data), socket_time))
        if self._socket is None or self._tcp_key is None:
            _LOGGER.debug(
                "Socket {} Closed, Create New Socket".format(self.get_socket_info()))
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
            packets = self.appliance_transparent_send_8370(
                original_data, msgtype)
            self._retries = 0
            return packets
        responses, self._buffer = self.security.decode_8370(
            self._buffer + responses)
        packets = []
        for response in responses:
            if len(response) > 40 + 16:
                response = self.security.aes_decrypt(response[40:-16])
            # header lenght is 10
            if len(response) > 10:
                packets.append(response)
        return packets

    def appliance_transparent_send(self, data):
        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self.request(data)
        _LOGGER.debug("Get responses len: {}".format(len(responses)))
        if responses == bytearray(0) and self._retries < 2 and b:
            packets = self.appliance_transparent_send(data)
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
                data = self.security.aes_decrypt(responses[i:i+size][40:-16])
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
            _LOGGER.error("Unknown responses {}".format(responses.hex()))
        return packets
