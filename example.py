
import logging
import time
from msmart.device import air_conditioning as ac

logging.basicConfig(level=logging.DEBUG)

# Manually construct device. Async functions may use Discover.discover_single("YOUR_AC_IP")
# See midea-discover to read ID, token and key
# Prefer to use named args
device = ac(ip='YOUR_AC_IP', port=6444, id=int('YOUR_AC_ID'))
# But position args will work
# device = ac('YOUR_AC_IP', int('YOUR_AC_ID'), 6444)

# V3 devices require authentication
device.authenticate('YOUR_AC_TOKEN', 'YOUR_AC_KEY')

# Refresh the object with the actual state by querying it
device.get_capabilities()
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
    'fahrenheit': device.fahrenheit,
    'indoor_temperature': device.indoor_temperature,
    'outdoor_temperature': device.outdoor_temperature
})

time.sleep(1)

# Set the state of the device and
device.power_state = True
device.prompt_tone = False
device.target_temperature = 25
device.operational_mode = ac.operational_mode_enum.cool
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
