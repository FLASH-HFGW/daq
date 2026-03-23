#!/bin/sh

echo $1
if [ "$1" = "clean" ]; then
    rm -r /home/cold/daq/builddirs/build-csv-driver/*
fi;
cmake -B /home/cold/daq/builddirs/build-csv-driver/ -S /home/cold/daq/online/driver/sc_csv_driver/
cmake --build /home/cold/daq/builddirs/build-csv-driver/
cmake --install /home/cold/daq/builddirs/build-csv-driver/ --prefix /home/cold/daq/online/lib/
chmod a+x /home/cold/daq/online/lib/libcsvdev.so
