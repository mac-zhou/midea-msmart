# -*- coding: UTF-8 -*-
import logging

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
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
