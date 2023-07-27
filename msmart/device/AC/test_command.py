import unittest
from .command import response

# V3 state response with checksum as CRC, and shorter than expected
TEST_MESSAGE_CHECKSUM_AS_CRC = bytes.fromhex(
    "aa1eac00000000000003c0004b1e7f7f000000000069630000000000000d33")
# V2 state response
TEST_MESSAGE_V2 = bytes.fromhex(
    "aa22ac00000000000303c0014566000000300010045eff00000000000000000069fdb9")
# V3 state response
TEST_MESSAGE_V3 = bytes.fromhex(
    "aa23ac00000000000303c00145660000003c0010045c6b20000000000000000000020d79")


class TestStateResponse(unittest.TestCase):
    def assertHasAttr(self, obj, attr):
        """Assert that the supplied object has the supplied attribute."""
        self.assertTrue(hasattr(obj, attr),
                        msg=f"Object {obj} lacks attribute '{attr}'.")

    def _test_build_response(self, msg):
        resp = response.construct(msg)
        self.assertIsNotNone(resp)

        return resp

    def _test_check_attributes(self, resp):
        expected_attrs = ["power_on", "target_temperature", "operational_mode",
                          "fan_speed", "swing_mode", "turbo_mode", "eco_mode",
                          "sleep_mode", "fahrenheit", "indoor_temperature",
                          "outdoor_temperature", "filter_alert", "display_on",
                          "freeze_protection_mode"]
        for attr in expected_attrs:
            self.assertHasAttr(resp, attr)

    def _test_response(self, msg):
        resp = self._test_build_response(msg)
        self._test_check_attributes(resp)
        return resp

    def test_message_checksum(self):
        resp = self._test_response(TEST_MESSAGE_CHECKSUM_AS_CRC)

        self.assertEqual(resp.target_temperature, 27.0)
        self.assertEqual(resp.indoor_temperature, 27.5)
        self.assertEqual(resp.outdoor_temperature, 24.5)

    def test_message_v2(self):
        resp = self._test_response(TEST_MESSAGE_V2)

        self.assertEqual(resp.target_temperature, 21.0)
        self.assertEqual(resp.indoor_temperature, 22.0)
        self.assertEqual(resp.outdoor_temperature, None)

    def test_message_v3(self):
        resp = self._test_response(TEST_MESSAGE_V3)

        self.assertEqual(resp.target_temperature, 21.0)
        self.assertEqual(resp.indoor_temperature, 21.0)
        self.assertEqual(resp.outdoor_temperature, 28.5)


if __name__ == '__main__':
    unittest.main()
