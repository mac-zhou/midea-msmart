# midea-msmart
A Python library to enable local communication with Midea (and associated brands) smart air conditioners.

![Code Quality Badge](https://github.com/mill1000/midea-msmart/actions/workflows/checks.yml/badge.svg?branch=future)

## Gratitude
This project is a fork of [mac-zhou/midea-msmart](https://github.com/mac-zhou/midea-msmart), and builds upon the work of
* [dudanov/MideaUART](https://github.com/dudanov/MideaUART)
* [NeoAcheron/midea-ac-py](https://github.com/NeoAcheron/midea-ac-py)
* [andersonshatch/midea-ac-py](https://github.com/andersonshatch/midea-ac-py)
* [yitsushi/midea-air-condition](https://github.com/yitsushi/midea-air-condition)

## Installing
Install this fork via pip.
```shell
pip install git+https://github.com/mill1000/midea-msmart.git@future
```

## Usage
Discover all devices on the LAN with the `midea-discover` command.

e.g.
```shell
$ midea-discover 
INFO:msmart.cli:msmart version: 0.2.6.dev33+g97533b9 Currently only supports ac devices, only support MSmartHome and 美的美居 APP.
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
