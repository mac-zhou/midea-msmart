import unittest

from msmart.const import DeviceType
from msmart.device import AirConditioner as AC
from msmart.discover import Discover


class TestDiscover(unittest.IsolatedAsyncioTestCase):
    # pylint: disable=protected-access

    async def test_discover_v2(self) -> None:
        """Test that we can parse a V2 discovery response."""
        DISCOVER_RESPONSE_V2 = bytes.fromhex(
            "5a5a011178007a8000000000000000000000000060ca0000000e0000000000000000000001000000c08651cb1b88a167bdcf7d37534ef81312d39429bf9b2673f200b635fae369a560fa9655eab8344be22b1e3b024ef5dfd392dc3db64dbffb6a66fb9cd5ec87a78000cd9043833b9f76991e8af29f3496")
        IP_ADDRESS = "10.100.1.140"

        # Check version
        version = Discover._get_device_version(DISCOVER_RESPONSE_V2)
        self.assertEqual(version, 2)

        # Check info matches
        info = await Discover._get_device_info(IP_ADDRESS, version, DISCOVER_RESPONSE_V2)
        self.assertIsNotNone(info)

        # Stop type errors
        assert info is not None

        self.assertEqual(info["ip"], IP_ADDRESS)
        self.assertEqual(info["port"], 6444)

        self.assertEqual(info["device_id"], 15393162840672)
        self.assertEqual(info["device_type"], DeviceType.AIR_CONDITIONER)

        self.assertEqual(info["name"], "net_ac_F7B4")
        self.assertEqual(info["sn"], "000000P0000000Q1F0C9D153F7B40000")

        # Check class is correct
        device_class = Discover._get_device_class(info["device_type"])
        self.assertEqual(device_class, AC)

        # Check that device can be built
        device = device_class(**info)
        self.assertIsNotNone(device)

    async def test_discover_v3(self) -> None:
        """Test that we can parse a V3 discovery response."""
        DISCOVER_RESPONSE_V3 = bytes.fromhex(
            "837000c8200f00005a5a0111b8007a800000000061433702060817143daa00000086000000000000000001800000000041c7129527bc03ee009284a90c2fbd2f179764ac35b55e7fb0e4ab0de9298fa1a5ca328046c603fb1ab60079d550d03546b605180127fdb5bb33a105f5206b5f008bffba2bae272aa0c96d56b45c4afa33f826a0a4215d1dd87956a267d2dbd34bdfb3e16e33d88768cc4c3d0658937d0bb19369bf0317b24d3a4de9e6a13106f7ceb5acc6651ce53d684a32ce34dc3a4fbe0d4139de99cc88a0285e14657045")
        IP_ADDRESS = "10.100.1.239"

        # Check version
        version = Discover._get_device_version(DISCOVER_RESPONSE_V3)
        self.assertEqual(version, 3)

        # Check info matches
        info = await Discover._get_device_info(IP_ADDRESS, version, DISCOVER_RESPONSE_V3)
        self.assertIsNotNone(info)

        # Stop type errors
        assert info is not None

        self.assertEqual(info["ip"], IP_ADDRESS)
        self.assertEqual(info["port"], 6444)

        self.assertEqual(info["device_id"], 147334558165565)
        self.assertEqual(info["device_type"], DeviceType.AIR_CONDITIONER)

        self.assertEqual(info["name"], "net_ac_63BA")
        self.assertEqual(info["sn"], "000000P0000000Q1B88C29C963BA0000")

        # Check class is correct
        device_class = Discover._get_device_class(info["device_type"])
        self.assertEqual(device_class, AC)

        # Check that device can be built
        device = device_class(**info)
        self.assertIsNotNone(device)


if __name__ == "__main__":
    unittest.main()
