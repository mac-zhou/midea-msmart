
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

VERSION = '0.1.36'

_LOGGER = logging.getLogger(__name__)

@click.command()
@click.option("-d", "--debug", default=False, count=True)
@click.option("-c", "--amount", default=1, help='Number of broadcast paktes, default is 1.\
                                                if you have many devices, you may change this vaule.')
@click.option("-a", "--account", default=OPEN_MIDEA_APP_ACCOUNT, help='Your email address for your Midea account.')
@click.option("-p", "--password", default=OPEN_MIDEA_APP_PASSWORD, help='Your password for your Midea account.')
# @click.pass_context
def discover(debug: int, amount: int, account:str, password:str):
    """Send Device Scan Broadcast"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        _LOGGER.info("Debug mode active")
    else:
        logging.basicConfig(level=logging.INFO)

    _LOGGER.info("msmart version: {} Currently only supports ac devices.".format(VERSION))
    _LOGGER.info(
        "Sending Device Scan Broadcast...")
    
    try:
        discovery = MideaDiscovery(account=account, password=password, amount=amount)
        loop = asyncio.new_event_loop()
        found_devices = loop.run_until_complete(discovery.get_all())
        loop.close()
        
        for device in found_devices:
            _LOGGER.info("*** Found a device: \033[94m\033[1m{} \033[0m".format(device)) 
    except KeyboardInterrupt:
        sys.exit(0)


# if __name__ == '__main__':
#     discover()
