import unittest

from msmart.lan import _LanProtocolV3, _Packet


class TestEncodeDecode(unittest.IsolatedAsyncioTestCase):
    # pylint: disable=protected-access

    async def test_encode_packet_roundtrip(self) -> None:
        """Test that we can encode and decode a frame."""
        FRAME = bytes.fromhex(
            "aa21ac8d000000000003418100ff03ff000200000000000000000000000003016971")

        packet = _Packet.encode(123456, FRAME)
        self.assertIsNotNone(packet)

        rx_frame = _Packet.decode(packet)
        self.assertEqual(rx_frame, FRAME)

    async def test_decode_packet(self) -> None:
        """Test that we can decode a packet to a frame."""
        PACKET = bytes.fromhex(
            "5a5a01116800208000000000000000000000000060ca0000000e0000000000000000000001000000c6a90377a364cb55af337259514c6f96bf084e8c7a899b50b68920cdea36cecf11c882a88861d1f46cd87912f201218c66151f0c9fbe5941c5384e707c36ff76")
        EXPECTED_FRAME = bytes.fromhex(
            "aa22ac00000000000303c0014566000000300010045cff2070000000000000008bed19")

        frame = _Packet.decode(PACKET)
        self.assertIsNotNone(frame)
        self.assertEqual(frame, EXPECTED_FRAME)

    async def test_decode_v3_packet(self) -> None:
        """Test that we can decode a V3 packet to payload to a frame."""
        PACKET = bytes.fromhex("8370008e2063ec2b8aeb17d4e3aff77094dde7fa65cf22671adf807f490a97b927347943626e9b4f58362cf34b97a0d641f8bf0c8fcbf69ad8cca131d2d7baa70ef048c5e3f3dc78da8af4598ff47aee762a0345c18815d91b50a24dedcacde0663c4ec5e73a963dc8bbbea9a593859996eb79dcfcc6a29b96262fcaa8ea6346366efea214e4a2e48caf83489475246b6fef90192b00")
        LOCAL_KEY = bytes.fromhex(
            "55a0a178746a424bf1fc6bb74b9fb9e4515965048d24ce8dc72aca91597d05ab")

        EXPECTED_PAYLOAD = bytes.fromhex(
            "5a5a01116800208000000000eaa908020c0817143daa0000008600000000000000000180000000003e99f93bb0cf9ffa100cb24dbae7838641d6e63ccbcd366130cd74a372932526d98479ff1725dce7df687d32e1776bf68a3fa6fd6259d7eb25f32769fcffef78")
        EXPECTED_FRAME = bytes.fromhex(
            "aa23ac00000000000303c00145660000003c0010045c6800000000000000000000018426")

        # Setup the protocol
        protocol = _LanProtocolV3()
        protocol._local_key = LOCAL_KEY

        with memoryview(PACKET) as mv_packet:
            payload = protocol._process_packet(mv_packet)
        self.assertIsNotNone(payload)
        self.assertEqual(payload, EXPECTED_PAYLOAD)

        frame = _Packet.decode(payload)
        self.assertIsNotNone(frame)
        self.assertEqual(frame, EXPECTED_FRAME)

    async def test_encode_packet_v3_roundtrip(self) -> None:
        """Test that we can encode a frame to V3 packet and back to the same frame."""
        FRAME = bytes.fromhex(
            "aa23ac00000000000303c00145660000003c0010045c6800000000000000000000018426")
        LOCAL_KEY = bytes.fromhex(
            "55a0a178746a424bf1fc6bb74b9fb9e4515965048d24ce8dc72aca91597d05ab")

        # Setup the protocol
        protocol = _LanProtocolV3()
        protocol._local_key = LOCAL_KEY

        # Encode frame into V2 payload
        payload = _Packet.encode(123456, FRAME)
        self.assertIsNotNone(payload)

        # Encode V2 payload into V3 packet
        with memoryview(payload) as mv_payload:
            packet = protocol._encode_encrypted_request(5555, mv_payload)

        self.assertIsNotNone(packet)

        # Decode packet into V2 payload
        with memoryview(packet) as mv_packet:
            # Can't call _process_packet since our test packet doesn't have the right type byte
            rx_payload = protocol._decode_encrypted_response(mv_packet)

        self.assertIsNotNone(rx_payload)

        # Decode V2 payload to frame
        rx_frame = _Packet.decode(rx_payload)
        self.assertIsNotNone(rx_frame)
        self.assertEqual(rx_frame, FRAME)


if __name__ == "__main__":
    unittest.main()
