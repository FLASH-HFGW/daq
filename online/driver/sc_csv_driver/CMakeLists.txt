cmake_minimum_required(VERSION 3.15)
project(spcm_ostools_linux)

add_compile_options(-Wall -O3)

#Find MIDAS
if(NOT TARGET midas::midas)
    find_package(Midas REQUIRED PATHS $ENV{MIDASSYS})
endif()

#Add driver lib to path for compilation
link_directories("/home/cold/daq/online/driver/sc_csv_driver/")

add_library(csvdev SHARED /home/cold/daq/online/driver/sc_csv_driver/csvdev.cxx)
target_include_directories(csvdev PUBLIC
                          "/home/cold/daq/online/driver/sc_csv_driver/"
                          )
                                                    
target_link_libraries(csvdev z midas::mfed midas::drivers)

install(TARGETS csvdev LIBRARY DESTINATION .)
