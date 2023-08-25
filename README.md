# msmart-ng
A Python library for local control of Midea (and associated brands) smart air conditioners.

![Code Quality Badge](https://github.com/mill1000/midea-msmart/actions/workflows/checks.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/msmart-ng?logo=PYPI)

## Features
#### Async Support
The device, LAN and cloud classes have all been rewritten to support async/await syntax.

```python
from msmart.device import AirConditioner as AC

# Build device
device = AC(ip=DEVICE_IP, port=6444, device_id=int(DEVICE_ID))

# Get capabilities
await device.get_capabilities()

# Get current state
await device.refresh()
```

#### Device Discovery
A new discovery module can discover and return ready-to-use device objects from the network. A single device can be discovered by IP or hostname with the `discover_single` method.

__Note: V3 devices are automatically authenticated via the Midea cloud.__

```python
from msmart.discover import Discover

# Discover all devices on the network
devices = await Discover.discover()

# Discover a single device by IP
device = await Discover.discover_single(DEVICE_IP)
```

#### Less Dependencies
Some external dependencies have been replaced with standard Python modules.

#### Code Quality
- The majority of the code is now type annotated.
- Code style and import sorting are enforced by autopep8 and isort via Github Actions.
- Unit tests are implemented and executed by Github Actions.
- A number of unused methods and modules have been removed from the code.

## Installing
Use pip.
1. Remove old `msmart` package.
```shell
pip uninstall msmart
```

2. Install this fork `msmart-ng`.
```shell
pip install msmart-ng
```

## Usage
Discover all devices on the LAN with the `midea-discover` command.

e.g.
```shell
$ midea-discover 
INFO:msmart.cli:msmart version: 2023.8.0 Currently only supports ac devices, only support MSmartHome and 美的美居 APP.
INFO:msmart.cli:*** Found a device: {'name': 'net_ac_F7B4', 'ssid': 'net_ac_F7B4', 'ip': '10.100.1.140', 'port': 6444, 'id': 15393162840672, 'version': 2, 'token': None, 'key': None, 'type': 'ac', 'sn': '000P0000000Q1F0C9D153F7B40000', 'model': '00Q1F', 'support': True, 'run_test': True} 
```
Check the output to ensure the type is 0xAC and the `supported` property is True.

Save the device ID, IP address, and port. Version 3 devices will also require the `token` and `key` fields to control the device.


#### Note: V1 Device Owners
Users with V1 devices will see the following error:
```
ERROR:msmart.discover:V1 device not supported yet.
```
I don't have any V1 devices to test with so please create an issue with the output of `midea-discover -d`.

### Home Assistant
Use [this fork](https://github.com/mill1000/midea-ac-py) of midea-ac-py to control devices from Home Assistant.

### Python
See the included [example](example.py) for controlling devices from a script.

## Gratitude
This project is a fork of [mac-zhou/midea-msmart](https://github.com/mac-zhou/midea-msmart), and builds upon the work of
* [dudanov/MideaUART](https://github.com/dudanov/MideaUART)
* [NeoAcheron/midea-ac-py](https://github.com/NeoAcheron/midea-ac-py)
* [andersonshatch/midea-ac-py](https://github.com/andersonshatch/midea-ac-py)
* [yitsushi/midea-air-condition](https://github.com/yitsushi/midea-air-condition)
