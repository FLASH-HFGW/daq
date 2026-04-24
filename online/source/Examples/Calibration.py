import midas
import midas.frontend
import midas.event
import numpy as np
import os
import json
from pyftdi import gpio
from ColdLibraryv3 import *
import time
import testSwitch_fe

class MyVNAEquipment(midas.frontend.EquipmentBase):
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
        equip_name = "VNA"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_POLLED
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 5
        default_common.period_ms = 100
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        
        self.vna = VNA( "TCPIP0::192.168.2.105::inst0::INSTR" )
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("VNA Initialized")
        
        
    def poll_func(self):
        daqState = self.client.odb_get("/Runinfo/State")
        print(daqState)
        '''
        if daqState == midas.STATE_RUNNING:
            self.client.msg("Could not calibrate. State is Running.")
            self.client.stop_run()
            pass
        else:
            self.vna.meas_param_znb(par="S21")
            self.vna.center(8e9)
        '''
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
        midas.frontend.FrontendBase.__init__(self, "Calibrarion_fe")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.Calibrate: bool = True
        self.client.odb_set("/Runinfo/Calibrate",self.Calibrate)
        
        self.add_equipment(MyVNAEquipment(self.client))
        #self.add_equipment(testSwitch_fe.MySwitchEquipment(self.client))

        
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
        self.Calibrate = False
        self.client.odb_set("/Runinfo/Calibrate",self.Calibrate)
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()

