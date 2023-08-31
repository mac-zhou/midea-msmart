import logging
import unittest
from typing import Union, cast

from .command import (CapabilitiesResponse, CapabilityId, Response,
                      StateResponse)


class _TestResponseBase(unittest.TestCase):
    """Base class that provides some common methods for derived classes."""

    def assertHasAttr(self, obj, attr) -> None:
        """Assert that an object has an attribute."""
        self.assertTrue(hasattr(obj, attr),
                        msg=f"Object {obj} lacks attribute '{attr}'.")

    def _test_build_response(self, msg) -> Union[StateResponse, CapabilitiesResponse, Response]:
        """Build a response from the frame and assert it exists."""
        resp = Response.construct(msg)
        self.assertIsNotNone(resp)
        return resp

    def _test_check_attributes(self, obj, expected_attrs) -> None:
        """Assert that an object has all expected attributes."""
        for attr in expected_attrs:
            self.assertHasAttr(obj, attr)


class TestStateResponse(_TestResponseBase):
    """Test device state response messages."""

    # Attributes expected in state response objects
    EXPECTED_ATTRS = ["power_on", "target_temperature", "operational_mode",
                      "fan_speed", "swing_mode", "turbo_mode", "eco_mode",
                      "sleep_mode", "fahrenheit", "indoor_temperature",
                      "outdoor_temperature", "filter_alert", "display_on",
                      "freeze_protection_mode"]

    def _test_response(self, msg) -> StateResponse:
        resp = self._test_build_response(msg)
        self._test_check_attributes(resp, self.EXPECTED_ATTRS)
        return cast(StateResponse, resp)

    def test_message_checksum(self) -> None:
        # V3 state response with checksum as CRC, and shorter than expected
        TEST_MESSAGE_CHECKSUM_AS_CRC = bytes.fromhex(
            "aa1eac00000000000003c0004b1e7f7f000000000069630000000000000d33")
        resp = self._test_response(TEST_MESSAGE_CHECKSUM_AS_CRC)

        # Assert response is a state response
        self.assertEqual(type(resp), StateResponse)

        # Suppress type errors
        resp = cast(StateResponse, resp)

        self.assertEqual(resp.target_temperature, 27.0)
        self.assertEqual(resp.indoor_temperature, 27.5)
        self.assertEqual(resp.outdoor_temperature, 24.5)

    def test_message_v2(self) -> None:
        # V2 state response
        TEST_MESSAGE_V2 = bytes.fromhex(
            "aa22ac00000000000303c0014566000000300010045eff00000000000000000069fdb9")
        resp = self._test_response(TEST_MESSAGE_V2)

        # Assert response is a state response
        self.assertEqual(type(resp), StateResponse)

        # Suppress type errors
        resp = cast(StateResponse, resp)

        self.assertEqual(resp.target_temperature, 21.0)
        self.assertEqual(resp.indoor_temperature, 22.0)
        self.assertEqual(resp.outdoor_temperature, None)

    def test_message_v3(self) -> None:
        # V3 state response
        TEST_MESSAGE_V3 = bytes.fromhex(
            "aa23ac00000000000303c00145660000003c0010045c6b20000000000000000000020d79")
        resp = self._test_response(TEST_MESSAGE_V3)

        # Assert response is a state response
        self.assertEqual(type(resp), StateResponse)

        # Suppress type errors
        resp = cast(StateResponse, resp)

        self.assertEqual(resp.target_temperature, 21.0)
        self.assertEqual(resp.indoor_temperature, 21.0)
        self.assertEqual(resp.outdoor_temperature, 28.5)


