from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any, List, Optional, cast

from msmart.base_device import Device
from msmart.const import DeviceType

from .command import (CapabilitiesResponse, GetCapabilitiesCommand,
                      GetStateCommand, InvalidResponseException)
from .command import Response as base_response
from .command import (ResponseId, SetStateCommand, StateResponse,
                      ToggleDisplayCommand)

_LOGGER = logging.getLogger(__name__)


class IntEnumHelper(IntEnum):
    """Helper class to convert IntEnums to/from strings."""
    @classmethod
    def list(cls) -> List[IntEnumHelper]:
        return list(map(lambda c: c, cls))

    @classmethod
    def get_from_value(cls, value: Optional[int], default: IntEnumHelper) -> IntEnumHelper:
        try:
            return cls(cast(int, value))
        except ValueError:
            _LOGGER.debug("Unknown %s: %d", cls, value)
            return default

    @classmethod
    def get_from_name(cls, name: str, default: IntEnumHelper) -> IntEnumHelper:
        try:
            return cls[name]
        except KeyError:
            _LOGGER.debug("Unknown %s: %d", cls, name)
            return default


class AirConditioner(Device):

    class FanSpeed(IntEnumHelper):
        AUTO = 102
        FULL = 100
        HIGH = 80
        MEDIUM = 60
        LOW = 40
        SILENT = 20

        @classmethod
        def get_from_value(cls, value: Optional[int], default=AUTO) -> AirConditioner.FanSpeed:
            return cast(cls, super().get_from_value(value, default))

        @classmethod
        def get_from_name(cls, name: str, default=AUTO) -> AirConditioner.FanSpeed:
            return cast(cls, super().get_from_name(name, default))

    class OperationalMode(IntEnumHelper):
        AUTO = 1
        COOL = 2
        DRY = 3
        HEAT = 4
        FAN_ONLY = 5

        @classmethod
        def get_from_value(cls, value: Optional[int], default=FAN_ONLY) -> AirConditioner.OperationalMode:
            return cast(cls, super().get_from_value(value, default))

        @classmethod
        def get_from_name(cls, name: str, default=FAN_ONLY) -> AirConditioner.OperationalMode:
            return cast(cls, super().get_from_name(name, default))

    class SwingMode(IntEnumHelper):
        OFF = 0x0
        VERTICAL = 0xC
        HORIZONTAL = 0x3
        BOTH = 0xF

        @classmethod
        def get_from_value(cls, value: Optional[int], default=OFF) -> AirConditioner.SwingMode:
            return cast(cls, super().get_from_value(value, default))

        @classmethod
        def get_from_name(cls, name: str, default=OFF) -> AirConditioner.SwingMode:
            return cast(cls, super().get_from_name(name, default))

    def __init__(self, ip: str, device_id: int,  port: int, **kwargs) -> None:
        # Remove possible duplicate device_type kwarg
        kwargs.pop("device_type", None)

        super().__init__(ip=ip, port=port, device_id=device_id,
                         device_type=DeviceType.AIR_CONDITIONER, **kwargs)

        self._updating = False
        self._keep_last_known_online_state = False
        self._defer_update = False

        self._beep_on = False
        self._power_state = False
        self._target_temperature = 17.0
        self._operational_mode = AirConditioner.OperationalMode.AUTO
        self._fan_speed = AirConditioner.FanSpeed.AUTO
        self._swing_mode = AirConditioner.SwingMode.OFF
        self._eco_mode = False
        self._turbo_mode = False
        self._freeze_protection_mode = False
        self._sleep_mode = False
        self._fahrenheit_unit = False  # Display temperature in Fahrenheit
        self._display_on = False
        self._filter_alert = False

        # Support all known modes initially
        self._supported_op_modes = cast(
            List[AirConditioner.OperationalMode], AirConditioner.OperationalMode.list())
        self._supported_swing_modes = cast(
            List[AirConditioner.SwingMode], AirConditioner.SwingMode.list())
        self._supports_eco_mode = True
        self._supports_turbo_mode = True
        self._supports_freeze_protection_mode = True
        self._supports_display_control = True
        self._min_target_temperature = 16
        self._max_target_temperature = 30

        self._on_timer = None
        self._off_timer = None
        self._indoor_temperature = None
        self._outdoor_temperature = None

    async def get_capabilities(self) -> None:
        cmd = GetCapabilitiesCommand()
        await self.send_command(cmd)

    async def toggle_display(self) -> None:
        if not self._supports_display_control:
            _LOGGER.warning("Device is not capable of display control.")

        cmd = ToggleDisplayCommand()
        await self.send_command(cmd, True)

        # Force a refresh to get the updated display state
        await self.refresh()

    async def refresh(self):
        cmd = GetStateCommand()
        await self.send_command(cmd)

    async def send_command(self, command, ignore_response=False) -> None:
        responses = await super().send_command(command)

        # Ignore responses if requested
        if ignore_response:
            return

        # No response from device
        if responses is None:
            # Set device offline unless keeping last known state
            if not self._keep_last_known_online_state:
                self._online = False

            return

        # Device is online if we received any response
        self._online = True

        for response in responses:
            self.process_response(response)

    def process_response(self, data) -> None:
        # Construct response from data
        try:
            response = base_response.construct(data)
        except InvalidResponseException as e:
            _LOGGER.error(e)
            return

        # Device is supported if we can process a response
        self._supported = True

        if response.id == ResponseId.STATE:
            response = cast(StateResponse, response)
            self.update(response)
        elif response.id == ResponseId.CAPABILITIES:
            response = cast(CapabilitiesResponse, response)
            self.update_capabilities(response)
        else:
            _LOGGER.debug("Ignored unknown response from %s:%d: %s",
                          self.ip, self.port, response.payload.hex())

    async def apply(self) -> None:
        self._updating = True
        try:
            # Warn if trying to apply unsupported modes
            if self._operational_mode not in self._supported_op_modes:
                _LOGGER.warning(
                    "Device is not capable of operational mode %s.", self._operational_mode)

            if self._swing_mode not in self._supported_swing_modes:
                _LOGGER.warning(
                    "Device is not capable of swing mode %s.", self._swing_mode)

            if self._turbo_mode and not self._supports_turbo_mode:
                _LOGGER.warning("Device is not capable of turbo mode.")

            if self._eco_mode and not self._supports_eco_mode:
                _LOGGER.warning("Device is not capable of eco mode.")

            if self._freeze_protection_mode and not self._supports_freeze_protection_mode:
                _LOGGER.warning("Device is not capable of freeze protection.")

            # Define function to return value or a default if value is None
            def or_default(v, d) -> Any: return v if v is not None else d

            cmd = SetStateCommand()
            cmd.beep_on = self._beep_on
            cmd.power_on = or_default(self._power_state, False)
            cmd.target_temperature = or_default(
                self._target_temperature, 25)  # TODO?
            cmd.operational_mode = self._operational_mode
            cmd.fan_speed = self._fan_speed
            cmd.swing_mode = self._swing_mode
            cmd.eco_mode = or_default(self._eco_mode, False)
            cmd.turbo_mode = or_default(self._turbo_mode, False)
            cmd.freeze_protection_mode = or_default(
                self._freeze_protection_mode, False)
            cmd.sleep_mode = or_default(self._sleep_mode, False)
            cmd.fahrenheit = or_default(self._fahrenheit_unit, False)

            await self.send_command(cmd, self._defer_update)
        finally:
            self._updating = False
            self._defer_update = False

    def update(self, res: StateResponse) -> None:
        self._power_state = res.power_on

        self._target_temperature = res.target_temperature
        self._operational_mode = AirConditioner.OperationalMode.get_from_value(
            res.operational_mode)

        self._fan_speed = AirConditioner.FanSpeed.get_from_value(
            res.fan_speed)

        self._swing_mode = AirConditioner.SwingMode.get_from_value(
            res.swing_mode)

        self._eco_mode = res.eco_mode
        self._turbo_mode = res.turbo_mode
        self._freeze_protection_mode = res.freeze_protection_mode
        self._sleep_mode = res.sleep_mode

        self._indoor_temperature = res.indoor_temperature
        self._outdoor_temperature = res.outdoor_temperature

        self._display_on = res.display_on
        self._fahrenheit_unit = res.fahrenheit

        self._filter_alert = res.filter_alert

        # self._on_timer = res.on_timer
        # self._off_timer = res.off_timer

    def update_capabilities(self, res: CapabilitiesResponse) -> None:
        # Build list of supported operation modes
        op_modes = [AirConditioner.OperationalMode.FAN_ONLY]
        if res.dry_mode:
            op_modes.append(AirConditioner.OperationalMode.DRY)
        if res.cool_mode:
            op_modes.append(AirConditioner.OperationalMode.COOL)
        if res.heat_mode:
            op_modes.append(AirConditioner.OperationalMode.HEAT)
        if res.auto_mode:
            op_modes.append(AirConditioner.OperationalMode.AUTO)

        self._supported_op_modes = op_modes

        # Build list of supported swing modes
        swing_modes = [AirConditioner.SwingMode.OFF]
        if res.swing_horizontal:
            swing_modes.append(AirConditioner.SwingMode.HORIZONTAL)
        if res.swing_vertical:
            swing_modes.append(AirConditioner.SwingMode.VERTICAL)
        if res.swing_both:
            swing_modes.append(AirConditioner.SwingMode.BOTH)

        self._supported_swing_modes = swing_modes

        self._supports_eco_mode = res.eco_mode
        self._supports_turbo_mode = res.turbo_mode
        self._supports_freeze_protection_mode = res.freeze_protection_mode

        self._supports_display_control = res.display_control

        self._min_target_temperature = res.min_temperature
        self._max_target_temperature = res.max_temperature

    @property
    def beep(self) -> bool:
        return self._beep_on

    @beep.setter
    def beep(self, tone: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._beep_on = tone

    @property
    def power_state(self) -> Optional[bool]:
        return self._power_state

    @power_state.setter
    def power_state(self, state: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._power_state = state

    @property
    def target_temperature(self) -> Optional[float]:
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, temperature_celsius: float) -> None:
        if self._updating:
            self._defer_update = True
        self._target_temperature = temperature_celsius

    @property
    def operational_mode(self) -> OperationalMode:
        return self._operational_mode

    @operational_mode.setter
    def operational_mode(self, mode: OperationalMode) -> None:
        if self._updating:
            self._defer_update = True
        self._operational_mode = mode

    @property
    def fan_speed(self) -> FanSpeed:
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, speed: FanSpeed) -> None:
        if self._updating:
            self._defer_update = True
        self._fan_speed = speed

    @property
    def swing_mode(self) -> SwingMode:
        return self._swing_mode

    @swing_mode.setter
    def swing_mode(self, mode: SwingMode) -> None:
        if self._updating:
            self._defer_update = True
        self._swing_mode = mode

    @property
    def supports_eco_mode(self) -> Optional[bool]:
        return self._supports_eco_mode

    @property
    def eco_mode(self) -> Optional[bool]:
        return self._eco_mode

    @eco_mode.setter
    def eco_mode(self, enabled: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._eco_mode = enabled

    @property
    def supports_turbo_mode(self) -> Optional[bool]:
        return self._supports_turbo_mode

    @property
    def turbo_mode(self) -> Optional[bool]:
        return self._turbo_mode

    @turbo_mode.setter
    def turbo_mode(self, enabled: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._turbo_mode = enabled

    @property
    def supports_freeze_protection_mode(self) -> Optional[bool]:
        return self._supports_freeze_protection_mode

    @property
    def freeze_protection_mode(self) -> Optional[bool]:
        return self._freeze_protection_mode

    @freeze_protection_mode.setter
    def freeze_protection_mode(self, enabled: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._freeze_protection_mode = enabled

    @property
    def sleep_mode(self) -> Optional[bool]:
        return self._sleep_mode

    @sleep_mode.setter
    def sleep_mode(self, enabled: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._sleep_mode = enabled

    @property
    def fahrenheit(self) -> Optional[bool]:
        return self._fahrenheit_unit

    @fahrenheit.setter
    def fahrenheit(self, enabled: bool) -> None:
        if self._updating:
            self._defer_update = True
        self._fahrenheit_unit = enabled

    @property
    def display_on(self) -> Optional[bool]:
        return self._display_on

    @property
    def filter_alert(self) -> Optional[bool]:
        return self._filter_alert

    @property
    def indoor_temperature(self) -> Optional[float]:
        return self._indoor_temperature

    @property
    def outdoor_temperature(self) -> Optional[float]:
        return self._outdoor_temperature

    @property
    def on_timer(self):
        return self._on_timer

    @property
    def off_timer(self):
        return self._off_timer

    @property
    def supported_operation_modes(self) -> List[OperationalMode]:
        return self._supported_op_modes

    @property
    def supported_swing_modes(self) -> List[SwingMode]:
        return self._supported_swing_modes

    @property
    def min_target_temperature(self) -> Optional[int]:
        return self._min_target_temperature

    @property
    def max_target_temperature(self) -> Optional[int]:
        return self._max_target_temperature
