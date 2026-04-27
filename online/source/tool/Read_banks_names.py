'''
This simple code opens a mid.gz file and lists the bank names
'''

#! /usr/bin/env python3
import midas
import midas.file_reader


mf = midas.file_reader.MidasFile("../../data/run00247.mid.gz")
for mevent in mf:
    if mevent.header.is_midas_internal_event():
            continue
    else:
            keys = mevent.banks.keys()
    for iobj,key in enumerate(keys):
            print(key, mevent.header.event_id)