import argparse
import asyncio
import logging

from msmart import __version__
from msmart.const import OPEN_MIDEA_APP_ACCOUNT, OPEN_MIDEA_APP_PASSWORD
from msmart.discover import Discover

_LOGGER = logging.getLogger(__name__)


async def _discover(ip: str, count: int, account: str, password: str, china: bool, **_kwargs) -> None:
    """Discover Midea devices and print configuration information."""

    _LOGGER.info("msmart version: %s", __version__)
    _LOGGER.info(
        "Only supports AC devices. Only supports MSmartHome and 美的美居.")

    if china and (account == OPEN_MIDEA_APP_ACCOUNT or password == OPEN_MIDEA_APP_PASSWORD):
        _LOGGER.error(
            "To use China server set account (phone number) and password of 美的美居.")
        exit(1)

    devices = []
    if ip is None or ip == "":
        devices = await Discover.discover(account=account, password=password, discovery_packets=count)
    else:
        dev = await Discover.discover_single(ip, account=account, password=password, discovery_packets=count)
        if dev:
            devices.append(dev)

    if len(devices) == 0:
        _LOGGER.error("No devices found.")
        return

    _LOGGER.info("Found %d devices.", len(devices))
    for device in devices:
        _LOGGER.info("Found device:\n%s", device)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Midea devices and print device information.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-d", "--debug", help="Enable debug logging.", action="store_true")
    parser.add_argument(
        "-a", "--account", help="MSmartHome or 美的美居 account username.", default=OPEN_MIDEA_APP_ACCOUNT)
    parser.add_argument(
        "-p", "--password", help="MSmartHome or 美的美居 account password.", default=OPEN_MIDEA_APP_PASSWORD)
    parser.add_argument(
        "-i", "--ip", help="IP address of a device. Useful if broadcasts don't work, or to query a single device.")
    parser.add_argument(
        "-c", "--count", help="Number of broadcast packets to send.", default=3, type=int)
    parser.add_argument("--china", help="Use China server.",
                        action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        # Keep httpx as info level
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("httpcore").setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)
        # Set httpx to warning level
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    try:
        asyncio.run(_discover(**vars(args)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
