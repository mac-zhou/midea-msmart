
from abc import ABC, abstractmethod
import logging
import time
from msmart.lan import lan
from msmart.packet_builder import packet_builder


_LOGGER = logging.getLogger(__name__)


class device(ABC):

    def __init__(self, *, ip: str, port: int, id: int, name: str, type: int, sn: str = None):
        self._ip = ip
        self._port = port

        self._id = id
        self._sn = sn
        self._name = name
        self._type = type

        # For V3 devices
        self._token = None
        self._key = None

        self._lan_service = lan(ip, id, port)

    def authenticate(self, token: str = None, key: str = None):
        # Use existing token and key if none provied
        if token is None or key is None:
            token = self._token
            key = self._key

        def convert(x):
            if isinstance(x, str):
                return bytes.fromhex(x)

        success = self._lan_service.authenticate(convert(token), convert(key))

        # Update token and key if successful
        if success:
            self._token = token
            self._key = key

        return success

    @abstractmethod
    def refresh(self):
        pass

    @abstractmethod
    def apply(self):
        pass

    def send_cmd(self, cmd):
        pkt_builder = packet_builder(self.id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        _LOGGER.debug(
            "pkt_builder: %s:%d len: %d data: %s", self.ip, self.port, len(data), data.hex())
        send_time = time.time()

        responses = self._lan_service.send(data)

        request_time = round(time.time() - send_time, 2)
        _LOGGER.debug(
            "Got responses from %s:%d Version: %d Count: %d Spend time: %f", self.ip, self.port, self._lan_service.protocol_version, len(responses), request_time)
        if len(responses) == 0:
            _LOGGER.warning(
                "Got Null from %s:%d Version: %d Count: %d Spend time: %f", self.ip, self.port, self._lan_service.protocol_version, len(responses), request_time)
            self._active = False
            self._support = False
        
        # sort, put CMD_TYPE_QUERRY last, so we can get END(machine_status) from the last response
        responses.sort()
        
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
    def ip(self) -> str:
        return self._ip

    @property
    def port(self) -> int:
        return self._port

    @property
    def id(self) -> int:
        return self._id

    @property
    def type(self) -> str:
        return self._type

    @property
    def name(self) -> str:
        return self._name

    @property
    def sn(self) -> str:
        return self._sn

    def __str__(self) -> str:
        return f"{self.ip}:{self.port} Type: {self.type} ID: {self.id}"