class TestCapabilitiesResponse(_TestResponseBase):
    """Test device capabilities response messages."""

    # Properties expected in capabilities responses
    EXPECTED_PROPERTIES = ["swing_horizontal", "swing_vertical", "swing_both",
                           "dry_mode", "cool_mode", "heat_mode", "auto_mode",
                           "eco_mode", "turbo_mode", "display_control",
                           "min_temperature", "max_temperature", "freeze_protection_mode"]

    def test_properties(self) -> None:
        """Test that the capabilities response has the expected properties."""

        # Construct a response from a dummy payload with no caps
        with memoryview(b"\xb5\x00") as data:
            resp = CapabilitiesResponse(data)
        self.assertIsNotNone(resp)

        # Check that the object has all the expected properties
        self._test_check_attributes(resp, self.EXPECTED_PROPERTIES)

    def test_capabilities_parsers(self) -> None:
        """Test the generic capabilities parsers. e.g. bool, get_value"""

        def _build_capability_response(cap, value) -> CapabilitiesResponse:
            data = b"\xBA\x01" + \
                cap.to_bytes(2, "little") + b"\x01" + bytes([value])
            with memoryview(data) as mv_data:
                resp = CapabilitiesResponse(mv_data)
            self.assertIsNotNone(resp)
            return resp

        # Test INDOOR_HUMIDITY capability which uses a boolean parser. e.g. X > 0
        self.assertEqual(_build_capability_response(
            CapabilityId.INDOOR_HUMIDITY, 0)._capabilities["indoor_humidity"], False)
        self.assertEqual(_build_capability_response(
            CapabilityId.INDOOR_HUMIDITY, 1)._capabilities["indoor_humidity"], True)
        self.assertEqual(_build_capability_response(
            CapabilityId.INDOOR_HUMIDITY, 100)._capabilities["indoor_humidity"], True)

        # Test SILKY_COOL capability which uses a get_value parser. e.g. X == 1
        self.assertEqual(_build_capability_response(
            CapabilityId.SILKY_COOL, 0)._capabilities["silky_cool"], False)
        self.assertEqual(_build_capability_response(
            CapabilityId.SILKY_COOL, 1)._capabilities["silky_cool"], True)
        self.assertEqual(_build_capability_response(
            CapabilityId.SILKY_COOL, 100)._capabilities["silky_cool"], False)

        # Test FAN_SPEED_CONTROL capability which uses an inverse get_value parser. e.g. X != 1
        self.assertEqual(_build_capability_response(
            CapabilityId.FAN_SPEED_CONTROL, 0)._capabilities["fan_speed_control"], True)
        self.assertEqual(_build_capability_response(
            CapabilityId.FAN_SPEED_CONTROL, 1)._capabilities["fan_speed_control"], False)
        self.assertEqual(_build_capability_response(
            CapabilityId.FAN_SPEED_CONTROL, 100)._capabilities["fan_speed_control"], True)

        # Test PRESET_ECO capability which uses 2 get_value parsers.
        # e.g. eco_mode -> X == 1, eco_mode2 -> X == 2
        resp = _build_capability_response(CapabilityId.PRESET_ECO, 0)
        self.assertEqual(resp._capabilities["eco_mode"], False)
        self.assertEqual(resp._capabilities["eco_mode_2"], False)

        resp = _build_capability_response(CapabilityId.PRESET_ECO, 1)
        self.assertEqual(resp._capabilities["eco_mode"], True)
        self.assertEqual(resp._capabilities["eco_mode_2"], False)

        resp = _build_capability_response(CapabilityId.PRESET_ECO, 2)
        self.assertEqual(resp._capabilities["eco_mode"], False)
        self.assertEqual(resp._capabilities["eco_mode_2"], True)

        # Test PRESET_TURBO capability which uses 2 custom parsers.
        # e.g. turbo_heat -> X == 1 or X == 3, turbo_cool -> X < 2
        resp = _build_capability_response(CapabilityId.PRESET_TURBO, 0)
        self.assertEqual(resp._capabilities["turbo_heat"], False)
        self.assertEqual(resp._capabilities["turbo_cool"], True)

        resp = _build_capability_response(CapabilityId.PRESET_TURBO, 1)
        self.assertEqual(resp._capabilities["turbo_heat"], True)
        self.assertEqual(resp._capabilities["turbo_cool"], True)

        resp = _build_capability_response(CapabilityId.PRESET_TURBO, 3)
        self.assertEqual(resp._capabilities["turbo_heat"], True)
        self.assertEqual(resp._capabilities["turbo_cool"], False)

        resp = _build_capability_response(CapabilityId.PRESET_TURBO, 4)
        self.assertEqual(resp._capabilities["turbo_heat"], False)
        self.assertEqual(resp._capabilities["turbo_cool"], False)

    def test_capabilities(self) -> None:
        """Test that we decode capabilities responses as expected."""
        # https://github.com/mill1000/midea-ac-py/issues/13#issuecomment-1657485359

        TEST_CAPABILITIES_RESPONSE = bytes.fromhex(
            "aa29ac00000000000303b5071202010113020101140201011502010116020101170201001a020101dedb")
        resp = self._test_build_response(TEST_CAPABILITIES_RESPONSE)
        resp = cast(CapabilitiesResponse, resp)

        EXPECTED_RAW_CAPABILITIES = {
            "eco_mode": True, "eco_mode_2": False,
            "freeze_protection": True, "heat_mode": True,
            "cool_mode": True, "dry_mode": True,
            "auto_mode": True,
            "swing_horizontal": True, "swing_vertical": True,
            "power_cal": False, "power_cal_setting": False,
            "nest_check": False, "nest_need_change": False,
            "turbo_heat": True, "turbo_cool": True
        }
        # Ensure raw decoded capabilities match
        self.assertEqual(resp._capabilities, EXPECTED_RAW_CAPABILITIES)

        EXPECTED_CAPABILITIES = {
            "swing_horizontal": True, "swing_vertical": True, "swing_both": True,
            "dry_mode": True, "heat_mode": True, "cool_mode": True,
            "auto_mode": True, "eco_mode": True, "turbo_mode": True,
            "freeze_protection_mode": True, "display_control": False,
            "min_temperature": 16, "max_temperature": 30
        }
        # Check capabilities properties match
        for prop in self.EXPECTED_PROPERTIES:
            self.assertEqual(getattr(resp, prop), EXPECTED_CAPABILITIES[prop])

    def test_capabilities_2(self) -> None:
        """Test that we decode capabilities responses as expected."""
        # https://github.com/mac-zhou/midea-ac-py/pull/177#issuecomment-1259772244
        # Test case includes an unknown capability 0x40
        # Suppress any warnings from capability parsing
        level = logging.getLogger("msmart").getEffectiveLevel()
        logging.getLogger("msmart").setLevel(logging.ERROR)

        TEST_CAPABILITIES_RESPONSE = bytes.fromhex(
            "aa3dac00000000000203b50a12020101180001001402010115020101160201001a020101100201011f020100250207203c203c203c00400001000100c83a")
        resp = self._test_build_response(TEST_CAPABILITIES_RESPONSE)
        resp = cast(CapabilitiesResponse, resp)

        # Restore original level
        logging.getLogger("msmart").setLevel(level)

        EXPECTED_RAW_CAPABILITIES = {
            "eco_mode": True, "eco_mode_2": False, "silky_cool": False,
            "heat_mode": True, "cool_mode": True, "dry_mode": True,
            "auto_mode": True, "swing_horizontal": True, "swing_vertical": True,
            "power_cal": False, "power_cal_setting": False, "turbo_heat": True,
            "turbo_cool": True, "fan_speed_control": False, "humidity_auto_set": False,
            "humidity_manual_set": False, "cool_min_temperature": 16.0,
            "cool_max_temperature": 30.0, "auto_min_temperature": 16.0,
            "auto_max_temperature": 30.0, "heat_min_temperature": 16.0,
            "heat_max_temperature": 30.0, "decimals": True
        }
        # Ensure raw decoded capabilities match
        self.assertEqual(resp._capabilities, EXPECTED_RAW_CAPABILITIES)

        EXPECTED_CAPABILITIES = {
            "swing_horizontal": True, "swing_vertical": True, "swing_both": True,
            "dry_mode": True, "heat_mode": True, "cool_mode": True,
            "auto_mode": True, "eco_mode": True, "turbo_mode": True,
            "freeze_protection_mode": False, "display_control": False,
            "min_temperature": 16, "max_temperature": 30
        }
        # Check capabilities properties match
        for prop in self.EXPECTED_PROPERTIES:
            self.assertEqual(getattr(resp, prop), EXPECTED_CAPABILITIES[prop])

    def test_capabilities_3(self) -> None:
        """Test that we decode capabilities responses as expected."""
        # Toshiba Smart Window Unit (2019)
        TEST_CAPABILITIES_RESPONSE = bytes.fromhex(
            "aa29ac00000000000303b507120201021402010015020102170201021a0201021002010524020101990d")
        resp = self._test_build_response(TEST_CAPABILITIES_RESPONSE)
        resp = cast(CapabilitiesResponse, resp)

        EXPECTED_RAW_CAPABILITIES = {
            "eco_mode": False, "eco_mode_2": True, "heat_mode": False,
            "cool_mode": True, "dry_mode": True, "auto_mode": True,
            "swing_horizontal": False, "swing_vertical": False,
            "nest_check": True, "nest_need_change": False, "turbo_heat": False,
            "turbo_cool": False, "fan_speed_control": True, "light_control": True
        }
        # Ensure raw decoded capabilities match
        self.assertEqual(resp._capabilities, EXPECTED_RAW_CAPABILITIES)

        EXPECTED_CAPABILITIES = {
            "swing_horizontal": False, "swing_vertical": False, "swing_both": False,
            "dry_mode": True, "heat_mode": False, "cool_mode": True,
            "auto_mode": True, "eco_mode": True, "turbo_mode": False,
            "freeze_protection_mode": False, "display_control": True,
            "min_temperature": 16, "max_temperature": 30
        }
        # Check capabilities properties match
        for prop in self.EXPECTED_PROPERTIES:
            self.assertEqual(getattr(resp, prop), EXPECTED_CAPABILITIES[prop])

    def test_capabilities_4(self) -> None:
        """Test that we decode capabilities responses as expected."""
        # Midea U-shaped Window Unit (2022)
        TEST_CAPABILITIES_RESPONSE = bytes.fromhex(
            "aa39ac00000000000303b50912020102130201001402010015020100170201021a02010010020101250207203c203c203c00240201010102a1a0")
        resp = self._test_build_response(TEST_CAPABILITIES_RESPONSE)
        resp = cast(CapabilitiesResponse, resp)

        EXPECTED_RAW_CAPABILITIES = {
            "eco_mode": False, "eco_mode_2": True, "freeze_protection": False,
            "heat_mode": False, "cool_mode": True, "dry_mode": True, "auto_mode": True,
            "swing_horizontal": False, "swing_vertical": True, "nest_check": True,
            "nest_need_change": False, "turbo_heat": False, "turbo_cool": True,
            "fan_speed_control": False,
            "cool_min_temperature": 16.0, "cool_max_temperature": 30.0,
            "auto_min_temperature": 16.0, "auto_max_temperature": 30.0,
            "heat_min_temperature": 16.0, "heat_max_temperature": 30.0,
            "decimals": True, "light_control": True
        }
        # Ensure raw decoded capabilities match
        self.assertEqual(resp._capabilities, EXPECTED_RAW_CAPABILITIES)

        EXPECTED_CAPABILITIES = {
            "swing_horizontal": False, "swing_vertical": True, "swing_both": False,
            "dry_mode": True, "heat_mode": False, "cool_mode": True,
            "auto_mode": True, "eco_mode": True, "turbo_mode": True,
            "freeze_protection_mode": False, "display_control": True,
            "min_temperature": 16, "max_temperature": 30
        }
        # Check capabilities properties match
        for prop in self.EXPECTED_PROPERTIES:
            self.assertEqual(getattr(resp, prop), EXPECTED_CAPABILITIES[prop])


if __name__ == "__main__":
    unittest.main()
