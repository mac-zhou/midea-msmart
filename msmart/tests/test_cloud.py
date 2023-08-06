import unittest
from msmart.cloud import Cloud
from msmart.const import OPEN_MIDEA_APP_ACCOUNT, OPEN_MIDEA_APP_PASSWORD


class TestCloud(unittest.IsolatedAsyncioTestCase):

    async def _login(self) -> Cloud:
        client = Cloud(account=OPEN_MIDEA_APP_ACCOUNT,
                       password=OPEN_MIDEA_APP_PASSWORD)
        await client.login()

        return client

    async def test_login(self):
        """Test that we can login to the cloud."""

        client = await self._login()

        self.assertIsNotNone(client._session)
        self.assertIsNotNone(client._access_token)

    async def test_get_token(self):
        """Test that a token and key can be obtained from the cloud."""

        DUMMY_UDPID = "4fbe0d4139de99dd88a0285e14657045"

        client = await self._login()
        token, key = await client.get_token(DUMMY_UDPID)

        self.assertIsNotNone(token)
        self.assertIsNotNone(key)


if __name__ == '__main__':
    unittest.main()
