#!/usr/bin/python3.9
import midas
import midas.frontend
import midas.event
import numpy as np
import os
import json
from pyftdi import gpio
from qcodes.instrument_drivers.AimTTi import _AimTTi_PL_P
import time

class MySwitchEquipment(midas.frontend.EquipmentBase):
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
        equip_name = "CryoSwitch"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 4
        default_common.period_ms = 1000
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        
        self.releController = gpio.GpioAsyncController()
        self.releController.configure('ftdi://ftdi:232h:FT7UQ713/1',direction=0xff)
        self.releController.write(0xff)
        #self.releController.close()
        self.tti = _AimTTi_PL_P.AimTTi("tti", "TCPIP::192.168.2.110::9221::SOCKET");
        self.tti.ch1.volt.set(28.1)
        voltage = self.tti.ch1.volt.get()
        chan1 = self.tti.ch1.channel
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "Voltage"), voltage)
        
        self.releController.write(252)
        time.sleep(0.005)
        #print('4 e 5 ON:\n')
        self.releController.write(228)
        self.tti.write(f"OP{chan1} 1")
        time.sleep(0.008)
        print('Done.\n')
        self.tti.write(f"OP{chan1} 0")
        self.releController.write(0xff)
        
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "C_set"), 1)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "C_status"), 1)
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("Relé Initialized")
        
        
        
        
    #def poll_func(self):
     #   print("sono qui")
     #   self.set_status("Running")
     #  
     #   #d = gpio.GpioAsyncController()
     #   #d.configure('ftdi://ftdi:232h:FT7UQ713/1',direction=0xff)
     #   self.client.msg("Switch has been configured.")
     #   #d.close()
     #   return False
        
        
    def readout_func(self):
        
        cset = client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "C_set"))
        cstatus = client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "C_status"))
        
        if cset == cstatus:
            pass
        
        elif cset==1 and cstatus==2:
            
            self.releController.write(252)
            time.sleep(0.005)
            #print('4 e 5 ON:\n')
            self.releController.write(228)
            self.tti.write(f"OP{chan1} 1")
            time.sleep(0.008)
            print('Done.\n')
            self.tti.write(f"OP{chan1} 0")
            self.releController.write(0xff)
           
            client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "C_status"), 1) 
            self.client.msg("Switch has been changed to C-1.")
        
        elif cset==2 and cstatus==1:
            
            #4,5 ON
            self.releController.write(231)
            self.tti.write(f"OP{chan1} 1")
            time.sleep(0.008)
            print('Done.\n')
            self.tti.write(f"OP{chan1} 0")
            self.releController.write(0xff)
            
            client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "C_status"), 2)
            self.client.msg("Switch has been changed to C-2.")
            
        self.set_status("Running")   
        
        return None
        


class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "CryoSwitch")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.add_equipment(MySwitchEquipment(self.client))
        
        #a = self._enabled_equipment()[0]
        #print(a._is_active_for_state(self.run_state))

        
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
        self.equipment['CryoSwitch'].releController.close()
        self.equipment['CryoSwitch'].tti.close()
        self.equipment['CryoSwitch'].set_status("Stopped")
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()

