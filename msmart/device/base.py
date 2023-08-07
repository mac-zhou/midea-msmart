
from abc import ABC, abstractmethod
import logging
import time
from msmart.lan import LAN, ProtocolError
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
        raise NotImplementedError()

    @abstractmethod
    async def apply(self):
        raise NotImplementedError()

    async def authenticate(self, token, key):
        return await self._lan.authenticate(token, key)

    async def send_command(self, cmd):
        # TODO push this logic into the LAN module
        pkt_builder = packet_builder(self.id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        _LOGGER.debug(
            "pkt_builder: %s:%d len: %d data: %s", self.ip, self.port, len(data), data.hex())

        start = time.time()
        response = None
        try:
            response = await self._lan.send(data)
        except (ProtocolError, TimeoutError) as e:
            _LOGGER.error(e)
        finally:
            response_time = round(time.time() - start, 2)

        if response is None:
            _LOGGER.warning("No response from %s:%d in %f seconds. ",
                            self.ip, self.port, response_time)
            return None

        _LOGGER.debug("Response from %s:%d in %f seconds.",
                      self.ip, self.port, response_time)

        return response

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
    def type(self) -> str | None:
        return self._type

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def sn(self) -> str | None:
        return self._sn

    @property
    def online(self) -> bool:
        return self._online

    def __str__(self) -> str:
        return f"{self.ip}:{self.port} Type: {self.type} ID: {self.id}"
