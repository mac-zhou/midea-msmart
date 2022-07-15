# -*- coding: UTF-8 -*-
from datetime import datetime
import json
import logging
import requests
from time import time

from threading import Lock
from msmart.security import security
# from msmart.security import loginKey
from secrets import token_hex, token_urlsafe
import os

# The Midea cloud client is by far the more obscure part of this library, and without some serious reverse engineering
# this would not have been possible. Thanks Yitsushi for the ruby implementation. This is an adaptation to Python 3

VERSION = '0.2.5'

_LOGGER = logging.getLogger(__name__)


class cloud:
    CLIENT_TYPE = 1                 # Android
    FORMAT = 2                      # JSON
    LANGUAGE = 'en_US'
    APP_ID = "1010"
    SRC = "1010"

    def __init__(self, email, password, use_china_server=False):
        # Get this from any of the Midea based apps, you can find one on Yitsushi's github page
        # self.app_key = app_key
        self.login_account = email   # Your email address for your Midea account
        self.password = password

        # An obscure log in ID that is seperate to the email address
        self.login_id = None

        # A session dictionary that holds the login information of the current user
        self.session = {}

        # A list of home groups used by the API to seperate "zones"
        self.home_groups = []

        # A list of appliances associated with the account
        self.appliance_list = []

        self._api_lock = Lock()

        self.security = security()
        self._retries = 0
        self.accessToken = ''
        self._use_china_server = use_china_server
        if os.getenv('USE_CHINA_SERVER', '0') == '1':
            self._use_china_server = True
        self.SERVER_URL = 'https://mp-prod.appsmb.com/mas/v5/app/proxy?alias='
        if self._use_china_server:
            self.SERVER_URL = 'https://mp-prod.smartmidea.net/mas/v5/app/proxy?alias='
        _LOGGER.info("Using Midea cloud server: {} {}".format(self.SERVER_URL, self._use_china_server))

    def api_request(self, endpoint, args=None, data=None):
        """
        Sends an API request to the Midea cloud service and returns the results
        or raises ValueError if there is an error
        """
        args = args or {}
        self._api_lock.acquire()
        response = {}
        headers = {}
        try:
            # Set up the initial data payload with the global variable set
            if data is None:
                data = {
                    'appId': self.APP_ID,
                    'format': self.FORMAT,
                    'clientType': self.CLIENT_TYPE,
                    'language': self.LANGUAGE,
                    'src': self.SRC,
                    'stamp': datetime.now().strftime("%Y%m%d%H%M%S"),
                }
            # Add the method parameters for the endpoint
            data.update(args)

            # Add the login information to the payload
            if not data.get("reqId"):
                data.update({
                    'reqId': token_hex(16),
                })

            url = self.SERVER_URL + endpoint
            random = str(int(time()))

            # Add the sign to the header
            sign = self.security.new_sign(json.dumps(data), random)
            headers.update({
                'Content-Type': 'application/json',
                'secretVersion': '1',
                'sign': sign,
                'random': random,
                'accessToken': self.accessToken
            })

            # POST the endpoint with the payload
            r = requests.post(
                url=url, 
                headers=headers,
                data=json.dumps(data),
                # verify=False
            )
            _LOGGER.debug("Response: {}".format(r.text))
            response = json.loads(r.text)
        finally:
            self._api_lock.release()

        # Check for errors, raise if there are any
        if int(response['code']) != 0:
            self.handle_api_error(int(response['code']), response['msg'])
            # If you don't throw, then retry
            _LOGGER.debug("Retrying API call: '{}'".format(endpoint))
            self._retries += 1
            if(self._retries < 3):
                return self.api_request(endpoint, args)
            else:
                raise RecursionError()

        self._retries = 0
        return response['data']

    def get_login_id(self):
        """
        Get the login ID from the email address
        """
        response = self.api_request(
            "/v1/user/login/id/get", 
            {'loginAccount': self.login_account}
        )
        self.login_id = response['loginId']

    def login(self):
        """
        Performs a user login with the credentials supplied to the constructor
        """
        if self.login_id == None:
            self.get_login_id()

        if self.session:
            return  # Don't try logging in again, someone beat this thread to it

        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # Log in and store the session
        self.session = self.api_request(
            "/mj/user/login", 
            data={
                "data": {
                    # "appKey": loginKey,
                    "platform": self.FORMAT,
                },
                "iotData": {
                    "appId": self.APP_ID,
                    "clientType": self.CLIENT_TYPE,
                    "iampwd": self.security.encrypt_iam_password(self.login_id, self.password),
                    "loginAccount": self.login_account,
                    "password": self.security.encryptPassword(self.login_id, self.password),
                    "pushToken": token_urlsafe(120),
                    "reqId": token_hex(16),
                    "src": self.SRC,
                    "stamp": stamp,
                },
            }
        )

        self.accessToken = self.session['mdata']['accessToken']

    def list(self, home_group_id=-1):
        """
        Lists all appliances associated with the account
        """

        # If a homeGroupId is not specified, use the default one
        if home_group_id == -1:
            li = self.list_homegroups()
            home_group_id = next(
                x for x in li if x['isDefault'] == '1')['id']

        response = self.api_request('appliance/list/get', {
            'homegroupId': home_group_id
        })

        self.appliance_list = response['list']
        _LOGGER.debug("Device list: {}".format(self.appliance_list))
        return self.appliance_list

    def gettoken(self, udpid):
        """
        Get tokenlist with udpid
        """

        response = self.api_request(
            '/v1/iot/secure/getToken', 
            {'udpid': udpid}
        )
        for token in response['tokenlist']:
            if token['udpId'] == udpid:
                return token['token'], token['key']
        return None, None

    def encode(self, data: bytearray):
        normalized = []
        for b in data:
            if b >= 128:
                b = b - 256
            normalized.append(str(b))

        string = ','.join(normalized)
        return bytearray(string.encode('ascii'))

    def decode(self, data: bytearray):
        data = [int(a) for a in data.decode('ascii').split(',')]
        for i in range(len(data)):
            if data[i] < 0:
                data[i] = data[i] + 256
        return bytearray(data)

    def appliance_transparent_send(self, id, data):
        if not self.session:
            self.login()

        _LOGGER.debug("Sending to {}: {}".format(id, data.hex()))
        encoded = self.encode(data)
        order = self.security.aes_encrypt(encoded)
        response = self.api_request('appliance/transparent/send', {
            'order': order.hex(),
            'funId': '0000',
            'applianceId': id
        })

        reply = self.decode(self.security.aes_decrypt(
            bytearray.fromhex(response['reply'])))

        _LOGGER.debug("Recieved from {}: {}".format(id, reply.hex()))
        return reply

    def list_homegroups(self, force_update=False):
        """
        Lists all home groups
        """

        # Get all home groups (I think the API supports multiple zones or something)
        if not self.home_groups or force_update:
            response = self.api_request('homegroup/list/get', {})
            self.home_groups = response['list']

        return self.home_groups

    def handle_api_error(self, error_code, message: str):

        def restart_full():
            _LOGGER.debug("Restarting full: '{}' - '{}'".format(error_code, message))
            self.session = None
            self.get_login_id()
            self.login()

        def session_restart():
            _LOGGER.debug("Restarting session: '{}' - '{}'".format(error_code, message))
            self.session = None
            self.login()

        def throw():
            raise ValueError(error_code, message)

        def ignore():
            _LOGGER.debug("Error ignored: '{}' - '{}'".format(error_code, message))

        error_handlers = {
            3176: ignore,          # The asyn reply does not exist.
            3106: session_restart,  # invalidSession.
            3144: restart_full,
            3004: ignore,  # value is illegal.
            9999: ignore,  # system error.
        }

        handler = error_handlers.get(error_code, throw)
        handler()
