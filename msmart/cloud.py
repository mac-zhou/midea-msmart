"""Module for minimal Midea cloud API access."""
import hashlib
import hmac
import json
import logging
import os
from asyncio import Lock
from datetime import datetime
from secrets import token_hex, token_urlsafe
from typing import Any, Dict, Optional, Tuple

import httpx

_LOGGER = logging.getLogger(__name__)


class CloudError(Exception):
    """Generic exception for Midea cloud errors."""
    pass


class ApiError(CloudError):
    """Exception class for Midea cloud API errors."""

    def __init__(self, message, code=None) -> None:
        super().__init__(message, code)

        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f"Code: {self.code}, Message: {self.message}"


class Cloud:
    """Class for minimal Midea cloud API access."""

    # Misc constants for the API
    CLIENT_TYPE = 1  # Android
    FORMAT = 2  # JSON
    LANGUAGE = "en_US"
    APP_ID = "1010"
    SRC = "1010"
    DEVICE_ID = "c1acad8939ac0d7d"

    # Base URLs
    BASE_URL = "https://mp-prod.appsmb.com"
    BASE_URL_CHINA = "https://mp-prod.smartmidea.net"

    # Default number of request retries
    RETRIES = 3

    def __init__(self, account: str, password: str,
                 use_china_server: bool = False) -> None:
        # Allow override Chia server from environment
        if os.getenv("MIDEA_CHINA_SERVER", "0") == "1":
            use_china_server = True

        self._account = account
        self._password = password

        # Attributes that holds the login information of the current user
        self._login_id = None
        self._access_token = ""
        self._session = {}

        self._api_lock = Lock()
        self._security = _Security(use_china_server)

        self._base_url = Cloud.BASE_URL_CHINA if use_china_server else Cloud.BASE_URL

        _LOGGER.info("Using Midea cloud server: %s (China: %s).",
                     self._base_url, use_china_server)

    def _timestamp(self) -> str:
        """Format a timestamp for the API."""
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")

    def _parse_response(self, response) -> Any:
        """Parse a response from the API."""

        _LOGGER.debug("API response: %s", response.text)
        body = json.loads(response.text)

        response_code = int(body["code"])
        if response_code == 0:
            return body["data"]

        raise ApiError(body["msg"], code=response_code)

    async def _post_request(self, url: str, headers: Dict[str, Any],
                            contents: str, retries: int = RETRIES) -> Optional[dict]:
        """Post a request to the API."""

        async with httpx.AsyncClient() as client:
            while retries > 0:
                try:
                    # Post request and handle bad status code
                    r = await client.post(url, headers=headers, content=contents)
                    r.raise_for_status()

                    # Parse the response
                    return self._parse_response(r)
                except httpx.TimeoutException as e:
                    if retries > 1:
                        _LOGGER.warning("Request to %s timed out.", url)
                        retries -= 1
                    else:
                        raise CloudError("No response from server.") from e

    async def _api_request(self, endpoint: str, body: Dict[str, Any]) -> Optional[dict]:
        """Make a request to the Midea cloud return the results."""

        # Encode body as JSON
        contents = json.dumps(body)
        random = token_hex(16)

        # Sign the contents and add it to the header
        sign = self._security.sign(contents, random)
        headers = {
            'Content-Type': 'application/json',
            "secretVersion": "1",
            "sign": sign,
            "random": random,
            "accessToken": self._access_token
        }

        # Build complete request URL
        url = f"{self._base_url}/mas/v5/app/proxy?alias={endpoint}"

        # Lock the API and post the request
        async with self._api_lock:
            return await self._post_request(url, headers, contents)

    def _build_request_body(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a request body."""

        # Set up the initial body
        body = {
            "appId": Cloud.APP_ID,
            "format": Cloud.FORMAT,
            "clientType": Cloud.CLIENT_TYPE,
            "language": Cloud.LANGUAGE,
            "src": Cloud.SRC,
            "stamp": self._timestamp(),
            "deviceId": Cloud.DEVICE_ID,
            "reqId": token_hex(16),
        }

        # Add additional fields to the body
        body.update(data)

        return body

    async def _get_login_id(self) -> str:
        """Get a login ID for the cloud account."""

        response = await self._api_request(
            "/v1/user/login/id/get",
            self._build_request_body(
                {"loginAccount": self._account}
            )
        )

        # Assert response is not None since we should throw on errors
        assert response is not None

        return response["loginId"]

    async def login(self, force: bool = False) -> None:
        """Login to the cloud API."""

        # Don't login if session already exists
        if self._session and not force:
            return

        # Get a login ID if we don't have one
        if self._login_id is None:
            self._login_id = await self._get_login_id()
            _LOGGER.debug("Received loginId: %s", self._login_id)

        # Build the login data
        body = {
            "data": {
                "platform": Cloud.FORMAT,
                "deviceId": Cloud.DEVICE_ID,
            },
            "iotData": {
                "appId": Cloud.APP_ID,
                "clientType": Cloud.CLIENT_TYPE,
                "iampwd": self._security.encrypt_iam_password(self._login_id, self._password),
                "loginAccount": self._account,
                "password": self._security.encrypt_password(self._login_id, self._password),
                "pushToken": token_urlsafe(120),
                "reqId": token_hex(16),
                "src": Cloud.SRC,
                "stamp": self._timestamp(),
            },
        }

        # Login and store the session
        response = await self._api_request("/mj/user/login", body)

        # Assert response is not None since we should throw on errors
        assert response is not None

        self._session = response
        self._access_token = response["mdata"]["accessToken"]
        _LOGGER.debug("Received accessToken: %s", self._access_token)

    async def get_token(self, udpid: str) -> Tuple[str, str]:
        """Get token and key for the provided udpid."""

        response = await self._api_request(
            '/v1/iot/secure/getToken',
            self._build_request_body({"udpid": udpid})
        )

        # Assert response is not None since we should throw on errors
        assert response is not None

        for token in response["tokenlist"]:
            if token["udpId"] == udpid:
                return token["token"], token["key"]

        # No matching udpId in the tokenlist
        raise CloudError(f"No token/key found for udpid {udpid}.")


class _Security:
    """"Class for Midea cloud specific security."""

    HMAC_KEY = "PROD_VnoClJI9aikS8dyy"

    IOT_KEY = "meicloud"
    LOGIN_KEY = "ac21b9f9cbfe4ca5a88562ef25e2b768"

    IOT_KEY_CHINA = "prod_secret123@muc"
    LOGIN_KEY_CHINA = "ad0ee21d48a64bf49f4fb583ab76e799"

    def __init__(self, use_china_server=False):
        self._use_china_server = use_china_server

    @property
    def _iot_key(self) -> str:
        """Get the IOT key for the appropriate server."""
        return _Security.IOT_KEY_CHINA if self._use_china_server else _Security.IOT_KEY

    @property
    def _login_key(self) -> str:
        """Get the login key for the appropriate server."""
        return _Security.LOGIN_KEY_CHINA if self._use_china_server else _Security.LOGIN_KEY

    def sign(self, data: str, random: str) -> str:
        """Generate a HMAC signature for the provided data and random data."""
        msg = self._iot_key + data + random

        sign = hmac.new(self.HMAC_KEY.encode("ASCII"),
                        msg.encode("ASCII"), hashlib.sha256)
        return sign.hexdigest()

    def encrypt_password(self, login_id: str, password: str) -> str:
        """Encrypt the password for cloud API password."""
        # Hash the password
        m1 = hashlib.sha256(password.encode("ASCII"))

        # Create the login hash with the loginID + password hash + loginKey, then hash it all AGAIN
        login_hash = login_id + m1.hexdigest() + self._login_key
        m2 = hashlib.sha256(login_hash.encode("ASCII"))

        return m2.hexdigest()

    def encrypt_iam_password(self, login_id: str, password: str) -> str:
        """Encrypts password for cloud API iampwd field."""

        # Hash the password
        m1 = hashlib.md5(password.encode("ASCII"))

        # Hash the password hash
        m2 = hashlib.md5(m1.hexdigest().encode("ASCII"))

        if self._use_china_server:
            return m2.hexdigest()

        login_hash = login_id + m2.hexdigest() + self._login_key
        sha = hashlib.sha256(login_hash.encode("ASCII"))

        return sha.hexdigest()
