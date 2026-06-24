'''
This simple code opens a mid.gz file and lists the bank names
'''

#! /usr/bin/env python3
import midas
import midas.file_reader


mf = midas.file_reader.MidasFile("../../../../data/run00373.mid.gz")
for mevent in mf:
    if mevent.header.is_midas_internal_event():
            continue
    else:
            keys = mevent.banks.keys()
            print(keys, len(keys), mevent.header.serial_number)
    for iobj,key in enumerate(keys):
            print(key, mevent.header.event_id)
            if key=='TGPS':
                arr =mevent.banks[key].data
                time = ''.join(chr(x) for x in arr if x !=0)
                print('scrivo ',time)
