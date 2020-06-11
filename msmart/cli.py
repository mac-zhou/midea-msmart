import click
import logging
import socket
import sys
from msmart.security import security
from msmart.device import convert_device_id_int
from msmart.device import device as midea_device

if sys.version_info < (3, 5):
    print(
        "To use this script you need python 3.5 or newer, got %s" % (
            sys.version_info,)
    )
    sys.exit(1)

VERSION = '0.1.17'

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
    _LOGGER.info(
        "Discovering devices with UDP Broadcast, press CTRL-C to quit...")
    for i in range(10):
        try:
            sock.sendto(BROADCAST_MSG, ("255.255.255.255", 6445))
            while True:
                data, addr = sock.recvfrom(512)
                m_ip = addr[0]
                if len(data) >= 41 and m_ip not in found_devices:
                    m_id = convert_device_id_int(data[20:26].hex())
                    found_devices[m_ip] = m_id
                    data = data[40:40+64]
                    reply = _security.aes_decrypt(data)

                    m_sn = reply[14:14+26].decode("utf-8")
                    m_ssid = reply[14+27:].decode("utf-8")
                    m_type = m_ssid.split('_')[1]
                    m_support = 'unknown'
                    if m_type == 'ac':
                        m_support = support_test(m_ip, int(m_id))

                    _LOGGER.info(
                        "Found a {} '0x{}' at {} - id: {} - sn: {} - ssid: {}".format(m_support, m_type, m_ip, m_id, m_sn, m_ssid))

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            sys.exit(0)


def support_test(device_ip, device_id: int):
    _device = midea_device(device_ip, device_id)
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


# if __name__ == '__main__':
#     discover()
