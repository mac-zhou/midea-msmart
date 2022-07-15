# -*- coding: UTF-8 -*-
import logging
import urllib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Util.strxor import strxor
from Crypto.Random import get_random_bytes
from hashlib import md5, sha256
from msmart.const import MSGTYPE_ENCRYPTED_REQUEST, MSGTYPE_ENCRYPTED_RESPONSE
from urllib.parse import urlparse
import hmac
import collections
from typing import Any, Dict, List, Optional, Tuple
import os

VERSION = '0.2.5'
_LOGGER = logging.getLogger(__name__)
appKey = '434a209a5ce141c3b726de067835d7f0'
signKey = 'xhdiwjnchekd4d512chdjx5d8e4c394D2D7S'

class security:

    def __init__(self, use_china_server=False):
        self.appKey = appKey.encode()
        self.signKey = signKey.encode()
        self.blockSize = 16
        self.iv = b'\0' * 16
        self.encKey = self.enc_key()
        self.dynamicKey = self.dynamic_key()
        self._tcp_key = None
        self._request_count = 0
        self._response_count = 0
        self._hmackey = "PROD_VnoClJI9aikS8dyy"

        self._iotkey = "meicloud"
        self._loginKey = 'ac21b9f9cbfe4ca5a88562ef25e2b768'

        self._use_china_server = use_china_server
        if os.getenv('USE_CHINA_SERVER', '0') == '1':
            self._use_china_server = True
        if self._use_china_server:
            self._iotkey = "prod_secret123@muc"
            self._loginKey = 'ad0ee21d48a64bf49f4fb583ab76e799'

    def aes_decrypt(self, raw):
        cipher = AES.new(self.encKey, AES.MODE_ECB)
        try:
            decrypted = cipher.decrypt(bytes(raw))

            # Remove the padding
            decrypted = unpad(decrypted, self.blockSize)
            return decrypted
        except ValueError as e:
            _LOGGER.error(
                "aes_decrypt error: {} - data: {}".format(repr(e), raw.hex()))
            return bytearray(0)

    def aes_encrypt(self, raw):
        # Make sure to pad the data
        raw = pad(raw, self.blockSize)

        cipher = AES.new(self.encKey, AES.MODE_ECB)
        encrypted = cipher.encrypt(bytes(raw))

        return encrypted

    def aes_cbc_decrypt(self, raw, key):
        return AES.new(key, AES.MODE_CBC, iv=self.iv).decrypt(raw)

    def aes_cbc_encrypt(self, raw, key):
        return AES.new(key, AES.MODE_CBC, iv=self.iv).encrypt(raw)

    def enc_key(self):
        return md5(self.signKey).digest()

    def dynamic_key(self):
        # Use only half of the hash
        return md5(self.appKey).digest()[:8]

    def encode32_data(self, raw):
        return md5(raw + self.signKey).digest()

    def local_key(self, mac: str, ssid: str, pw: str):
        mac = bytes.fromhex(mac.replace(':', ''))
        if len(mac) != 6:
            raise Exception('bad MAC address')
        ssid = ssid.encode()
        pw = pw.encode()
        return sha256(ssid + pw + mac).digest()

    def token_key_pair(self, mac: str, ssid: str, pw: str):
        local_key = self.local_key(mac, ssid, pw)
        rand = get_random_bytes(32)
        key = strxor(rand, local_key)
        token = self.aes_cbc_encrypt(key, local_key)
        sign = sha256(key).digest()
        return (token + sign, key)

    def tcp_key(self, response, key):
        if response == b'ERROR':
            _LOGGER.error('authentication failed')
            return b'', False
        if len(response) != 64:
            _LOGGER.error('unexpected data length')
            return b'', False
        payload = response[:32]
        sign = response[32:]
        plain = self.aes_cbc_decrypt(payload, key)
        if sha256(plain).digest() != sign:
            _LOGGER.error("sign does not match")
            return b'', False
        self._tcp_key = strxor(plain, key)
        self._request_count = 0
        self._response_count = 0
        return self._tcp_key, True

    def encode_8370(self, data, msgtype):
        header = bytes([0x83, 0x70])
        size, padding = len(data), 0
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            if (size + 2) % 16 != 0:
                padding = 16 - (size + 2 & 0xf)
                size += padding + 32
                data += get_random_bytes(padding)
        header += size.to_bytes(2, 'big')
        header += bytes([0x20, padding << 4 | msgtype])
        if self._request_count >= 0xfff:
            _LOGGER.info("request_count is too big to convert: {}".format(self._request_count))
            self._request_count = 0 
        data = self._request_count.to_bytes(2, 'big') + data
        self._request_count += 1
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = sha256(header + data).digest()
            data = self.aes_cbc_encrypt(data, self._tcp_key) + sign
        return header + data

    def decode_8370(self, data):
        if len(data) < 6:
            return [], data
        header = data[:6]
        if header[0] != 0x83 or header[1] != 0x70:
            raise Exception('not an 8370 message')
        size = int.from_bytes(header[2:4], 'big') + 8
        leftover = None
        if len(data) < size:
            return [], data
        elif len(data) > size:
            leftover = data[size:]
            data = data[:size]
        if header[4] != 0x20:
            raise Exception('missing byte 4')
        padding = header[5] >> 4
        msgtype = header[5] & 0xf
        data = data[6:]
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = data[-32:]
            data = data[:-32]
            data = self.aes_cbc_decrypt(data, self._tcp_key)
            if sha256(header + data).digest() != sign:
                raise Exception('sign does not match')
            if padding:
                data = data[:-padding]
        self._response_count = int.from_bytes(data[:2], 'big')
        data = data[2:]
        if leftover:
            packets, incomplete = self.decode_8370(leftover)
            return [data] + packets, incomplete
        return [data], b''

    def sign(self, url, payload):
        # We only need the path
        path = urlparse(url).path

        # This next part cares about the field ordering in the payload signature
        query = sorted(payload.items(), key=lambda x: x[0])
        
        # Create a query string (?!?) and make sure to unescape the URL encoded characters (!!!)
        query = urllib.parse.unquote_plus(urllib.parse.urlencode(query))
        
        # Combine all the sign stuff to make one giant string, then SHA256 it
        sign = path + query + self._loginKey
        m = sha256()
        m.update(sign.encode('ASCII'))
        
        return m.hexdigest()

    def new_sign(self, data: str, random: str) -> str:
        msg = self._iotkey
        if data:
            msg += data
        msg += random
        sign = hmac.new(self._hmackey.encode("ascii"), msg.encode("ascii"), sha256)
        return sign.hexdigest()

    def encryptPassword(self, loginId, password):         
        # Hash the password
        m = sha256()
        m.update(password.encode('ascii'))
        
        # Create the login hash with the loginID + password hash + appKey, then hash it all AGAIN       
        loginHash = loginId + m.hexdigest() + self._loginKey
        m = sha256()
        m.update(loginHash.encode('ascii'))
        return m.hexdigest()

    def encrypt_iam_password(self, loginId, password) -> str:
        """Encrypts password for cloud API"""
        # Hash the password
        md = md5()
        md.update(password.encode("ascii"))
        md_second = md5()
        md_second.update(md.hexdigest().encode("ascii"))
        if self._use_china_server:
            return md_second.hexdigest()
        login_hash = loginId + md_second.hexdigest() + self._loginKey
        sha = sha256()
        sha.update(login_hash.encode("ascii"))

        return sha.hexdigest()

def get_udpid(data):
    b = sha256(data).digest()
    b1, b2 = b[:16], b[16:]
    b3 = bytearray(16)
    i = 0
    while i < len(b1):
        b3[i] = b1[i] ^ b2[i]
        i += 1
    return b3.hex()
