import unittest

from msmart.cloud import ApiError, Cloud, CloudError
from msmart.const import OPEN_MIDEA_APP_ACCOUNT, OPEN_MIDEA_APP_PASSWORD


class TestCloud(unittest.IsolatedAsyncioTestCase):
    # pylint: disable=protected-access

    async def _login(self, account: str = OPEN_MIDEA_APP_ACCOUNT,
                     password: str = OPEN_MIDEA_APP_PASSWORD) -> Cloud:
        client = Cloud(account, password)
        await client.login()

        return client

    async def test_login(self) -> None:
        """Test that we can login to the cloud."""

        client = await self._login()

        self.assertIsNotNone(client._session)
        self.assertIsNotNone(client._access_token)

    async def test_login_exception(self) -> None:
        """Test that we can login to the cloud."""

        with self.assertRaises(ApiError):
            await self._login(account="bad@account.com", password="not_a_password")

    async def test_get_token(self) -> None:
        """Test that a token and key can be obtained from the cloud."""

        DUMMY_UDPID = "4fbe0d4139de99dd88a0285e14657045"

        client = await self._login()
        token, key = await client.get_token(DUMMY_UDPID)

        self.assertIsNotNone(token)
        self.assertIsNotNone(key)

    async def test_get_token_exception(self) -> None:
        """Test that an exception is thrown when a token and key 
        can't be obtained from the cloud."""

        BAD_UDPID = "NOT_A_UDPID"

        client = await self._login()

        with self.assertRaises(CloudError):
            await client.get_token(BAD_UDPID)


if __name__ == "__main__":
    unittest.main()
