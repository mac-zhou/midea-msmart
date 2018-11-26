
import hashlib
import urllib
from urllib.parse import urlparse
from urllib.request import unquote
from Crypto.Cipher import AES

INITIALIZATION_VECTOR = b'\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'

class security:

    def __init__(self, appKey):
        self.appKey = appKey
        self.accessToken = None
        self.blockSize = 16        

    def sign(self, url, payload):
        # We only need the path
        path = urlparse(url).path

        # This next part cares about the field ordering in the payload signature
        query = sorted(payload.items(), key=lambda x: x[0])
        
        # Create a query string (?!?) and make sure to unescape the URL encoded characters (!!!)
        query = urllib.parse.unquote_plus(urllib.parse.urlencode(query))
        
        # Combine all the sign stuff to make one giant string, then SHA256 it and add it to the payload
        sign = path + query + self.appKey 
        m = hashlib.sha256()
        m.update(sign.encode('ASCII'))
        
        return m.hexdigest()

    def encryptPassword(self, loginId, password):         
        # Hash the password
        m = hashlib.sha256()
        m.update(password.encode('ASCII'))
        
        # Create the login hash with the loginID + password hash + appKey, then hash it all AGAIN       
        loginHash = loginId + m.hexdigest() + self.appKey
        m = hashlib.sha256()
        m.update(loginHash.encode('ASCII'))
        return m.hexdigest()

    def aes_decrypt(self, raw, key = None):
        if not key:
            key = self.data_key()

        final = bytearray([])
        blocks = [raw[i:i+self.blockSize] for i in range(0, len(raw), self.blockSize)]  

        for block in blocks:
            cipher = AES.new(key, AES.MODE_CBC, iv=INITIALIZATION_VECTOR)    
            decrypted = cipher.decrypt(block) 
            final.extend(decrypted)  
        
        final = self._unpad(final)
        raw = bytes(final)
        return raw

    def aes_encrypt(self, raw, key = None):
        if not key:
            key = self.data_key() 

        self._pad(raw)

        blocks = [raw[i:i+self.blockSize] for i in range(0, len(raw), self.blockSize)]
        final = bytearray([])
        print(blocks)

        for block in blocks:    
            cipher = AES.new(key, AES.MODE_CBC, iv=INITIALIZATION_VECTOR)        
            encrypted = cipher.encrypt(block)
            final.extend(encrypted)
            
        return final

    def _pad(self, s):
        pad = self.blockSize - (len(s) % self.blockSize)
        s.extend([pad] * pad)
       
    def _unpad(self, s):
        return s[:-s[-1]]

    def data_key(self):
        m = hashlib.md5()
        m.update(self.appKey.encode('ascii'))
        key_hash = m.hexdigest().encode('ascii')[0:16]
        key = self.aes_decrypt(bytearray.fromhex(self.accessToken), key_hash)
        return key     


