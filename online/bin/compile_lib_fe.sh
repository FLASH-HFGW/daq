#!/bin/sh

echo $1
if [ "$1" = "clean" ]; then
    rm -r /home/cold/daq/build-libostools/*
fi;
cmake -B /home/cold/daq/build-libostools/ -S /home/cold/daq/online/driver/Spectrum_NetBox/
cmake --build /home/cold/daq/build-libostools/
sudo cmake --install /home/cold/daq/build-libostools/ --prefix /usr/lib/x86_64-linux-gnu/
sudo chmod a+x /usr/lib/x86_64-linux-gnu/libspcm_ostools_linux.so
