# midea-ac-py

This is a library to allow communicating to a Midea AC via the Midea Cloud.

This is a very early release, and comes without any guarantees. This is still an early work in progress and simply serves as a proof of concept.

This library would not have been possible if it wasn't for the amazing work done by @yitsushi and his Ruby based command line tool. 
You can find his work here: https://github.com/yitsushi/midea-air-condition
The reasons for me converting this to Python is that this library also serves as a platform component for Home Assistant.

## Device Support
Unfortunately it is difficult to tell if your Air Conditioning unit will be supported, but generally any OEM that uses the OSK102 WiFi module and is 
compatible with the 'Nethome Plus' app. It doesn't mean you need a Midea air conditioning unit, I have a Carrier split unit installed.

You have to have a valid account with Midea in order to use this library. Local mode is not working yet.

## Home Assistant Usage
For now the installation is done manually in your configuration directory. This guide expects a basic understanding of Home Assistant and its configuration. 
You'll need to follow these steps in order to use this platform (All paths are relative to Home Assistant's configuration directory):

* Copy the entire `midea` directory from the repository to `./deps/`
* Create a directory `./custom_components/climate` if it doesn't exist
* Copy `midea.py` from the repository into `./custom_components/climate`
* Add the following configuration to your Home Assistant's `configuration.yaml` changing the username field:
```yaml
climate:
  - platform: midea
    app_key: 3742e9e5842d4ad59c2db887e12449f9
    username: 'foo@bar.com'
    password: !secret midea_password
```
* Add the following to your Home Assistant's `secrets.yaml` changing the placeholder with your actual password:
```yaml
midea_password: PLACEHOLDER
```
* Restart Home Assistant and enjoy!

## Basic usage
You don't need to use Home Assistant to use this library and a little bit of Python below will get you started:
```python
from midea.client import client as midea_client
from midea.device import operational_mode_enum
from midea.device import fan_speed_enum
from midea.device import swing_mode_enum

# The client takes an App_Key, an account email address and a password
client = midea_client('3742e9e5842d4ad59c2db887e12449f9', 'foo@bar.com', 'account_password')

# Log in right now, to check credentials (this step is optional, and will be called when listing devices)
client.setup()

# List devices. These are complex state holding objects, no other trickery needed from here. 
devices = client.devices()

for device in devices:

    # Refresh the object with the actual state by querying it
    device.refresh()
    print({
        'id': device.id,
        'name': device.name,
        'power_state': device.power_state,
        'audible_feedback': device.audible_feedback,
        'target_temperature': device.target_temperature,
        'operational_mode': device.operational_mode,
        'fan_speed': device.fan_speed,
        'swing_mode': device.swing_mode,
        'eco_mode': device.eco_mode,
        'turbo_mode': device.turbo_mode
    })

    # Set the state of the device and
    device.power_state = True
    device.audible_feedback = True
    device.target_temperature = 21
    device.operational_mode = operational_mode_enum.auto
    device.fan_speed = fan_speed_enum.Auto
    device.swing_mode = swing_mode_enum.Off
    device.eco_mode = False
    device.turbo_mode = False
    # commit the changes with apply()
    device.apply()
```

## Known Issues
Currently this Midea API doesn't support multiple sessions, and using the NetHome App with the Home Assistant plugin with cause issues. If you see an exception with 'Invalid Session'
then your session has expired due to multiple use. This is being addressed, at the moment to improve the robustness of the component.