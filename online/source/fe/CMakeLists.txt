cmake_minimum_required(VERSION 3.5)
project(cold_fe)

add_compile_options(-Wall -O3)

#
# Find MIDAS
#

if (NO_MIDAS)
   message(STATUS "${PROJECT_NAME}: MIDAS support is disabled via NO_MIDAS")
   unset(MIDAS_FOUND)
elseif(TARGET midas)
   message(STATUS "${PROJECT_NAME}: Building as a subproject of MIDAS")
   set(MIDAS_FOUND true)
   set(MIDASSYS ${CMAKE_HOME_DIRECTORY})
elseif(DEFINED ENV{MIDASSYS})
   include($ENV{MIDASSYS}/lib/midas-targets.cmake)
   include($ENV{MIDASSYS}/lib/manalyzer-targets.cmake)
   message(STATUS "${PROJECT_NAME}: Building with MIDAS from $ENV{MIDASSYS}/lib/midas-targets.cmake")
   set(MIDAS_FOUND TRUE)
   set(MIDASSYS $ENV{MIDASSYS})
else()
   message(STATUS "${PROJECT_NAME}: Building without MIDAS")
   unset(MIDAS_FOUND)
endif()
#forse era più facile find_package(Midas REQUIRED PATHS $ENV{MIDASSYS})
message(STATUS "${PROJECT_NAME}: MIDASSYS: ${MIDASSYS}")

#Add driver lib to path for compilation
link_directories("/home/cold/daq/online/driver/Spectrum_NetBox/")

add_executable(cold_fe cold_fe.cxx)
target_include_directories(cold_fe PUBLIC "/home/cold/daq/online/driver/Spectrum_NetBox/")

# link against mfe.cxx and mfed.cxx frameworks
target_link_libraries(cold_fe midas::mfe z spcm_linux pthread rt)


install(TARGETS cold_fe DESTINATION .)