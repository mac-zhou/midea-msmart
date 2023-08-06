# -*- coding: UTF-8 -*-
import logging
from Crypto.Cipher import AES
from Crypto.Util import Padding
from Crypto.Util.strxor import strxor
from Crypto.Random import get_random_bytes
from hashlib import md5, sha256
from msmart.const import MSGTYPE_ENCRYPTED_REQUEST, MSGTYPE_ENCRYPTED_RESPONSE

_LOGGER = logging.getLogger(__name__)


class Security:
    SIGN_KEY = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S".encode()
    ENC_KEY = md5(SIGN_KEY).digest()

    def __init__(self):
        self._tcp_key = None
        self._request_count = 0
        self._response_count = 0

    def _aes_cbc_decrypt(self, raw, key):
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).decrypt(raw)

    def _aes_cbc_encrypt(self, raw, key):
        return AES.new(key, AES.MODE_CBC, iv=bytes(16)).encrypt(raw)

    def tcp_key(self, response, key):
        if response == b'ERROR':
            _LOGGER.error('authentication failed')
            return b'', False
        if len(response) != 64:
            _LOGGER.error('unexpected data length')
            return b'', False
        payload = response[:32]
        sign = response[32:]
        plain = self._aes_cbc_decrypt(payload, key)
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
            _LOGGER.info("request_count is too big to convert: %d",
                         self._request_count)
            self._request_count = 0
        data = self._request_count.to_bytes(2, 'big') + data
        self._request_count += 1
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = sha256(header + data).digest()
            data = self._aes_cbc_encrypt(data, self._tcp_key) + sign
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
            data = self._aes_cbc_decrypt(data, self._tcp_key)
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

    @classmethod
    def decrypt_aes(cls, data: bytes):
        cipher = AES.new(Security.ENC_KEY, AES.MODE_ECB)

        # Decrypt and remove padding
        return Padding.unpad(cipher.decrypt(data), 16)

    @classmethod
    def encrypt_aes(cls, data: bytes):
        cipher = AES.new(Security.ENC_KEY, AES.MODE_ECB)

        # Encrypt the padded data
        return cipher.encrypt(Padding.pad(data, 16))

    @classmethod
    def encode32(cls, data: bytes):
        return md5(data + Security.SIGN_KEY).digest()

    @classmethod
    def udpid(cls, id: bytes):
        with memoryview(sha256(id).digest()) as hash:
            return bytes(a ^ b for a, b in zip(hash[:16], hash[16:]))
