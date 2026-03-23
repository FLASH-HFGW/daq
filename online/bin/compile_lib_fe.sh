#!/bin/sh

echo $1
if [ "$1" = "clean" ]; then
    rm -r /home/cold/daq/builddirs/build-libostools/*
fi;
cmake -B /home/cold/daq/builddirs/build-libostools/ -S /home/cold/daq/online/driver/Spectrum_NetBox/
cmake --build /home/cold/daq/builddirs/build-libostools/
cmake --install /home/cold/daq/builddirs/build-libostools/ --prefix /home/cold/daq/online/lib/
chmod a+x /home/cold/daq/online/lib/libspcm_ostools_linux.so