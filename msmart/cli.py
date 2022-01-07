
# -*- coding: UTF-8 -*-
import asyncio
from msmart.const import OPEN_MIDEA_APP_ACCOUNT, OPEN_MIDEA_APP_PASSWORD
import click
import logging
import sys
from msmart.scanner import MideaDiscovery

if sys.version_info < (3, 5):
    print(
        "To use this script you need python 3.5 or newer, got %s" % (
            sys.version_info,)
    )
    sys.exit(1)

VERSION = '0.2.0'

_LOGGER = logging.getLogger(__name__)

@click.command()
@click.option("-d", "--debug", default=False, count=True, help='Enable debug logging')
@click.option("-c", "--amount", default=1, help='Number of broadcast packets, default is 1.\
                                                if you have many devices, you may change this value.')
@click.option("-a", "--account", default=OPEN_MIDEA_APP_ACCOUNT, help='Your email address for your Midea account.')
@click.option("-p", "--password", default=OPEN_MIDEA_APP_PASSWORD, help='Your password for your Midea account.')
@click.option("-i", "--ip", default='', help="IP address of Midea device. you can use: \
                                                - broadcasts don't work. \
                                                - just get one device's info. \
                                                - an error occurred.")
# @click.pass_context
def discover(debug: bool, amount: int, account:str, password:str, ip: str):
    """Discover Midea Deivces and Get Device's info"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        _LOGGER.info("Debug mode active")
    else:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.info("msmart version: {} Currently only supports ac devices.".format(VERSION))
    
    try:
        discovery = MideaDiscovery(account=account, password=password, amount=amount)
        loop = asyncio.new_event_loop()
        found_devices = loop.run_until_complete(discovery.get_all() if ip == '' else discovery.get(ip))
        loop.close()
        if not found_devices:
            _LOGGER.error("*** \033[0;31mDevice not found, please read: https://github.com/mac-zhou/midea-ac-py#how-to-get-configuration-variables \033[0m")
        else:
            for device in found_devices:
                _LOGGER.info("*** Found a device: \033[94m\033[1m{} \033[0m".format(device))
    except KeyboardInterrupt:
        sys.exit(0)

# if __name__ == '__main__':
#     discover()
