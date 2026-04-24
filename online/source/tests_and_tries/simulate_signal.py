"""
Example of a basic midas frontend that has one periodic equipment.

See `examples/multi_frontend.py` for an example that uses more
features (frontend index, polled equipment, ODB settings etc). 
"""

import midas
import midas.frontend
import midas.event
import numpy as np

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
        equip_name = "SimulateSignal"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 1
        default_common.period_ms = 10
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 0
        
        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        
        # You can set the status of the equipment (appears in the midas status page)
        # Parameters
        self.FormFactor = 1e5
        self.ResonatFrequancy_Hz = 100e6  # Resonance frequency in Hz
        omega_0 = 2 * np.pi * self.ResonatFrequancy_Hz  # Resonance angular frequency

        self.k = omega_0**2                 # Spring constant
        self.b = omega_0 / self.FormFactor  # Damping coefficient

        self.NumberOfSample = 1024
        self.SampligTime_s  = 1.4285714285714286e-09 # 700 MHz
        self.t_max = self.SampligTime_s * self.NumberOfSample
        
        # Thermal noise (Gaussian noise with mean 0 and standard deviation proportional to sqrt(kT/m))

        self.Teff = 3  # Temperature in Kelvin
        
        self.AmpWhiteNoise = 0
        self.AmpThermalNoise = 1
        
        self.counts = 0
        self.A0 = 0 
        self.V0 = 0
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
        t = np.arange(self.counts*self.t_max, (1+self.counts)*self.t_max, self.SampligTime_s)  # Time array
    
        # White noise (Gaussian noise with mean 0 and standard deviation 1)
        
        np.random.seed(self.counts)
        
        eta_white = self.AmpWhiteNoise * np.random.normal(0, 1, len(t))

        eta_thermal = self.AmpThermalNoise * np.random.normal(0, np.sqrt(1.38e-23 * self.Teff), len(t))
        
        eta_total = eta_white + eta_thermal
        
        # Initialize displacement and velocity arrays
        x = np.zeros(len(t))
        v = np.zeros(len(t))
        
        x[0]=self.A0
        v[0]=self.V0
        
        # Solve the differential equation using the Euler-Maruyama method
        for i in range(1, len(t)):
            a = (eta_total[i] - self.b * v[i-1] - self.k * x[i-1]) 
            v[i] = v[i-1] + a * self.SampligTime_s
            x[i] = x[i-1] + v[i] * self.SampligTime_s
            
        data = np.concatenate((t,x))
        
        event.create_bank("SSIM", midas.TID_DOUBLE, data)
        
        self.counts += 1
        self.A0 = x[-1]
        self.V0 = v[-1]
        
        self.set_status("Running")
        return event

class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "simulate_signal")
        
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