
# -*- coding: UTF-8 -*-
import click
import logging
import socket
import sys
from msmart.security import security
from msmart.device import air_conditioning_device as midea_device

if sys.version_info < (3, 5):
    print(
        "To use this script you need python 3.5 or newer, got %s" % (
            sys.version_info,)
    )
    sys.exit(1)

VERSION = '0.1.20'

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


@click.command()
@click.option("-d", "--debug", default=False, count=True)
# @click.pass_context
def discover(debug: int):
    """Discover Midea Devices with UDP Broadcast"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        _LOGGER.info("Debug mode active")
    else:
        logging.basicConfig(level=logging.INFO)

    _security = security()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(5)
    found_devices = {}
    _LOGGER.info("msmart version: {}".format(VERSION))
    _LOGGER.info(
        "Discovering devices with UDP Broadcast, press CTRL-C to quit...")
    for i in range(10):
        try:
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", 6445))
            while True:
                data, addr = sock.recvfrom(512)
                m_ip = addr[0]
                m_protocol = 2
                if m_ip in found_devices:
                    continue
                if data[:2] == bytes([0x83, 0x70]):
                    data = data[8:-16]
                    m_protocol = 3
                if data[:2] == bytes([0x5a, 0x5a]) and len(data) >= 104:
                    _LOGGER.info("Midea Local Data {} {}".format(m_ip, data.hex()))
                    m_id = int.from_bytes(data[20:26], 'little')
                    found_devices[m_ip] = m_id
                    encrypt_data = data[40:-16]
                    reply = _security.aes_decrypt(encrypt_data)

                    m_ip = '.'.join([str(i) for i in reply[3::-1]])
                    m_port = int.from_bytes(reply[4:8], 'little')
                    m_sn = reply[8:40].decode()
                    # ssid like midea_xx_xxxx net_xx_xxxx
                    m_ssid_len = reply[40]
                    m_ssid = reply[41:41+m_ssid_len].decode()
                    m_id_reserve = reply[43+m_ssid_len]
                    b = reply[44+m_ssid_len]
                    m_enable_extra = (b >> 7) == 1
                    m_support_extra_auth = (b & 1) == 1
                    m_support_extra_channel = (b & 2) == 2
                    m_support_extra_last_error_code = (b & 4) == 4
                    m_extra_high = reply[45+m_ssid_len]
                    m_udp_version = int.from_bytes(reply[46+m_ssid_len:50+m_ssid_len], 'little')
                    m_type = reply[55+m_ssid_len:56+m_ssid_len].hex()
                    m_subtype = int.from_bytes(reply[57+m_ssid_len:59+m_ssid_len], 'little')
                    m_mac = reply[63+m_ssid_len:69+m_ssid_len].hex()
                    m_protocol_version = reply[69+m_ssid_len:75+m_ssid_len].hex()
                    m_random_code = reply[78+m_ssid_len:94+m_ssid_len]

                    if m_protocol == 2:
                        m_support = support_test(m_ip, m_id)
                    else:
                        m_support = 'supported'

                    _LOGGER.info(
                        "*** Found a {} '{}' ({}) at {}:{} - id: {} - sn: {} - ssid: {} - mac: {} - protocol: {}".format(m_support, m_type, m_subtype, m_ip, m_port, m_id, m_sn, m_ssid, m_mac, m_protocol))

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            sys.exit(0)


def support_test(device_ip, device_id: int):
    device = midea_device(device_ip, device_id)
    device.refresh()
    if device.support:
        return 'supported'
    else:
        return 'unsupported'

# if __name__ == '__main__':
#     discover()
