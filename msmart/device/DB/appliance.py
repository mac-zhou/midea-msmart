
import logging
import time
from enum import Enum
from .command import get_state_command, appliance_response
from msmart.device.base import device

VERSION = '0.2.5'

_LOGGER = logging.getLogger(__name__)


class front_load_washer(device):

    class cycle_program_enum(Enum):
        UNKNOWN = 255
        Cotton = 0
        ECO = 1
        Quick = 2
        Mix = 3
        Chemical_Fiber = 4
        Wool = 5
        Active_Enzyme = 6
        Drum_Clean = 7
        Spin_Only = 9
        Rinse_Spin = 10
        Big = 11
        Childrens_Clothes = 12
        Underwear = 13
        Down_Jacket = 15
        Air_Wash = 21
        Single_Drying = 22
        Shirt = 28
        Laundry_Experts = 35

        @staticmethod
        def list():
            return list(map(lambda c: c.name, front_load_washer.cycle_program_enum))

        @staticmethod
        def get(value):
            if(value in front_load_washer.cycle_program_enum._value2member_map_):
                return front_load_washer.cycle_program_enum(value)
            _LOGGER.debug("Unknown cycle_program: {}".format(value))
            return front_load_washer.cycle_program_enum.UNKNOWN

    class machine_status_enum(Enum):
        UNKNOWN = 255
        IDLE = 0
        STANDBY = 1
        START = 2
        PAUSE = 3
        END = 4
        FAULT = 5 
        DELAY = 6

        @staticmethod
        def list():
            return list(map(lambda c: c.name, front_load_washer.machine_status_enum))

        @staticmethod
        def get(value):
            if(value in front_load_washer.machine_status_enum._value2member_map_):
                return front_load_washer.machine_status_enum(value)
            _LOGGER.debug("Unknown machine_status: {}".format(value))
            return front_load_washer.machine_status_enum.Unknown    

    def __init__(self, *args, **kwargs):
        super(front_load_washer, self).__init__(*args, **kwargs)
        self._type = 0xdb
        self._power = False
        self._machine_status = front_load_washer.machine_status_enum.IDLE
        self._work_mode = False
        self._cycle_program = front_load_washer.cycle_program_enum.Cotton
        self._water_line = 0
        self._dring_state = 0
        self._rinse_times = 0
        self._temperature = 0
        self._dehydrate_speed = 0
        self._wash_times = 0
        self._dehydrate_time = 0
        self._wash_dose = 0
        self._memory = 0
        self._supple_dose  = 0
        self._remainder_time = 0
        self._appliance_type = 0xff

        self._on_timer = None
        self._off_timer = None
        self._online = True
        self._active = True
    
    def __str__(self):
        return str(self.__dict__)

    def refresh(self):
        cmd = get_state_command(self.type)
        self._send_cmd(cmd)
    
    def _send_cmd(self, cmd):
        responses = self.send_cmd(cmd)
        for response in responses:
            self._process_response(response)

    def _process_response(self, data):
        if self.process_response(data):
            response = appliance_response(data)
            self._defer_update = False
            self._support = True
            self.update(response)

    def update(self, res: appliance_response):   
        if res.update:     
            self._power = res.power
            self._machine_status = front_load_washer.machine_status_enum.get(res.machine_status)
            self._work_mode = res.work_mode
            self._cycle_program = front_load_washer.cycle_program_enum.get(res.cycle_program)
            self._water_line = res.water_line
            self._dring_state = res.dring_state
            self._rinse_times = res.rinse_times
            self._temperature = res.temperature
            self._dehydrate_speed = res.dehydrate_speed
            self._wash_times = res.wash_times
            self._dehydrate_time = res.dehydrate_time
            self._wash_dose = res.wash_dose
            self._memory = res.memory
            self._supple_dose = res.supple_dose
            self._remainder_time = res.remainder_time
            self._wash_experts = res.wash_experts
            self._appliance_type = res.appliance_type
            # self._type = res.appliance_type
            # self._on_timer = res.on_timer
            # self._off_timer = res.off_timer


    @property
    def power(self):
        return self._power
    
    @property
    def machine_status(self):
        return self._machine_status

    @property
    def work_mode(self):
        return self._work_mode

    @property
    def cycle_program(self):
        return self._cycle_program
    
    @property
    def water_line(self):
        return self._water_line
    
    @property
    def dring_state(self):
        return self._dring_state
    
    @property
    def rinse_times(self):
        return self._rinse_times
    
    @property
    def temperature(self):
        return self._temperature

    @property
    def dehydrate_speed(self):
        return self._dehydrate_speed

    @property
    def wash_times(self):
        return self._wash_times

    @property
    def dehydrate_time(self):
        return self._dehydrate_time

    @property
    def wash_dose(self):
        return self._wash_dose
    
    @property
    def memory(self):
        return self._memory
    
    @property
    def supple_dose(self):
        return self._supple_dose
    
    @property
    def remainder_time(self):
        return self._remainder_time
    
    @property
    def wash_experts(self):
        return self._wash_experts

    @property
    def on_timer(self):
        return self._on_timer

    @property
    def off_timer(self):
        return self._off_timer
