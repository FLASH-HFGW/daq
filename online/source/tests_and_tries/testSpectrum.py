import midas
import midas.frontend
import midas.event
import numpy as np
import os
import json
from pyftdi import gpio
import time
from ColdLibraryv3 import *

class MySpectrumEquipment(midas.frontend.EquipmentBase):
    """
    We define an "equipment" for each logically distinct task that this frontend
    performs. For example, you may have one equipment for reading data from a
    device and sending it to a midas buffer, and another equipment that updates
    summary statistics every 10s.
    
    Each equipment class you define should inherit from 
    `midas.frontend.EquipmentBase`, and should define a `readout_func` function.
    If you're creating a "polled" equipment (rather than a periodic one), you
    should also define a `poll_func` function in addition to `readout_func`.
    """
    def __init__(self, client):
        # The name of our equipment. This name will be used on the midas status
        # page, and our info will appear in /Equipment/MyPeriodicEquipment in
        # the ODB.
        equip_name = "testSpectrum"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_POLLED
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 6
        default_common.period_ms = 5000
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        
        self.spectrum = RnS_FSV( "TCPIP0::192.168.2.104::inst0::INSTR" )
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("Spectrum Initialized")
        
        
    def poll_func(self):
        self.set_status("Running")
        self.client.msg("Spectrum has been configured.")
        
        self.spectrum.set_frequency(10e9)
        return False
        
        
    def readout_func(self):
        return None
        


class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "testSpectrum")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.add_equipment(MySpectrumEquipment(self.client))
        

        
    #def begin_of_run(self, run_number):
    #     """
    #     This function will be called at the beginning of the run.
    #     You don't have to define it, but you probably should.
    #     You can access individual equipment classes through the `self.equipment`
    #     dict if needed.
    #     """
    #     self.set_all_equipment_status("Running", "greenLight")
    #     self.client.msg("Frontend has seen start of run number %d" % run_number)
    #     return midas.status_codes["SUCCESS"]
        
    # def end_of_run(self, run_number):
    #     self.set_all_equipment_status("Finished", "greenLight")
    #     self.client.msg("Frontend has seen end of run number %d" % run_number)
    #     return midas.status_codes["SUCCESS"]
    
    def frontend_exit(self):
        """
        Most people won't need to define this function, but you can use
        it for final cleanup if needed.
        """
        self.equipment['testSpectrum'].close()
        self.equipment['testSpectrum'].set_status("Stopped")
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()

