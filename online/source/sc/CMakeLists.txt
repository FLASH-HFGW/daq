cmake_minimum_required(VERSION 3.14)
project(sc_fe)

add_compile_options(-Wall -O3)

if(NOT TARGET midas::midas)
    find_package(Midas REQUIRED PATHS $ENV{MIDASSYS})
endif()

#Add driver lib to path for compilation
link_directories("/home/cold/daq/online/lib/")

add_executable(sc_fe sc_fe.cxx)
target_include_directories(sc_fe PUBLIC "/home/cold/daq/online/driver/sc_csv_driver/")
target_link_libraries(sc_fe csvdev midas::mfed midas::drivers)


install(TARGETS sc_fe DESTINATION .)