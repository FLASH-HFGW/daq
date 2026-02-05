#!/bin/sh

kill_daq.sh

odbedit -c clean

mhttpd -D
sleep 2
mlogger -D

echo Please point your web browser to http://localhost:8081
echo Or run: mozilla http://localhost:8081 &
echo To look at live histograms, run: roody -Hlocalhost

#end file
