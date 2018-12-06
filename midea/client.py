# This library is part of an effort to get Midea air conditioning devices to work with Home Assistant
# This library is based off the work by Yitsushi. The original work was a ruby based commandline utility.
# The orignal Ruby version can be found here https://github.com/yitsushi/midea-air-condition
# License MIT - Use as you please and at your own risk

from typing import Dict, List

from midea.cloud import cloud
from midea.device import air_conditioning_device
from midea.device import dehumidifier_device
from midea.device import unknown_device

DEVICE_TYPES = {
    0xAC: air_conditioning_device,
    0x00: dehumidifier_device
}


def build_device(cloud_service: cloud, device_detail: dict):
    device_type = int(device_detail['type'], 0)
    device_constructor = DEVICE_TYPES.get(device_type, None)
    if device_constructor is not None:
        device = device_constructor(cloud_service)
    else:
        device = unknown_device(cloud_service)        
    device.set_device_detail(device_detail)
    return device


class client:

    def __init__(self, appKey: str, email: str, password: str):
        self._cloud = cloud(appKey, email, password)
        self._devices = {}  # type: Dict[str, device]

    def setup(self):
        if self._cloud.loginId is None:
            self._cloud.login()

    def devices(self):
        self.setup()

        device_status_list = self._cloud.list()
        for device_status in device_status_list:
            current_device_id = device_status['id']
            current_device = self._devices.setdefault(current_device_id, None)
            if current_device is None:
                current_device = build_device(self._cloud, device_status)
                self._devices[current_device_id] = current_device
            else:
                current_device.set_device_detail(device_status)

        return list(self._devices.values())

