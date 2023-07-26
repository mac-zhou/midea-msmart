
import logging
from msmart.lan import lan
from msmart.packet_builder import packet_builder
import time


_LOGGER = logging.getLogger(__name__)


class device:

    def __init__(self, device_ip: str, device_id: int, device_port: int):
        self._name = None
        self._lan_service = lan(device_ip, device_id, device_port)
        self._ip = device_ip
        self._id = device_id
        self._port = device_port
        self._keep_last_known_online_state = False
        self._type = 0xac
        self._updating = False
        self._defer_update = False
        self._half_temp_step = False
        self._support = False
        self._online = True
        self._active = True
        self._protocol_version = 2
        self._token = None
        self._key = None
        self._last_responses = []

    def authenticate(self, key: str, token: str):
        # compatible example.py
        if key != "YOUR_AC_K1" and token != "YOUR_AC_TOKEN":
            self._protocol_version = 3
            self._token = bytearray.fromhex(token)
            self._key = bytearray.fromhex(key)
            return self._authenticate()
        return False

    def _authenticate(self):
        return self._lan_service.authenticate(self._token, self._key)

    def set_device_detail(self, device_detail: dict):
        '''set device detail'''
        self._ip = device_detail.get('host', self._ip)
        self._port = device_detail.get('port', 6444)
        self._id = device_detail.get('id', self._id)
        token = device_detail.get('token', "")
        self._token = bytearray.fromhex(token)
        key = device_detail.get('key', "")
        self._key = bytearray.fromhex(key)
        self._type = device_detail.get('type', self._type)
        self._protocol_version = device_detail.get(
            'version', self._protocol_version)

        self._lan_service = lan(self._ip, self._id, self._port)
        self._lan_service._key = self._key
        self._lan_service._token = self._token

        self._name = device_detail.get('name', self._name)
        self._ssid = device_detail.get('ssid', None)
        self._model = device_detail.get('model', None)
        self._sn = device_detail.get('sn', None)

    def refresh(self):
        pass

    def apply(self):
        pass

    def send_cmd(self, cmd):
        pkt_builder = packet_builder(self.id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        _LOGGER.debug(
            "pkt_builder: %s:%d len: %d data: %s", self.ip, self.port, len(data), data.hex())
        send_time = time.time()
        if self._protocol_version == 3:
            responses = self._lan_service.appliance_transparent_send_8370(data)
        else:
            responses = self._lan_service.appliance_transparent_send(data)
        request_time = round(time.time() - send_time, 2)
        _LOGGER.debug(
            "Got responses from %s:%d Version: %d Count: %d Spend time: %f", self.ip, self.port, self._protocol_version, len(responses), request_time)
        if len(responses) == 0:
            _LOGGER.warning(
                "Got Null from %s:%d Version: %d Count: %d Spend time: %f", self.ip, self.port, self._protocol_version, len(responses), request_time)
            self._active = False
            self._support = False
        # sort, put CMD_TYPE_QUERRY last, so we can get END(machine_status) from the last response
        responses.sort()
        self._last_responses = responses
        return responses

    def process_response(self, data):
        _LOGGER.debug("Update from %s:%d %s", self.ip, self.port, data.hex())
        if len(data) > 0:
            self._online = True
            self._active = True
            if data == b'ERROR':
                self._support = False
                _LOGGER.warning("Got ERROR from %s, %s", self.ip, self.id)
                return
            return data

    @property
    def id(self):
        return self._id

    @property
    def type(self):
        return self._type

    @property
    def ip(self):
        return self._ip

    @property
    def port(self):
        return self._port

    @property
    def name(self):
        return self._name

    @property
    def ssid(self):
        return self._ssid

    @property
    def model(self):
        return self._model

    @property
    def sn(self):
        return self._sn

    @property
    def active(self):
        return self._active

    @property
    def online(self):
        return self._online

    @property
    def support(self):
        return self._support

    @property
    def keep_last_known_online_state(self):
        return self._keep_last_known_online_state

    @keep_last_known_online_state.setter
    def keep_last_known_online_state(self, feedback: bool):
        self._keep_last_known_online_state = feedback

    @property
    def last_responses(self):
        return ','.join(b.hex() for b in self._last_responses)
