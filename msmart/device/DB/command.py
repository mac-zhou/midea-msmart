
import logging
import datetime
import msmart.crc8 as crc8
from msmart.utils import getBit, getBits
from msmart.const import CMD_TYPE_CONTROL, CMD_TYPE_QUERRY, CMD_TYPE_REPORT

VERSION = '0.2.3'

_LOGGER = logging.getLogger(__name__)


class base_command:

    def __init__(self, device_type=0xAC):
        # More magic numbers. I'm sure each of these have a purpose, but none of it is documented in english. I might make an effort to google translate the SDK
        self.data = bytearray([
            # 0 header
            0xaa,
            # 1 command lenght: N+10
            0x20,
            # 2 device type
            0xac,
            # 3 Frame SYN CheckSum
            0x00, 
            # 4-5 Reserved 
            0x00, 0x00, 
            # 6 Message ID 
            0x00, 
            # 7 Frame Protocol Version
            0x00,
            # 8 Device Protocol Version 
            0x00,
            # 9 Messgae Type: request is 0x03; setting is 0x02
            0x03,
            
            # Byte0 - Data request/response type: 0x41 - check status; 0x40 - Set up
            0x41,
            # Byte1
            0x81,
            # Byte2 - operational_mode
            0x00,
            # Byte3
            0xff,
            # Byte4
            0x03,
            # Byte5
            0xff,
            # Byte6
            0x00,
            # Byte7 - Room Temperature Request: 0x02 - indoor_temperature, 0x03 - outdoor_temperature
            # when set, this is swing_mode
            0x02,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            # Message ID
            0x00
        ])
        self.data[-1] = datetime.datetime.now().second
        self.data[0x02] = device_type

    def checksum(self, data):
        c = (~ sum(data) + 1) & 0xff
        return (~ sum(data) + 1) & 0xff

    def finalize(self, addd_crc8=True):
        # Add the CRC8
        if addd_crc8:
            self.data.append(crc8.calculate(self.data[10:]))
        # Set the length of the command data
        # self.data[0x01] = len(self.data)
        # Add cheksum
        self.data.append(self.checksum(self.data[1:]))
        _LOGGER.debug("Finalize request data: {}".format(self.data.hex()))
        return self.data

class appliance_response:

    def __init__(self, data: bytearray):
        self.header = data[:0xa]
        self.data = data[0xa:-1]
        self.message_type = data[0x09]
        self.update = True
        if self.message_type ==CMD_TYPE_REPORT and self.data[0] != CMD_TYPE_REPORT:
            self.update = False
        _LOGGER.info("Appliance response type: {} update:{} data: {}".format(self.message_type, self.update, self.data.hex()))

    # Byte 0x01
    @property
    def power(self):
        return (self.data[1] & 0x1) > 0

    @property
    def machine_status(self):
        return self.data[2]

    @property
    def work_mode(self):
        return self.data[3]
    
    @property
    def cycle_program(self):
        return self.data[4]
    
    @property
    def water_line (self):
        return self.data[5]

    @property
    def dring_state(self):
        return getBits(self.data, 6, 0, 3)

    @property
    def rinse_times(self):
        return getBits(self.data, 6, 4, 7)
    
    @property
    def temperature(self):
        return self.data[7]
    
    @property
    def dehydrate_speed(self):
        return self.data[8]
    
    @property
    def wash_times(self):
        return self.data[9]
    
    @property
    def dehydrate_time(self):
        return self.data[10]

    @property
    def wash_dose(self):
        return self.data[11]

    @property
    def memory(self):
        return self.data[12]
    
    @property
    def supple_dose(self):
        return self.data[13]

    @property
    def remainder_time(self):
        return self.data[17] | self.data[18] << 8
    
    @property
    def wash_experts(self):
        return self.data[19]

    @property
    def appliance_type(self):
        if self.message_type == CMD_TYPE_QUERRY:
            return self.data[20]
    
    @property
    def appliance_code(self):
        if self.message_type == CMD_TYPE_QUERRY:
            return chr(self.data[23]) + chr(self.data[22]) + chr(self.data[21])