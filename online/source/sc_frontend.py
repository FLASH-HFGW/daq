#!/usr/bin/python3.9
import midas
import midas.frontend
import midas.event
import numpy as np
import os
import json

def get_last_row_as_list(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        last_line = lines[-1].strip().split('\t')
    return last_line

def get_first_row_as_list(file_path):
    with open(file_path, 'r') as file:
        first_line = file.readline().strip().split('\t')
    return first_line

def get_N_row_as_list(file_path, N):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        line = lines[N].strip().split('\t')
    return line

def get_most_recent_file(directory, prefix, extension):
    # Ottieni una lista di file nella directory
    files = os.listdir(directory)
    
    # Filtra i file che iniziano con il prefisso specificato e hanno l'estensione determinata
    files = [f for f in files if f.startswith(prefix) and f.endswith(extension) and os.path.isfile(os.path.join(directory, f))]
    
    if not files:
        return None
    
    # Ottieni il percorso completo del file più recente
    most_recent_file = max(files, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
    
    return os.path.join(directory, most_recent_file)

def concatenate_arrays_to_json(keys, values):
    # Concatena i due array in un dizionario
    data = dict(zip(keys, values))
    
    # Converti il dizionario in una stringa JSON
    json_data = json.dumps(data, indent=4)
    
    return json_data


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
        equip_name = "SCFrontend"
        
        # Define the "common" settings of a frontend. These will appear in
        # /Equipment/MyPeriodicEquipment/Common. The values you set here are
        # only used the very first time this frontend/equipment runs; after 
        # that the ODB settings are used.
        default_common = midas.frontend.InitialEquipmentCommon()
        # attenzione molti modi python/midas/frontend.py sono non supportati
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 3
        default_common.period_ms = 60000
        default_common.read_when = midas.RO_ALWAYS
        default_common.log_history = 1

        # You MUST call midas.frontend.EquipmentBase.__init__ in your equipment's __init__ method!
        midas.frontend.EquipmentBase.__init__(self, client, equip_name, default_common)
        try:
            M = get_most_recent_file('/media/Mercury_dati/', 'Mercury_', '.txt')
            self.header_M = get_first_row_as_list(M)[1:]
            client.odb_set("/Equipment/{:}/Settings/Names {:}".format(equip_name, "MERC"), self.header_M)
        except:
            self.client.msg("Error configuting Mercury datasets")
            pass
        try:
            FP = get_most_recent_file('/media/avs-47/', 'logFP___', '.dat')
            self.header_FP = get_first_row_as_list(FP)[1:]
            client.odb_set("/Equipment/{:}/Settings/Names {:}".format(equip_name, "TEFP"), self.header_FP)
        except:
            self.client.msg("Error configuting FP datasets")
            pass
        try:
            AVS = get_most_recent_file('/media/avs-47/', 'LogAVS___', '.dat')
            self.header_AVS = get_N_row_as_list(AVS, 2)[1:]
            client.odb_set("/Equipment/{:}/Settings/Names {:}".format(equip_name, "TAVS"), self.header_AVS)
        except:
            self.client.msg("Error configuting AVS datasets")
            pass
        
        # You can set the status of the equipment (appears in the midas status page)
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

        try:
            # Definisci i dati come un array di byte
            M = get_most_recent_file('/media/Mercury_dati/', 'Mercury_', '.txt')
            datas = get_last_row_as_list(M)
            data = [float(item) for item in datas[1:]]
            # Crea un banco con i dati per formati vedi: https://bitbucket.org/tmidas/midas/src/develop/python/midas/__init__.py
            event.create_bank("MERC", midas.TID_FLOAT, data)
            #self.client.odb_set("Equipment/SCFrontend/Variables/T_Merc2[0]", data[2])
            #self.client.odb_set("Equipment/SCFrontend/Variables/T_Merc2[1]", data[8])
            # self.client.odb_set("/pyexample", concatenate_arrays_to_json(self.header_M, data))
        except Exception as e:
            print(e)
            self.client.msg("Error reading Mercury datasets")
            pass
            
        try: 
            FP = get_most_recent_file('/media/avs-47/', 'logFP___', '.dat')
            datas = get_last_row_as_list(FP)
            data = [float(item) for item in datas[1:]]
            event.create_bank("TEFP", midas.TID_FLOAT, data)
        except:
            self.client.msg("Error reading FP datasets")
            pass        
            
        try:
            AVS = get_most_recent_file('/media/avs-47/', 'LogAVS___', '.dat')
            datas = get_last_row_as_list(AVS)
            data = [float(item) for item in datas[1:]]
            event.create_bank("TAVS", midas.TID_FLOAT, data)
        except:
            self.client.msg("Error reading AVS datasets")
            pass       

        self.set_status("Running")
        return event

class MyFrontend(midas.frontend.FrontendBase):
    """
    A frontend contains a collection of equipment.
    You can access self.client to access the ODB etc (see `midas.client.MidasClient`).
    """
    def __init__(self):
        # You must call __init__ from the base class.
        midas.frontend.FrontendBase.__init__(self, "sc_frontend")
        
        # You can add equipment at any time before you call `run()`, but doing
        # it in __init__() seems logical.
        self.add_equipment(MyPeriodicEquipment(self.client))
        print(self.run_state)
        print(self._enabled_equipment())
        a = self._enabled_equipment()[0]
        print(a._is_active_for_state(self.run_state))
        
    # def begin_of_run(self, run_number):
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
        self.equipment['SCFrontend'].set_status("Stopped")
        print("Goodbye from user code!")
        
if __name__ == "__main__":
    # The main executable is very simple - just create the frontend object,
    # and call run() on it.
    with MyFrontend() as my_fe:
        my_fe.run()
