
# -*- coding: UTF-8 -*-
import asyncio
from msmart.const import OPEN_MIDEA_APP_ACCOUNT, OPEN_MIDEA_APP_PASSWORD
import click
import logging
import sys
from msmart.scanner import MideaDiscovery
import os

if sys.version_info < (3, 5):
    print(
        "To use this script you need python 3.5 or newer, got %s" % (
            sys.version_info,)
    )
    sys.exit(1)

VERSION = '0.2.5'

_LOGGER = logging.getLogger(__name__)

@click.command()
@click.option("-d", "--debug", default=False, count=True, help='Enable debug logging')
@click.option("-cn", "--china", default=False, count=True, help='Use china server')
@click.option("-c", "--amount", default=1, help='Number of broadcast packets, default is 1.\
                                                if you have many devices, you may change this value.')
@click.option("-a", "--account", default=OPEN_MIDEA_APP_ACCOUNT, help='Your account of MSmartHome or 美的美居 APP.')
@click.option("-p", "--password", default=OPEN_MIDEA_APP_PASSWORD, help='Your password of MSmartHome or 美的美居APP.')
@click.option("-i", "--ip", default='', help="IP address of Midea device. you can use: \
                                                - broadcasts don't work. \
                                                - just get one device's info. \
                                                - an error occurred.")
# @click.pass_context
def discover(debug: bool, amount: int, account:str, password:str, ip: str, china: bool):
    """Discover Midea Deivces and Get Device's info"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        _LOGGER.info("Debug mode active")
    else:
        logging.basicConfig(level=logging.INFO)
    _LOGGER.info("msmart version: {} Currently only supports ac devices, only support MSmartHome and 美的美居 APP.".format(VERSION))
    os.environ['USE_CHINA_SERVER']=str(china)
    if china:
        if account == OPEN_MIDEA_APP_ACCOUNT or password == OPEN_MIDEA_APP_PASSWORD:
            _LOGGER.error("if you want to use china server, you need to set account(phone number) and password of 美的美居.")
            sys.exit(1)

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
