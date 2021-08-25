
# -*- coding: UTF-8 -*-
import click
import logging
import socket
import sys
import hashlib
import os
import ctypes
from msmart.security import security
from msmart.security import get_udpid
from msmart.device import air_conditioning_device as ac
from msmart.cloud import cloud
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

if sys.version_info < (3, 5):
    print(
        "To use this script you need python 3.5 or newer, got %s" % (
            sys.version_info,)
    )
    sys.exit(1)

VERSION = '0.1.31'

Client = None
Account = ''
Password = ''

_LOGGER = logging.getLogger(__name__)

BROADCAST_MSG = bytearray([
    0x5a, 0x5a, 0x01, 0x11, 0x48, 0x00, 0x92, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x7f, 0x75, 0xbd, 0x6b, 0x3e, 0x4f, 0x8b, 0x76,
    0x2e, 0x84, 0x9c, 0x6e, 0x57, 0x8d, 0x65, 0x90,
    0x03, 0x6e, 0x9d, 0x43, 0x42, 0xa5, 0x0f, 0x1f,
    0x56, 0x9e, 0xb8, 0xec, 0x91, 0x8e, 0x92, 0xe5
])

DEVICE_INFO_MSG = bytearray([
    0x5a, 0x5a, 0x15, 0x00, 0x00, 0x38, 0x00, 0x04,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x27, 0x33, 0x05,
    0x13, 0x06, 0x14, 0x14, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x03, 0xe8, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xca, 0x8d, 0x9b, 0xf9, 0xa0, 0x30, 0x1a, 0xe3,
    0xb7, 0xe4, 0x2d, 0x53, 0x49, 0x47, 0x62, 0xbe
])


class scandevice:

    def __init__(self):
        self.type = 'unknown'
        self.support = False
        self.version = 0
        self.ip = None
        self.id = None
        self.port = None
        self.token = None
        self.key = None
        self.ssid = None
        
        
    def __str__(self):
        return str(self.__dict__)


@click.command()
@click.option("-d", "--debug", default=False, count=True)
@click.option("-c", "--count", default=1, help='Number of broadcast paktes, default is 1.\
                                                if you have many devices, you may change this vaule.')
