
# -*- coding: UTF-8 -*-
import click
import logging
import socket
import sys
import os
import ctypes
from msmart.security import security
from msmart.device import convert_device_id_int
from msmart.device import device as midea_device
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

VERSION = '0.1.25'

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


@click.command()
@click.option("-d", "--debug", default=False, count=True)
# @click.pass_context
def discover(debug: int):
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
    _LOGGER.info("msmart version: {}".format(VERSION))
    _LOGGER.info(
        "Sending Device Scan Broadcast...")
    for i in range(10):
        try:
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", 6445))
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", 20086))
            while True:
                data, addr = sock.recvfrom(512)
                m_ip = addr[0]
                if m_ip in found_devices:
                    continue
                m_id, m_type, m_sn, m_ssid, m_version, m_support = 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown'
                if len(data) >= 104 and (data[:2].hex() == '5a5a' or data[8:10].hex() == '5a5a'):
                    _LOGGER.info("Midea Local Data {} {}".format(m_ip, data.hex()))
                    data_string = data.decode("utf-8", errors="replace")
                    # _LOGGER.info(data.decode("utf-8", errors="replace"))
                    # root=ET.fromstring(data.decode(encoding="utf-8", errors="replace"))
                    if data[:2].hex() == '5a5a':
                        m_version = 'V2'
                    if data[:2].hex() == '8370':
                        m_version = 'V3'
                    if data[8:10].hex() == '5a5a':
                        data = data[8:-16]
                    m_id = convert_device_id_int(data[20:26].hex())
                    found_devices[m_ip] = m_id
                    encrypt_data = data[40:-16]
                    reply = _security.aes_decrypt(encrypt_data)
                    _LOGGER.info("Decrypt Reply: {} {}".format(m_ip, reply.hex()))
                    
                    m_ip = '.'.join([str(i) for i in reply[3::-1]])
                    m_port = str(bytes2port(reply[4:8]))
                    m_sn = reply[8:40].decode("utf-8")
                    # ssid like midea_xx_xxxx net_xx_xxxx
                    m_ssid = reply[41:41+reply[40]].decode("utf-8")
                    # if len(reply) > 54:

                    m_type = m_ssid.split('_')[1]
                    
                    m_support = support_test(m_ip, int(m_id), int(m_port))

                    _LOGGER.info(
                        "*** Found a {} device - type: '0x{}' - version: {} - ip: {} - port: {} - id: {} - sn: {} - ssid: {}".format(m_support, m_type, m_version, m_ip, m_port, m_id, m_sn, m_ssid))

                if data[:6].hex() == '3c3f786d6c20':
                    m_version = 'V1'
                    root=ET.fromstring(data.decode(encoding="utf-8", errors="replace"))
                    child = root.find('body/device')
                    m=child.attrib
                    m_port, m_sn, m_type  = m['port'], m['apc_sn'], str(hex(int(m['apc_type'])))[2:]
                    response = get_device_info(m_ip, int(m_port))
                    m_id = get_id_from_response(response)

                    _LOGGER.info(
                    "*** Found a {} device - type: '0x{}' - version: {} - ip: {} - port: {} - id: {} - sn: {} - ssid: {}".format(m_support, m_type, m_version, m_ip, m_port, m_id, m_sn, m_ssid))
  

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            sys.exit(0)

def get_id_from_response(response):
    if response[64:-16][:6].hex() == '3c3f786d6c20':
        xml = response[64:-16]
        root=ET.fromstring(xml.decode(encoding="utf-8", errors="replace"))
        child = root.find('smartDevice')
        m=child.attrib
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
        sock.sendall(message)

        # Received data
        response = sock.recv(512)
    except socket.error:
        _LOGGER.info("Couldn't connect with Device {}:{}".format(
            device_ip, device_port))
        return bytearray(0)
    except socket.timeout:
        _LOGGER.info("Connect the Device %s:%s TimeOut for 8s. don't care about a small amount of this. if many maybe not support".format(
            device_ip, device_port))
        return bytearray(0)
    finally:
        sock.close()
    _LOGGER.debug("Received from {}:{} {}".format(
        device_ip, device_port, message.hex()))
    return response

def support_test(device_ip, device_id: int, device_port: int):
    _device = midea_device(device_ip, device_id, device_port)
    device = _device.setup()
    device.refresh()
    if device.support:
        return 'supported'
    else:
        return 'unsupported'


def remove_duplicates(device_list: list):
    newlist = []
    for i in device_list:
        if i not in newlist:
            newlist.append(i)
    return newlist

def bytes2port(paramArrayOfbyte):
    if paramArrayOfbyte == None:
        return 0
    b, i = 0, 0
    while b < 4:
        if b < len(paramArrayOfbyte):
            b1 = paramArrayOfbyte[b] & 0xFF
        else:
            b1 = 0
        i |= b1 << b * 8
        b += 1
    return i

# if __name__ == '__main__':
#     discover()
