
from msmart.device import device as midea_device
from msmart.device import air_conditioning_device as ac
import logging
logging.basicConfig(level=logging.DEBUG)

# first take device's ip and id
# pip3 install msmart; midea-discover
c = midea_device('YOUR_AC_IP', YOUR_AC_ID)
device = c.setup()
# If the device is using protocol 3 (aka 8370), you must authenticate with your
# WiFi network's credentials for local control
device.authenticate('YOUR_AC_MAC', 'YOUR_WIFI_SSID', 'YOUR_WIFI_PW')
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
device.power_state = True
device.prompt_tone = False
device.target_temperature = 25
device.operational_mode = ac.operational_mode_enum.cool

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

