cmake_minimum_required(VERSION 3.5)
project(quax_fe)

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

# link against mfe.cxx and mfed.cxx frameworks
add_executable(quax_fe.exe quax_fe.cxx)

target_link_libraries(quax_fe.exe midas::mfe z spcm_linux pthread rt)


install(TARGETS quax_fe.exe DESTINATION .)