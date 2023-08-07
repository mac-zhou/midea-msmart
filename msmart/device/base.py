
from abc import ABC, abstractmethod
import logging
import time
from msmart.lan import LAN
from msmart.packet_builder import packet_builder


_LOGGER = logging.getLogger(__name__)


class device(ABC):

    def __init__(self, *, ip: str, port: int, id: int, **kwargs):
        self._ip = ip
        self._port = port

        self._id = id
        self._sn = kwargs.get("sn", None)
        self._name = kwargs.get("name", None)
        self._type = kwargs.get("type", None)

        self._lan = LAN(ip, port)
        self._support = False
        self._online = False

    @abstractmethod
    async def refresh(self):
        pass

    @abstractmethod
    async def apply(self):
        pass

    async def authenticate(self, token, key):
        return await self._lan.authenticate(token, key)

    async def send_command(self, cmd):
        pkt_builder = packet_builder(self.id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        _LOGGER.debug(
            "pkt_builder: %s:%d len: %d data: %s", self.ip, self.port, len(data), data.hex())
        send_time = time.time()

        responses = await self._lan.send(data)

        request_time = round(time.time() - send_time, 2)
        _LOGGER.debug(
            "Got responses from %s:%d Version: %d Count: %d Spend time: %f", self.ip, self.port, self._lan.protocol_version, len(responses), request_time)
        if len(responses) == 0:
            _LOGGER.warning(
                "Got Null from %s:%d Version: %d Count: %d Spend time: %f", self.ip, self.port, self._lan.protocol_version, len(responses), request_time)
            self._support = False

        # sort, put CMD_TYPE_QUERRY last, so we can get END(machine_status) from the last response
        responses.sort()

        return responses

    def process_response(self, data):
        _LOGGER.debug("Update from %s:%d %s", self.ip, self.port, data.hex())
        if len(data) > 0:
            self._online = True
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

    @property
    def online(self) -> bool:
        return self._online

    def __str__(self) -> str:
        return f"{self.ip}:{self.port} Type: {self.type} ID: {self.id}"
