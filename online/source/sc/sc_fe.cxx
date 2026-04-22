/********************************************************************\

  Name:         sc_fe.cxx
  Created by:   Giorgio Dho and Giovanni Mazzitelli
  Date:         18/03/2026

  Contents:     Slow Control Frontend program.

  $Id$

\********************************************************************/

#include <stdio.h>
#include "midas.h"
#include "mfe.h"
#include "history.h"
//#include "class/hv.h"
#include "class/multi.h"
//#include "device/nulldev.h"
#include "csvdev.h"
#include "bus/null.h"

/*-- Globals -------------------------------------------------------*/

/* The frontend name (client name) as seen by other MIDAS clients   */
const char *frontend_name = "SC Frontend";
/* The frontend file name, don't change it */
const char *frontend_file_name = __FILE__;

/*-- Equipment list ------------------------------------------------*/

DEVICE_DRIVER multi_driver0[] = {
   {"Input0", csvdev, 13, null, DF_INPUT},
   //{"Output", nulldev, 2, null, DF_OUTPUT},
   {""}
};
DEVICE_DRIVER multi_driver1[] = {
   {"Input1", csvdev, 20, null, DF_INPUT},
   //{"Output", nulldev, 2, null, DF_OUTPUT},
   {""}
};
DEVICE_DRIVER multi_driver2[] = {
   {"Input2", csvdev, 25, null, DF_INPUT},
   //{"Output", nulldev, 2, null, DF_OUTPUT},
   {""}
};

BOOL equipment_common_overwrite = TRUE;

EQUIPMENT equipment[] = {

   {"Temp_Mercury",              /* equipment name */
    {10, 0,                     /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     200000,                     /* produce event every x msec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     200000,                         /* log history every second */
     "", "", ""} ,
    cd_multi_read,              /* readout routine */
    cd_multi,                   /* class driver main routine */
    multi_driver0,               /* device driver list */
    NULL,                       /* init string */
    },
    {"Temp_FP",              /* equipment name */
    {11, 0,                     /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     200000,                     /* produce event every x msec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     200000,                         /* log history every second */
     "", "", ""} ,
    cd_multi_read,              /* readout routine */
    cd_multi,                   /* class driver main routine */
    multi_driver1,               /* device driver list */
    NULL,                       /* init string */
    },
    {"Temp_AVS",              /* equipment name */
    {12, 0,                     /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     200000,                     /* produce event every x msec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     200000,                         /* log history every second */
     "", "", ""} ,
    cd_multi_read,              /* readout routine */
    cd_multi,                   /* class driver main routine */
    multi_driver2,               /* device driver list */
    NULL,                       /* init string */
    },

   {""}
};


/*-- Frontend Init -------------------------------------------------*/

INT frontend_init()
{
   //hs_define_panel("Environment", "Sines", {
   //                   "Environment/Input:Input Channel 0",
   //                   "Environment/Input:Input Channel 1"
   //                });

   return CM_SUCCESS;
}
