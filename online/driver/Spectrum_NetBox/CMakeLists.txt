cmake_minimum_required(VERSION 3.15)
project(spcm_ostools_linux)

add_compile_options(-Wall -O3)

#Add driver lib to path for compilation
link_directories("/home/cold/daq/online/driver/Spectrum_NetBox/")

add_library(spcm_ostools_linux SHARED /home/cold/daq/online/driver/Spectrum_NetBox/spcm_ostools_linux.cpp)
target_include_directories(spcm_ostools_linux PUBLIC
                          "/home/cold/daq/online/driver/Spectrum_NetBox/"
                          )
                                                    
target_link_libraries(spcm_ostools_linux z pthread)

install(TARGETS spcm_ostools_linux LIBRARY DESTINATION .)
