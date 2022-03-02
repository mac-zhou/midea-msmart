
from msmart.device import air_conditioning_device as ac
from msmart.device.base import device
import logging
import time
logging.basicConfig(level=logging.DEBUG)

# first take device's ip and id, port is generally 6444
# pip3 install msmart; midea-discover
device = ac('YOUR_AC_IP', int('YOUR_AC_ID'), 6444)
# If the device is using protocol 3 (aka 8370)
# you must authenticate with device's k1 and token.
# adb logcat | grep doKeyAgree
device.authenticate('YOUR_AC_K1', 'YOUR_AC_TOKEN')
# Refresh the object with the actual state by querying it
device.refresh()
print({
    'id': device.id,
    'name': device.ip,
    'power_state': device.power_state,
    'prompt_tone': device.prompt_tone,
    'target_temperature': device.target_temperature,
    'operational_mode': device.operational_mode,
    'fan_speed': device.fan_speed,
    'swing_mode': device.swing_mode,
    'eco_mode': device.eco_mode,
    'turbo_mode': device.turbo_mode,
    'indoor_temperature': device.indoor_temperature,
    'outdoor_temperature': device.outdoor_temperature
})

# Set the state of the device and
device.prompt_tone = True
device.power_state = True
device.prompt_tone = False
device.target_temperature = 25
device.operational_mode = ac.operational_mode_enum.cool
time.sleep(1)
# commit the changes with apply()
device.apply()
print({
    'id': device.id,
    'name': device.ip,
    'power_state': device.power_state,
    'prompt_tone': device.prompt_tone,
    'target_temperature': device.target_temperature,
    'operational_mode': device.operational_mode,
    'fan_speed': device.fan_speed,
    'swing_mode': device.swing_mode,
    'eco_mode': device.eco_mode,
    'turbo_mode': device.turbo_mode,
    'indoor_temperature': device.indoor_temperature,
    'outdoor_temperature': device.outdoor_temperature
}) 