@click.option("-a", "--account", default='midea_is_best@outlook.com', help='Your email address for your Midea account.')
@click.option("-p", "--password", default='lovemidea4ever', help='Your password for your Midea account.')
# @click.pass_context
def discover(debug: int, count: int, account:str, password:str):
    global Account, Password
    Account, Password = account, password
    """Send Device Scan Broadcast"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        _LOGGER.info("Debug mode active")
    else:
        logging.basicConfig(level=logging.INFO)

    _security = security()
    

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        # Will be raised when executed in Windows. Safe to ignore.
        pass

    sock.settimeout(5)
    found_devices = {}
    _LOGGER.info("msmart version: {} Currently only supports ac devices.".format(VERSION))
    _LOGGER.info(
        "Sending Device Scan Broadcast...")
    for i in range(int(count)):
        try:
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", 6445))
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", 20086))
            while True:
                data, addr = sock.recvfrom(512)
                m_ip = addr[0]
                if m_ip in found_devices:
                    continue
                if len(data) >= 104 and (data[:2].hex() == '5a5a' or data[8:10].hex() == '5a5a'):
                    _LOGGER.debug(
                        "Midea Local Data {} {}".format(m_ip, data.hex()))
                    device = scandevice()
                    if data[:2].hex() == '5a5a':
                        device.version = 2
                    if data[:2].hex() == '8370':
                        device.version = 3
                    if data[8:10].hex() == '5a5a':
                        data = data[8:-16]

                    device.id = int.from_bytes(data[20:26], 'little')
                    found_devices[m_ip] = device.id
                    encrypt_data = data[40:-16]
                    reply = _security.aes_decrypt(encrypt_data)
                    _LOGGER.debug(
                        "Decrypt Reply: {} {}".format(m_ip, reply.hex()))
                    device.ip = '.'.join([str(i) for i in reply[3::-1]])
                    device.port = int.from_bytes(reply[4:8], 'little')
                    # ssid like midea_xx_xxxx net_xx_xxxx
                    device.ssid = reply[41:41+reply[40]].decode("utf-8")
                    device.type = device.ssid.split('_')[1]
                    support_test(device)
                    _LOGGER.info("*** Found a device: \033[94m\033[1m{} \033[0m".format(device))

                if data[:6].hex() == '3c3f786d6c20':
                    m_version = 'V1'
                    root = ET.fromstring(data.decode(
                        encoding="utf-8", errors="replace"))
                    child = root.find('body/device')
                    m = child.attrib
                    m_port, m_sn, m_type = m['port'], m['apc_sn'], str(
                        hex(int(m['apc_type'])))[2:]
                    response = get_device_info(m_ip, int(m_port))
                    m_id = get_id_from_response(response)

                    _LOGGER.info(
                        "\033[94m\033[1m*** Found a {} device - type: '0x{}' - version: {} - ip: {} - port: {} - id: {} - sn: {} - ssid: {} \033[0m".format(m_support, m_type, m_version, m_ip, m_port, m_id, m_sn, m_ssid))

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            sys.exit(0)


def get_id_from_response(response):
    if response[64:-16][:6].hex() == '3c3f786d6c20':
        xml = response[64:-16]
        root = ET.fromstring(xml.decode(encoding="utf-8", errors="replace"))
        child = root.find('smartDevice')
        m = child.attrib
        return int.from_bytes(bytearray.fromhex(m['devId']), 'little')
    else:
        return 0


def get_device_info(device_ip, device_port: int):
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(8)

    try:
        # Connect the Device
        device_address = (device_ip, device_port)
        sock.connect(device_address)

        # Send data
        _LOGGER.debug("Sending to {}:{} {}".format(
            device_ip, device_port, DEVICE_INFO_MSG.hex()))
        sock.sendall(DEVICE_INFO_MSG)

        # Received data
        response = sock.recv(512)
    except socket.error:
        _LOGGER.info("Couldn't connect with Device {}:{}".format(
            device_ip, device_port))
        return bytearray(0)
    except socket.timeout:
        _LOGGER.info("Connect the Device {}:{} TimeOut for 8s. don't care about a small amount of this. if many maybe not support".format(
            device_ip, device_port))
        return bytearray(0)
    finally:
        sock.close()
    _LOGGER.debug("Received from {}:{} {}".format(
        device_ip, device_port, response.hex()))
    return response


def support_test(device: scandevice):
    if device.version == 3:
        _device = support_testv3(device)
    else:
        _device = ac(device.ip, device.id, device.port)
    if device.type == 'ac':
        _device.refresh()
        _LOGGER.debug("{}".format(_device))
        device.support = _device.support

def support_testv3(device: scandevice):
    _device = ac(device.ip, device.id, device.port)
    for udpid in [get_udpid(device.id.to_bytes(6, 'little')), get_udpid(device.id.to_bytes(6, 'big'))]:
        token, key = gettoken(udpid)
        auth = _device.authenticate(key, token)
        if auth:
            device.token, device.key = token, key
            return _device
    return _device

def gettoken(udpid):
    global Client
    if Client is None:
        Client = cloud(Account, Password)
    if Client.session == {}:
        Client.login()
    return Client.gettoken(udpid)
    

def remove_duplicates(device_list: list):
    newlist = []
    for i in device_list:
        if i not in newlist:
            newlist.append(i)
    return newlist


def id2udpid(data):
    b = hashlib.sha256(data).digest()
    b1, b2 = b[:16], b[16:]
    b3 = bytearray(16)
    i = 0
    while i < len(b1):
        b3[i] = b1[i] ^ b2[i]
        i += 1
    return b3


# if __name__ == '__main__':
#     discover()
