#!/bin/sh

cmake -B /home/cold/daq/build-fe/ -S /home/cold/daq/online/source/fe/
cmake --build /home/cold/daq/build-fe/
cmake --install /home/cold/daq/build-fe/ --prefix /home/cold/daq/online/bin/ 
