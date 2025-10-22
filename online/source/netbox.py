#!/usr/bin/python3.9
"""
Example of a basic midas frontend that has one periodic equipment.

See `examples/multi_frontend.py` for an example that uses more
features (frontend index, polled equipment, ODB settings etc). 
"""

import midas
import midas.frontend
import midas.event
import numpy as np
import spcm
from spcm import units

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
        equip_name = "Netbox"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 4
        default_common.period_ms = 100
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0
        
        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        
        self.card = spcm.Card('TCPIP::192.168.2.109::inst0::INSTR').open()
        self.counts = 0
        
        # do a simple standard setup
        self.card.card_mode(spcm.SPC_REC_STD_SINGLE)     # single trigger standard mode
        self.card.timeout(5 * units.s)                     # timeout 5 s

        trigger = spcm.Trigger(self.card)
        trigger.or_mask(spcm.SPC_TMASK_NONE)       # trigger set to none #software
        trigger.and_mask(spcm.SPC_TMASK_NONE)      # no AND mask

        clock = spcm.Clock(self.card)
        clock.mode(spcm.SPC_CM_INTPLL)            # clock mode internal PLL
        clock.sample_rate(20 * units.MHz, return_unit=units.MHz)

        # setup the channels
        self.channel0, = spcm.Channels(self.card, card_enable=spcm.CHANNEL0) # enable channel 0
        self.channel0.amp(200 * units.mV)
        self.channel0.offset(0 * units.mV)
        self.channel0.termination(1)
        # channels.coupling(spcm.COUPLING_DC)

        # Channel triggering
        trigger.ch_or_mask0(self.channel0.ch_mask())
        trigger.ch_mode(self.channel0, spcm.SPC_TM_POS)
        trigger.ch_level0(self.channel0, 0 * units.mV, return_unit=units.mV)
        
        self.set_status("Initialized")
      
        
    def readout_func(self):
        """
        For a periodic equipment, this function will be called periodically
        (every 100ms in this case). It should return either a `midas.event.Event`
        or None (if we shouldn't write an event).
        """
        
        # In this example, we just make a simple event with one bank.
        event = midas.event.Event()
        
        # Create a bank (called "MYBK") which in this case will store 8 ints.
        # data can be a list, a tuple or a numpy array.
        # If performance is a strong factor (and you have large bank sizes), 
        # you should use a numpy array instead of raw python lists. In
        # that case you would have `data = numpy.ndarray(8, numpy.int32)`
        # and then fill the ndarray as desired. The correct numpy data type
        # for each midas TID_xxx type is shown in the `midas.tid_np_formats`
        # dict.
        # print(self.counts)
        
        # define the data buffer
        data_transfer = spcm.DataTransfer(self.card)
        data_transfer.duration(100*units.us, post_trigger_duration=80*units.us)
        # Start DMA transfer
        data_transfer.start_buffer_transfer(spcm.M2CMD_DATA_STARTDMA)

        # start card
        self.card.start(spcm.M2CMD_CARD_ENABLETRIGGER, spcm.M2CMD_DATA_WAITDMA)
        
        t = np.array(data_transfer.time_data().magnitude)
        V = np.array( self.channel0.convert_data(data_transfer.buffer[self.channel0, :], units.V).magnitude )
            
        data = np.concatenate((t,V))
        
        event.create_bank("SSIM", midas.TID_DOUBLE, data)
        
        self.counts += 1
       
        
        self.set_status("Running")
        return event

class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "netbox")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.add_equipment(MyPeriodicEquipment(self.client))
        
    def begin_of_run(self, run_number):
        """
        This function will be called at the beginning of the run.
        You don't have to define it, but you probably should.
        You can access individual equipment classes through the `self.equipment`
        dict if needed.
        """
        self.set_all_equipment_status("Running", "greenLight")
        self.client.msg("Frontend has seen start of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]
        
    def end_of_run(self, run_number):
        #self.card.close()
        self.set_all_equipment_status("Finished", "greenLight")
        self.client.msg("Frontend has seen end of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]
    
    def frontend_exit(self):
        """
        Most people won't need to define this function, but you can use
        it for final cleanup if needed.
        """
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()