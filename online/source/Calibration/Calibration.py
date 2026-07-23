#!/usr/bin/python3.9
import midas
import midas.frontend
import midas.event
import numpy as np
import os
import json
from pyftdi import gpio
import ColdLibraryv3 as coldlib
from ColdLibraryv3 import modules
import time
from datetime import datetime
from urllib.request import urlopen
import sys

########################################
# Define a function to send an HTTP command to the switch rack and get the result
########################################

def Get_HTTP_Result(CmdToSend):

    # Specify the IP address of the switch box
    CmdToSend = "http://192.168.2.113/:" + CmdToSend

    # Send the HTTP command and try to read the result
    try:
        HTTP_Result = urlopen(CmdToSend, timeout=1)
        PTE_Return = HTTP_Result.read()

        # The switch displays a web GUI for unrecognised commands
        if len(PTE_Return) > 100:
            print ("Error, command not found:", CmdToSend)
            PTE_Return = "Invalid Command!"

    # Catch an exception if URL is incorrect (incorrect IP or disconnected)
    except:
        print ("Error, no response from device; check IP address and connections.")
        PTE_Return = "No Response!"
        sys.exit()      # Exit the script

    # Return the response
    return PTE_Return



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
        self.equip_name = "VNA"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 6
        default_common.period_ms = 1000
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, self.equip_name, default_common)
        
        #### apro comunicazione strumenti
        self.vna = coldlib.VNA( modules['VNA-ZNB'] )

        #variabile si/no se è stato cambiato qualche parametro. False = NO, True = YES
        hasChanged : bool = False

        
        Npoints = self.vna.inst.query(':SENS1:SWE:POIN?')
        ifbw = self.vna.ifbw()
        center = self.vna.center()
        span = self.vna.span()
        power = self.vna.power()
        
        #setup odb variables if not existing
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Scatter"), 'S21')
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Format"), 'POL')
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Npoints"), Npoints)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "IFBW_Hz"), ifbw)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Center_Hz"), center)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Span_Hz"), span)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Power_dBm"), power)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "hasChanged"), False)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Sart_Calib"), False)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"), str('0'))
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("VNA Initialized")
        
        
    def readout_func(self):

        hasChanged = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "hasChanged"))

        if hasChanged == True:
            Get_HTTP_Result("SETD=0")   # Set switch D
            
            scatter = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Scatter"))
            formato = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Format"))
            Npoints = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Npoints"))
            ifbw = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "IFBW_Hz"))
            center = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Center_Hz"))
            span = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Span_Hz"))
            power = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Power_dBm"))

            start_calib = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Start_Calib"))

            #setting new parameters
            self.vna.meas_param_znb(par=scatter)
            self.vna.format(format=formato)
            self.vna.ifbw(ifbw)
            self.vna.center(center)
            self.vna.span(span)
            self.vna.Npoints(npoints=Npoints)
            self.vna.power(power)

            if start_calib:
                self.vna.sweep_time_auto(1)
                self.vna.trigger_src('IMM')
                self.vna.trigger_mode(mode='CONT', state='OFF')

                calibState = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"))
                description = self.client.odb_get("/Equipment/{:}/vnaCalib/{:}".format(self.equip_name, "Description"))

                freq = np.linspace(center-span/2, center+span/2, Npoints)

                if calibState == "S22cav": #S51 sulle linee
                    Get_HTTP_Result("SETA=1")   # Set switch A
                    Get_HTTP_Result("SETB=0")   # Set switch B
                    Get_HTTP_Result("SETC=1")   # Set switch C
                    
                    self.vna.meas_param_znb(par='S21')
                    self.vna.format(format='POL')
                    self.vna.output(1)
                    self.vna.inst.write(':INIT1')
                    time.sleep(0.1)
                    #retrieve data from VNA sweep
                    y1, y2 = self.vna.read_znb()
                    self.vna.autoscale(trace=1)
                    data = np.c_[freq, y1, y2]
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
                    np.savetxt('/home/cold/data/{:}_{:}_{:}.txt'.format(calibState, description, timestamp), data)

                    #save on ODB real and imag data of selected scattering parameter
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataReal".format(self.equip_name, calibState), y1)
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataImag".format(self.equip_name, calibState), y2)


                elif calibState == "S21cav":   #S53 sulle linee
                    Get_HTTP_Result("SETA=0")   # Set switch A
                    Get_HTTP_Result("SETB=0")   # Set switch B
                    Get_HTTP_Result("SETC=1")   # Set switch C

                    self.vna.meas_param_znb(par='S21')
                    self.vna.format(format='POL')
                    self.vna.output(1)
                    self.vna.inst.write(':INIT1')
                    time.sleep(0.05)
                    #retrieve data from VNA sweep
                    y1, y2 = self.vna.read_znb()
                    self.vna.autoscale(trace=1)
                    data = np.c_[freq, y1, y2]
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
                    np.savetxt('/home/cold/data/{:}_{:}_{:}.txt'.format(calibState, description, timestamp), data)

                    #save on ODB real and imag data of selected scattering parameter
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataReal".format(self.equip_name, calibState), y1)
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataImag".format(self.equip_name, calibState), y2)


                elif calibState == "S12cav":   #S31 sulle linee
                    Get_HTTP_Result("SETA=0")   # Set switch A
                    Get_HTTP_Result("SETB=1")   # Set switch B
                    Get_HTTP_Result("SETC=0")   # Set switch C

                    self.vna.meas_param_znb(par='S12')
                    self.vna.format(format='POL')
                    self.vna.output(1)
                    self.vna.inst.write(':INIT1')
                    time.sleep(0.1)
                    #retrieve data from VNA sweep
                    y1, y2 = self.vna.read_znb()
                    self.vna.autoscale(trace=1)
                    data = np.c_[freq, y1, y2]
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
                    np.savetxt('/home/cold/data/{:}_{:}_{:}.txt'.format(calibState, description, timestamp), data)

                    #save on ODB real and imag data of selected scattering parameter
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataReal".format(self.equip_name, calibState), y1)
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataImag".format(self.equip_name, calibState), y2)


                elif calibState == "S11cav":   #S33 sulle linee
                    Get_HTTP_Result("SETA=0")   # Set switch A
                    Get_HTTP_Result("SETB=0")   # Set switch B
                    Get_HTTP_Result("SETC=0")   # Set switch C

                    self.vna.meas_param_znb(par='S11')
                    self.vna.format(format='POL')
                    self.vna.output(1)
                    self.vna.inst.write(':INIT1')
                    time.sleep(0.1)
                    #retrieve data from VNA sweep
                    y1, y2 = self.vna.read_znb()
                    self.vna.autoscale(trace=1)
                    data = np.c_[freq, y1, y2]
                    now = datetime.now()
                    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
                    np.savetxt('/home/cold/data/{:}_{:}_{:}.txt'.format(calibState, description, timestamp), data)

                    #save on ODB real and imag data of selected scattering parameter
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataReal".format(self.equip_name, calibState), y1)
                    self.client.odb_set("/Equipment/{:}/vnaCalib/{:}_dataImag".format(self.equip_name, calibState), y2)


                elif calibState == "0":
                    self.vna.output(1)
                    sweep_time = self.vna.inst.query(':SENS1:SWE:TIME?')
                    self.vna.inst.write(':INIT1')
                    time.sleep(float(sweep_time))
                    self.vna.autoscale(trace=1)


                #resets calibState flag
                calibState = '0'
                self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"), calibState)

                self.vna.trigger_mode(mode='CONT', state='OFF')
                self.vna.output(0)

                start_calib = False
                self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Start_Calib"), start_calib)

            hasChanged = False
            self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "hasChanged"), hasChanged)


        
        return None
    
    
    
