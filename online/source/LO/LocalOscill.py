#!/usr/bin/python3.9
import midas
import midas.frontend
import midas.event
import numpy as np
import os, re
import json
import ColdLibraryv3 as coldlib
from ColdLibraryv3 import modules
import time

class MyLOEquipment(midas.frontend.EquipmentBase):
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
        equip_name = "LocalOscill"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 7
        default_common.period_ms = 1000
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        
        #### apro comunicazione strumenti
        self.RShandler = coldlib.RS(modules["RS_SMA100B"])
        self.Teledyne = coldlib.Teledyne(modules["T3AFG500"])

        #### leggo i parametri dagli strumenti
        powerRS = float(self.RShandler.power())
        freqRS = float(self.RShandler.freq())
        onoffRS = int(self.RShandler.output())
        parTeledCh1 = self.Teledyne.inst.query('C1:BSWV?')
        parTeledCh2 = self.Teledyne.inst.query('C2:BSWV?')
        stateTeledCh1 = self.Teledyne.inst.query('C1:OUTP?')
        stateTeledCh2 = self.Teledyne.inst.query('C2:OUTP?')
        
        #variabile si/no se è stato cambiato qualche parametro. False = NO, True = YES
        hasChanged : bool = False


        #### uso regex per estrarre da tutta la stringa dei parametri del teledyne la frequenza e l'ampiezza
        match1 = re.search(r'FRQ,(.*?)HZ',parTeledCh1)
        freqTeledCh1 = float(match1.group(1))
        match1 = re.search(r'AMP,(.*?)V,AMPVRMS',parTeledCh1)
        ampTeledCh1 = float(match1.group(1))

        match2 = re.search(r'FRQ,(.*?)HZ',parTeledCh2)
        freqTeledCh2 = float(match2.group(1))
        match2 = re.search(r'AMP,(.*?)V,AMPVRMS',parTeledCh2)
        ampTeledCh2 = float(match2.group(1))

        match1 = re.search(r'OUTP (.*?),LOAD',stateTeledCh1)
        strTeledCh1 = match1.group(1)
        match2 = re.search(r'OUTP (.*?),LOAD',stateTeledCh2)
        strTeledCh2 = match2.group(1)

        if strTeledCh1 == 'OFF':
            onoffTeledCh1 : int = 0
        elif strTeledCh1 == 'ON':
            onoffTeledCh1 : int = 1
        else:
            print('break') #mettere messaggio errore midas

        if strTeledCh2 == 'OFF':
            onoffTeledCh2 : int = 0
        elif strTeledCh2 == 'ON':
            onoffTeledCh2 : int = 1
        else:
            print('break') #mettere messaggio errore midas
        
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "freq RS"), freqRS)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "power RS"), powerRS)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "onoff RS"), onoffRS)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "freq Teled Ch1"), freqTeledCh1)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "Vpp Teled Ch1"), ampTeledCh1)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "onoff Teled Ch1"), onoffTeledCh1)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "freq Teled Ch2"), freqTeledCh2)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "Vpp Teled Ch2"), ampTeledCh2)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "onoff Teled Ch2"), onoffTeledCh2)

        client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "hasChanged"), hasChanged)
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("LO Initialized")
        
        
        
        
    #def poll_func(self):
     #   return False
        
        
    def readout_func(self):
        
        equip_name = "LocalOscill"

        hasChanged = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "hasChanged"))

        if hasChanged == True:
        
            freqRS = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "freq RS"))
            powerRS = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "power RS"))
            onoffRS = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "onoff RS"))
            freqTeledCh1 = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "freq Teled Ch1"))
            ampTeledCh1 = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "Vpp Teled Ch1"))
            onoffTeledCh1 = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "onoff Teled Ch1"))
            freqTeledCh2 = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "freq Teled Ch2"))
            ampTeledCh2 = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "Vpp Teled Ch2"))
            onoffTeledCh2 = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(equip_name, "onoff Teled Ch2"))

            if onoffTeledCh1 == 1:
                strTeledCh1 : str = 'ON'
            elif onoffTeledCh1 == 0:
                strTeledCh1 : str = 'OFF'
            else:
                print('break') #mettere messaggio errore midas

            if onoffTeledCh2 == 1:
                strTeledCh2 : str = 'ON'
            elif onoffTeledCh2 == 0:
                strTeledCh2 : str = 'OFF'
            else:
                print('break') #mettere messaggio errore midas
            
            #### set dei parametri sugli strumenti
            self.RShandler.power(powerRS)
            self.RShandler.freq(freqRS)
            self.RShandler.output(onoffRS)
            self.Teledyne.amp(1,ampTeledCh1)
            self.Teledyne.freq(1,freqTeledCh1)
            self.Teledyne.output(1,strTeledCh1)
            self.Teledyne.amp(2,ampTeledCh2)
            self.Teledyne.freq(2,freqTeledCh2)
            self.Teledyne.output(2,strTeledCh2)

            hasChanged = False
            self.client.odb_set("/Equipment/{:}/Variables/{:}".format(equip_name, "hasChanged"), hasChanged)

        else: pass

        
        self.set_status("Running")   
        
        return None
        



class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "LocalOscill")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.add_equipment(MyLOEquipment(self.client))
        
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
        self.equipment['LocalOscill'].RShandler.close()
        self.equipment['LocalOscill'].Teledyne.close()
        self.equipment['LocalOscill'].set_status("Stopped")
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()

