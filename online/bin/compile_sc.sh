#!/bin/sh

echo $1
if [ "$1" = "clean" ]; then
    rm -r /home/cold/daq/builddirs/build-sc/*
fi;
cmake -B /home/cold/daq/builddirs/build-sc/ -S /home/cold/daq/online/source/sc/
cmake --build /home/cold/daq/builddirs/build-sc/
cmake --install /home/cold/daq/builddirs/build-sc/ --prefix /home/cold/daq/online/bin/ 
