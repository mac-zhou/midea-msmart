import asyncio
import logging

from msmart.device import AirConditioner as AC
from msmart.discover import Discover

logging.basicConfig(level=logging.INFO)

DEVICE_IP = "YOUR_DEVICE_IP"
DEVICE_PORT = 6444
DEVICE_ID = "YOUR_AC_ID"

# For V3 devices
DEVICE_TOKEN = None  # "YOUR_DEVICE_TOKEN"
DEVICE_KEY = None  # "YOUR_DEVICE_KEY"


async def main():

    # There are 2 ways to connect

    # Discover.discover_single can automatically construct a device from IP or hostname
    #  - V3 devices will be automatically authenticated
    #  - The Midea cloud will be accessed for V3 devices to fetch the token and key
    # device = await Discover.discover_single(DEVICE_IP)

    # Manually construct the device
    #  - See midea-discover to read ID, token and key
    device = AC(ip=DEVICE_IP, port=6444, device_id=int(DEVICE_ID))
    if DEVICE_TOKEN and DEVICE_KEY:
        await device.authenticate(DEVICE_TOKEN, DEVICE_KEY)

    # Get device capabilities
    await device.get_capabilities()

    # Refresh the state
    await device.refresh()

    print({
        'id': device.id,
        'ip': device.ip,
        "online": device.online,
        "supported": device.supported,
        'power_state': device.power_state,
        'beep': device.beep,
        'target_temperature': device.target_temperature,
        'operational_mode': device.operational_mode,
        'fan_speed': device.fan_speed,
        'swing_mode': device.swing_mode,
        'eco_mode': device.eco_mode,
        'turbo_mode': device.turbo_mode,
        'fahrenheit': device.fahrenheit,
        'indoor_temperature': device.indoor_temperature,
        'outdoor_temperature': device.outdoor_temperature
    })

    await asyncio.sleep(1)

    # Change some device properties and apply them
    device.power_state = True
    device.beep = False
    device.target_temperature = 25
    device.operational_mode = AC.OperationalMode.COOL
    await device.apply()

    print({
        'id': device.id,
        'ip': device.ip,
        "online": device.online,
        "supported": device.supported,
        'power_state': device.power_state,
        'beep': device.beep,
        'target_temperature': device.target_temperature,
        'operational_mode': device.operational_mode,
        'fan_speed': device.fan_speed,
        'swing_mode': device.swing_mode,
        'eco_mode': device.eco_mode,
        'turbo_mode': device.turbo_mode,
        'fahrenheit': device.fahrenheit,
        'indoor_temperature': device.indoor_temperature,
        'outdoor_temperature': device.outdoor_temperature
    })

if __name__ == "__main__":
    asyncio.run(main())
