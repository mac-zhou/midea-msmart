# -*- coding: UTF-8 -*-
import logging

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from Cryptodome.Util.strxor import strxor
from Cryptodome.Random import get_random_bytes
from hashlib import md5, sha256

VERSION = '0.1.20'
_LOGGER = logging.getLogger(__name__)
appKey = '434a209a5ce141c3b726de067835d7f0'
signKey = 'xhdiwjnchekd4d512chdjx5d8e4c394D2D7S'


class security:

    def __init__(self):
        self.appKey = appKey.encode()
        self.signKey = signKey.encode()
        self.blockSize = 16
        self.iv = b'\0' * 16
        self.encKey = self.enc_key()
        self.dynamicKey = self.dynamic_key()

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
        try:
            return AES.new(key, AES.MODE_CBC, iv=self.iv).decrypt(raw)
        except ValueError as e:
            _LOGGER.error(
                "aes_cbc_decrypt error: {} - data: {}".format(repr(e), raw.hex()))
            return bytearray(0)

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
        if len(response) != 64:
            raise Exception('unexpected data length')
        payload = response[:32]
        sign = response[32:]
        plain = self.aes_cbc_decrypt(payload, key)
        if sha256(plain).digest() != sign:
            raise Exception("sign does not match")
        return strxor(plain, key)
