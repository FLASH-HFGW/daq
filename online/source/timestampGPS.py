"""
Example of a basic midas frontend that has one periodic equipment.

See `examples/multi_frontend.py` for an example that uses more
features (frontend index, polled equipment, ODB settings etc). 
"""

import midas
import midas.frontend
import midas.event
import numpy as np
import serial

class MyPeriodicEquipment(midas.frontend.EquipmentBase):
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
        self.equip_name = "timestampGPS"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 8
        default_common.period_ms = 950
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0
        
        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, self.equip_name, default_common)
        
        self.ser = serial.Serial(
            port='/dev/ttyUSB1',
            baudrate=9600,
            timeout=1,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS
            )
        
        linea = self.ser.readline().decode('utf-8').strip()
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "timestamp"), linea)
        
        self.set_status("Initialized")
      
        
    def readout_func(self):
        """
        For a periodic equipment, this function will be called periodically
        (every 100ms in this case). It should return either a `midas.event.Event`
        or None (if we shouldn't write an event).
        """
        
        linea = self.ser.readline().decode('utf-8').strip()
        self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "timestamp"), linea)
        
        self.set_status("Running")
        return None

class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "timestampGPS")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.add_equipment(MyPeriodicEquipment(self.client))
        
    #def begin_of_run(self, run_number):
    #    """
    #    This function will be called at the beginning of the run.
    #    You don't have to define it, but you probably should.
    #    You can access individual equipment classes through the `self.equipment`
    #    dict if needed.
    #    """
    #    self.set_all_equipment_status("Running", "greenLight")
    #    self.client.msg("Frontend has seen start of run number %d" % run_number)
    #    return midas.status_codes["SUCCESS"]
    #    
    #def end_of_run(self, run_number):
    #    #self.card.close()
    #    self.set_all_equipment_status("Finished", "greenLight")
    #    self.client.msg("Frontend has seen end of run number %d" % run_number)
    #    return midas.status_codes["SUCCESS"]
    
    def frontend_exit(self):
        """
        Most people won't need to define this function, but you can use
        it for final cleanup if needed.
        """
        
        self.equipment['timestampGPS'].set_status("Stopped")
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()