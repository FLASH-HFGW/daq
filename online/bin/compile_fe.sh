#!/bin/sh

echo $1
if [ "$1" = "clean" ]; then
    rm -r /home/cold/daq/builddirs/build-fe/*
fi;
cmake -B /home/cold/daq/builddirs/build-fe/ -S /home/cold/daq/online/source/fe/
cmake --build /home/cold/daq/builddirs/build-fe/
cmake --install /home/cold/daq/builddirs/build-fe/ --prefix /home/cold/daq/online/bin/ 
