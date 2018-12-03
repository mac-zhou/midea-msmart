
import hashlib
import urllib
from urllib.parse import urlparse
from urllib.request import unquote
from Crypto.Cipher import AES

# Much secure, very null... IV of 0's... Why even have encryption at this point?
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
        
        # Combine all the sign stuff to make one giant string, then SHA256 it
        sign = path + query + self.appKey 
        m = hashlib.sha256()
        m.update(sign.encode('ASCII'))
        
        return m.hexdigest()

    def encryptPassword(self, loginId, password):         
        # Hash the password
        m = hashlib.sha256()
        m.update(password.encode('ascii'))
        
        # Create the login hash with the loginID + password hash + appKey, then hash it all AGAIN       
        loginHash = loginId + m.hexdigest() + self.appKey
        m = hashlib.sha256()
        m.update(loginHash.encode('ascii'))
        return m.hexdigest()

    def aes_decrypt(self, raw, key = None):
        # If the key is not set, then use the data_key from the access_token that comes from the current session
        if not key:
            key = self.data_key()

        final = bytearray([])
        # Break up the data into blockSize sized blocks
        blocks = [raw[i:i+self.blockSize] for i in range(0, len(raw), self.blockSize)]  

        # Decrypt each block with a new Cipher. There doesn't seem to be a reset in Python for the Cipher object
        for block in blocks:            
            cipher = AES.new(key, AES.MODE_CBC, INITIALIZATION_VECTOR)
            decrypted = cipher.decrypt(bytes(block))
            final.extend(decrypted)  
        
        # Remove the padding
        final = self._unpad(final)        
        
        return bytes(final)

    def aes_encrypt(self, raw, key = None):
        # If the key is not set, then use the data_key from the access_token that comes from the current session
        if not key:
            key = self.data_key() 

        # Make sure to pad the data
        self._pad(raw)
        
        # Break up the data into blockSize sized blocks
        blocks = [raw[i:i+self.blockSize] for i in range(0, len(raw), self.blockSize)]
        final = bytearray([])

        # Encrypt each block with a new Cipher. There doesn't seem to be a reset in Python for the Cipher object
        for block in blocks:    
            cipher = AES.new(key, AES.MODE_CBC, INITIALIZATION_VECTOR)
            encrypted = cipher.encrypt(bytes(block))
            final.extend(encrypted)
            
        return final

    def _pad(self, s):
        pad = self.blockSize - (len(s) % self.blockSize)
        s.extend([pad] * pad)
       
    def _unpad(self, s):
        return s[:-s[-1]]

    def data_key(self):
        """ 
        This is just horrible...
        """
        # MD5 sum, yay
        m = hashlib.md5()
        # Hash the appKey
        m.update(self.appKey.encode('ascii'))
        # Use only half the HEX output of the hash
        key_hash = m.hexdigest().encode('ascii')[0:16]
        # Decrypt the access token with that weird key
        key = self.aes_decrypt(bytearray.fromhex(self.accessToken), key_hash)
        return key     


