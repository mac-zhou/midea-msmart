import unittest

from .command import response, capabilities_response


class _TestResponseBase(unittest.TestCase):
    """Base class that provides some common methods for derived classes."""

    def assertHasAttr(self, obj, attr):
        """Assert that an object has an attribute."""
        self.assertTrue(hasattr(obj, attr),
                        msg=f"Object {obj} lacks attribute '{attr}'.")

    def _test_build_response(self, msg):
        """Build a response from the frame and assert it exists."""
        resp = response.construct(msg)
        self.assertIsNotNone(resp)
        return resp

    def _test_check_attributes(self, obj, expected_attrs):
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

    def _test_response(self, msg):
        resp = self._test_build_response(msg)
        self._test_check_attributes(resp, self.EXPECTED_ATTRS)
        return resp

    def test_message_checksum(self):
        # V3 state response with checksum as CRC, and shorter than expected
        TEST_MESSAGE_CHECKSUM_AS_CRC = bytes.fromhex(
            "aa1eac00000000000003c0004b1e7f7f000000000069630000000000000d33")
        resp = self._test_response(TEST_MESSAGE_CHECKSUM_AS_CRC)

        self.assertEqual(resp.target_temperature, 27.0)
        self.assertEqual(resp.indoor_temperature, 27.5)
        self.assertEqual(resp.outdoor_temperature, 24.5)

    def test_message_v2(self):
        # V2 state response
        TEST_MESSAGE_V2 = bytes.fromhex(
            "aa22ac00000000000303c0014566000000300010045eff00000000000000000069fdb9")
        resp = self._test_response(TEST_MESSAGE_V2)

        self.assertEqual(resp.target_temperature, 21.0)
        self.assertEqual(resp.indoor_temperature, 22.0)
        self.assertEqual(resp.outdoor_temperature, None)

    def test_message_v3(self):
        # V3 state response
        TEST_MESSAGE_V3 = bytes.fromhex(
            "aa23ac00000000000303c00145660000003c0010045c6b20000000000000000000020d79")
        resp = self._test_response(TEST_MESSAGE_V3)

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

    def test_properties(self):
        """Test that the capabilities response has the expected properties."""

        # Construt a response from a dummy payload with no caps
        resp = capabilities_response(b"\xb5\x00")
        self.assertIsNotNone(resp)

        # Check that the object has all the expected properties
        self._test_check_attributes(resp, self.EXPECTED_PROPERTIES)

    def test_capabilities(self):
        """Test that we decode capabilities responses as expected."""
        
        TEST_CAPABILITIES_RESPONSE = bytes.fromhex(
            "aa29ac00000000000303b5071202010113020101140201011502010116020101170201001a020101dedb")
        resp = self._test_build_response(TEST_CAPABILITIES_RESPONSE)

        EXPECTED_RAW_CAPABILITIES = {"eco_mode": True, "eco_mode_2": False,
                                     "freeze_protection": True, "heat_mode": True,
                                     "cool_mode": True, "dry_mode": True,
                                     "auto_mode": True,
                                     "swing_horizontal": True, "swing_vertical": True,
                                     "power_cal": False, "power_cal_setting": False,
                                     "nest_check": False, "nest_need_change": False,
                                     "turbo_heat": True, "turbo_cool": True}
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


if __name__ == "__main__":
    unittest.main()
