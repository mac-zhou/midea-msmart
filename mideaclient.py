# This library is part of an effort to get Midea air conditioning devices to work with Home Assistant
# This library is based off the work by Yitsushi. The original work was a ruby based commandline utility.
# The orignal Ruby version can be found here https://github.com/yitsushi/midea-air-condition
# License MIT - Use as you please and at your own risk

import copy
import requests 
import hashlib
import datetime
import urllib
import json
import binascii
from midea.security import security
from midea.command import request_status_command
from midea.packet_builder import packet_builder


# The Midea client is by far the more obscure part of this library, and without some serious reverse engineering
# this would not have been possible. Thanks Yitsushi for the ruby implementation. This is an adaptation to python 3

class MideaClient:
    SERVER_URL  = "https://mapp.appsmb.com/v1/"
    CLIENT_TYPE = 1                 # Android
    FORMAT      = 2                 # JSON
    LANGUAGE    = 'en_US'
    APP_ID      = 1017
    SRC         = 17

    def __init__(self, appKey, email, password):
        self.appKey = appKey        # Get this from any of the Midea based apps, you can find one on Yitsushi's github page
        self.loginAccount = email   # Your email address for your Midea account
        self.password = password
        self.loginId = None         # An obscure log in ID that is seperate to the email address
        self.session = {}           # A session dictionary that holds the login information of the current user
        self.homeGroups = []        # A list of home groups used by the API to seperate "zones"
        self.applianceList = []     # A list of appliances associated with the account        
        
        self.security = security(self.appKey)
        # Lets not store the password in plain text any longer than we should

    def api_request(self, endpoint, args):
        """Sends an API request to the Midea cloud service and returns the results
        or raises ValueError if there is an error
        """
        # Set up the initial data payload with the global variable set
        data = {
            'appId': self.APP_ID,
            'format': self.FORMAT,
            'clientType': self.CLIENT_TYPE,
            'language': self.LANGUAGE,
            'src': self.SRC,
            'stamp': datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        }
        # Add the method parameters for the endpoint
        data.update(args)

        # Add the sessionId if there is a valid session
        if self.session:
            data['sessionId'] = self.session['sessionId']

        url = self.SERVER_URL + endpoint

        data['sign'] = self.security.sign(url, data)

        # POST the endpoint with the payload
        r = requests.post(url = url, data = data) 
        response = json.loads(r.text)
        # Check for errors, raise if there are any
        if response['errorCode'] != '0':
            raise ValueError(response['errorCode'], response['msg'])
        
        return response['result']

    def login(self):
        """Performs a user login with the credentials supplied to the constructor
        """
        # Get the login ID from the email address
        response = self.api_request("user/login/id/get", {'loginAccount': loginAccount})
        self.loginId = response['loginId']

        # Log in and store the session
        self.session = self.api_request("user/login", {
            'loginAccount': loginAccount, 
            'password': self.security.encryptPassword(self.loginId, self.password)
        })

        self.security.accessToken = self.session['accessToken']

        # Get all home groups (I think the API supports multiple zones or something)
        response = self.api_request('homegroup/list/get', {})
        self.homeGroups = response['list']

    def list(self, homeGroupId = -1):
        """Lists all appliances associated with the account
        """        
        # If a homeGroupId is not specified, use the default one
        if homeGroupId == -1:            
            homeGroupId = next(x for x in self.homeGroups if x['isDefault'] == '1')['id']

        response = self.api_request('appliance/list/get', {
            'homegroupId': homeGroupId
        })

        self.applianceList = response['list']
        return self.applianceList
        
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
        encoded = client.encode(data)
        order = security.aes_encrypt(encoded)
        response = client.api_request('appliance/transparent/send', {
            'order': order.hex(), 
            'funId':'0000', 
            'applianceId':id
        })
        reply = self.decode(security.aes_decrypt(bytearray.fromhex(response['reply'])))
        return reply



# TEST BLOCK
appKey = "<GET FROM APK>"
loginAccount = "<YOUR EMAIL ADDRESS>"
password = "<YOUR APP PASSWORD>"

# Start up a client and log in
client = MideaClient(appKey, loginAccount, password)
client.login()
deviceList = client.list()
print(deviceList)
security = client.security

# Test the weird CSV encoding
# I used this to check if the encrytion was working, I got this hex string from the Ruby version before it encrypted it and sent it to the device
request = bytearray.fromhex('5a5a01115700200000000000000000000e031214c679000000050a00000000000000000002000000aa1eac00000000000302408100ff03ff00020000000000000000000003323800000000000000000000000000000000')
encoded = client.encode(request)
print(encoded)
requestStr = security.aes_encrypt(encoded)
print(requestStr.hex())
reply = client.api_request('appliance/transparent/send', {'order': requestStr.hex(), 'funId':'0000', 'applianceId':deviceList[0]['id'] })
data = security.aes_decrypt(bytearray.fromhex(reply['reply']))
print(data)
print(client.decode(data))

# Test if the class flavours of that command is working. The packet builder and the command adds quite a bit of complexity, but does abstract this sufficiently from the caller.
command = request_status_command()
builder = packet_builder()
builder.set_command(command)
data = client.appliance_transparent_send(deviceList[0]['id'] , builder.finalize())
print(data)