class MySAEquipment(midas.frontend.EquipmentBase):
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
        self.equip_name = "SA"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 5
        default_common.period_ms = 1000
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, self.equip_name, default_common)
        
        #### apro comunicazione strumenti
        self.sa = coldlib.RnS_FSV( modules['RS-spectrum'] )
        self.sa.set_trace_mode(trace_number=1,mode='AVER')
        
        #define save data path
        self.savePath = '/home/cold/data/spectrumAnalyzer'

        #variabile si/no se è stato cambiato qualche parametro. False = NO, True = YES
        hasChanged : bool = False

        center = self.sa.inst.query('FREQ:CENT?')
        span = self.sa.inst.query('FREQ:SPAN?')
        Npoints = self.sa.inst.query('SWE:POIN?')
        rbw = self.sa.inst.query('BAND:RES?')
        vbw = self.sa.inst.query('BAND:VID?')
        reflev = self.sa.inst.query('DISP:TRAC:Y:RLEV?')
        atten = self.sa.inst.query('INP:ATT?')
        Navg = self.sa.inst.query('AVER:COUN?')
        detector = self.sa.inst.query('DET?')
        
        #setup odb variables if not existing
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Center_Hz"), center)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Span_Hz"), span)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Npoints"), Npoints)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "RBW_Hz"), rbw)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "VBW_Hz"), vbw)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Ref_level"), reflev)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Input_Atten"), atten)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Navg"), Navg)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Detector_type"), detector)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "hasChanged"), False)
        client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"), str('0'))
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("SA Initialized")
        
        
    def readout_func(self):

        hasChanged = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "hasChanged"))

        if hasChanged == True:
            Get_HTTP_Result("SETA=0")   # Set switch A
            Get_HTTP_Result("SETB=0")   # Set switch B
            Get_HTTP_Result("SETC=0")   # Set switch C
            Get_HTTP_Result("SETD=1")   # Set switch D
            
            center = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Center_Hz"))
            span = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Span_Hz"))
            Npoints = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Npoints"))
            RBW = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "RBW_Hz"))
            VBW = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "VBW_Hz"))
            reflev = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Ref_level"))
            atten = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Input_Atten"))
            Navg = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Navg"))
            detType = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Detector_type"))

            calibState = self.client.odb_get("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"))

            #setting new parameters
            self.sa.set_frequency(center)
            self.sa.set_span(span)
            self.sa.set_sweep_points(Npoints)
            self.sa.set_RBW(RBW)
            self.sa.set_VBW(VBW)
            self.sa.set_reference_level(reflev)
            self.sa.set_input_attenuation(atten)
            self.sa.average_count(Navg) #setting number of averages
            self.sa.set_detector(detType)

            if calibState == 'sweep':
                self.sa.disable_continuous_sweep() #single sweep mode.
                self.sa.average_type('LIN') #turn to linear units before averaging
                self.sa.average_state('ON')
                                      
                self.sa.enable_measurement_channel(channel_number=1)
                self.sa.initiate_measurement()
                
                self.sa.disable_measurement_channel(channel_number=1)
                self.sa.average_state('OFF')

                self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"), '0')
                
            elif calibState == 'save':
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
                
                self.sa.disable_continuous_sweep() #single sweep mode.
                self.sa.average_type('LIN') #turn to linear units before averaging
                self.sa.average_state('ON')
                
                self.sa.enable_measurement_channel(channel_number=1)
                self.sa.initiate_measurement()
                fsweep, P = self.sa.fetch_trace()
                data = np.c_[fsweep, P]
                np.savetxt('{:}_{:}.txt'.format(self.savePath, timestamp), data)
                #self.sa.save_trace_to_file(trace_number=1, file_path=self.savePath+'_{:}.txt'.format(timestamp) )
                
                self.sa.disable_measurement_channel(channel_number=1)
                self.sa.average_state('OFF')
                
                self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "Calib_state"), '0')
            
            elif calibState == '0':
                pass

            else:
                self.client.msg("calibState can only be 0, sweep or save.")
                

            self.client.odb_set("/Equipment/{:}/Variables/{:}".format(self.equip_name, "hasChanged"), False)

        
        return None
    
        


class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "Calibration")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        
        self.add_equipment(MyVNAEquipment(self.client))
        self.add_equipment(MySAEquipment(self.client))

        
    def begin_of_run(self, run_number):
        """
        This function will be called at the beginning of the run.
        You don't have to define it, but you probably should.
        You can access individual equipment classes through the `self.equipment`
        dict if needed.
        """
        #self.set_all_equipment_status("Running", "greenLight")
        #self.client.msg("Frontend has seen start of run number %d" % run_number)

        self.equipment['VNA'].vna.output(0)
        self.equipment['VNA'].vna.trigger_mode(mode='CONT', state='OFF')
        
        return midas.status_codes["SUCCESS"]
        
    def end_of_run(self, run_number):
        self.equipment['VNA'].vna.output(0)
        self.equipment['VNA'].vna.trigger_mode(mode='CONT', state='OFF')
    #     self.set_all_equipment_status("Finished", "greenLight")
    #     self.client.msg("Frontend has seen end of run number %d" % run_number)
        return midas.status_codes["SUCCESS"]
    
    def frontend_exit(self):
        """
        Most people won't need to define this function, but you can use
        it for final cleanup if needed.
        """
        self.equipment['VNA'].vna.close()
        self.equipment['SA'].sa.close()
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()

