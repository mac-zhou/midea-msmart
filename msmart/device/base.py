
import logging
from msmart.lan import lan

VERSION = '0.2.2'

_LOGGER = logging.getLogger(__name__)


def convert_device_id_hex(device_id: int):
    return device_id.to_bytes(6, 'little').hex()


def convert_device_id_int(device_id: str):
    return int.from_bytes(bytes.fromhex(device_id), 'little')


class device:
    
    def __init__(self, device_ip: str, device_id: int, device_port: int):
        # device_id = convert_device_id_hex(device_id)
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
        self._id = device_detail['id']
        self._name = device_detail['name']
        self._model_number = device_detail['modelNumber']
        self._serial_number = device_detail['sn']
        self._type = int(device_detail['type'], 0)
        self._active = device_detail['activeStatus'] == '1'
        self._online = device_detail['onlineStatus'] == '1'

    def refresh(self):
        pass

    def apply(self):
        pass

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
    def model_number(self):
        return self._model_number

    @property
    def serial_number(self):
        return self._serial_number

    @property
    def type(self):
        return self._type

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
