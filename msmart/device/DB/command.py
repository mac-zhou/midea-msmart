
import logging
from enum import IntEnum
from msmart.utils import getBit, getBits
from msmart.const import FRAME_TYPE
from msmart.base_command import command as base_command

VERSION = '0.2.5'

_LOGGER = logging.getLogger(__name__)

class get_state_command(base_command):
    def __init__(self, device_type=0xdb, FRAME_TYPE=FRAME_TYPE.Request):
        super().__init__(device_type, FRAME_TYPE)

    @property
    def payload(self):
        return bytes([
            # Get state
            0x03,
        ])

class appliance_response:

    def __init__(self, data: bytearray):
        self.header = data[:0xa]
        self.data = data[0xa:-1]
        self.message_type = data[0x09]
        self.update = True
        if self.message_type == FRAME_TYPE.Report and self.data[0] !=  FRAME_TYPE.Report:
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
        if self.message_type == FRAME_TYPE.Set:
            return self.data[20]
    
    @property
    def appliance_code(self):
        if self.message_type ==  FRAME_TYPE.Set:
            return chr(self.data[23]) + chr(self.data[22]) + chr(self.data[21])