/********************************************************************\

  Name:         scfe.c
  Created by:   Francesco Renga

  Contentes: Slow Control Frontend program for CYGNUS_RD

  $Id$

\********************************************************************/

#include <stdio.h>
#include "midas.h"
#include "mfe.h"
#include "mscb.h"
#include "device/mscbdev.h"
#include "class/hv.h"
#include "class/multi.h"
#include "class/generic.h"
#include "gem_hv.h"
#include "gem_dd_sy4527.h"
#include "iseg_hps.h"
#include "opc.h"
#include "arduino_motor.h"
#include "bus/null.h"

using namespace std;

/*-- Globals -------------------------------------------------------*/

/* The frontend name (client name) as seen by other MIDAS clients   */
const char *frontend_name = "SC Frontend";
/* The frontend file name, don't change it */
const char *frontend_file_name = __FILE__;

/* frontend_loop is called periodically if this variable is TRUE    */
BOOL frontend_call_loop = FALSE;

/* a frontend status page is displayed with this frequency in ms    */
INT display_period = 1000;

/* maximum event size produced by this frontend */
INT max_event_size = 10000;

/* maximum event size for fragmented events (EQ_FRAGMENTED) */
INT max_event_size_frag = 5 * 1024 * 1024;

/* buffer size to hold events */
INT event_buffer_size = 10 * 10000;

/*-- Equipment list ------------------------------------------------*/

/* device driver list */
DEVICE_DRIVER sy4527_driver[] = {
  {"sy4527", dd_sy4527, 26, null, DF_PRIO_DEVICE|DF_REPORT_CHSTATE|DF_REPORT_STATUS|DF_HW_RAMP},
  {""}
};

DEVICE_DRIVER iseg_hps_driver[] = {
  {"iseg_hps", iseg_hps, 1, null, DF_PRIO_DEVICE|DF_REPORT_CHSTATE|DF_REPORT_STATUS|DF_HW_RAMP},
  {""}
};

DEVICE_DRIVER environment_driver[] = {
  {"Input", mscbdev, 0, null, DF_INPUT | DF_MULTITHREAD},
  {"Output", mscbdev, 0, null, DF_OUTPUT | DF_PRIO_DEVICE | DF_MULTITHREAD},
  {""}
};

DEVICE_DRIVER gassystem_driver[] = {
  {"gassystem", opc, 323, null, DF_PRIO_DEVICE },
  {""}
};

DEVICE_DRIVER sourcemotor_driver[] = {
  {"Input", arduino_motor, 1, null, DF_INPUT | DF_MULTITHREAD },
  {"Output", arduino_motor, 1, null, DF_OUTPUT | DF_MULTITHREAD },
  {""}
};


BOOL equipment_common_overwrite = TRUE;

EQUIPMENT equipment[] = {

   {"HV",                       /* equipment name */
    {3, 0,                       /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     60000,                     /* read every 60 sec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     1,                         /* log history every event */
     "", "", ""} ,
    cd_gem_hv_read,                 /* readout routine */
    cd_gem_hv,                      /* class driver main routine */
    sy4527_driver,                  /* device driver list */
    NULL,                       /* init string */
    },

   {"CATHODE",                       /* equipment name */
    {4, 0,                       /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     60000,                     /* read every 60 sec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     1,                         /* log history every event */
     "", "", ""} ,
    cd_hv_read,                 /* readout routine */
    cd_hv,                      /* class driver main routine */
    iseg_hps_driver,                  /* device driver list */
    NULL,                       /* init string */
   },

   {"Environment",                       /* equipment name */
    {5, 0,                       /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     60000,                     /* read every 60 sec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     1,                         /* log history every event */
     "", "", ""} ,
    cd_multi_read,                 /* readout routine */
    cd_multi,                      /* class driver main routine */
    environment_driver,                  /* device driver list */
    NULL,                       /* init string */
   },

   {"GasSystem",                       /* equipment name */
    {6, 0,                       /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     60000,                     /* read every 60 sec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     1,                         /* log history every event */
     "", "", ""} ,
    cd_gen_read,                 /* readout routine */
    cd_gen,                      /* class driver main routine */
    gassystem_driver,                  /* device driver list */
    NULL,                       /* init string */
   },

   {"SourceMotor",                       /* equipment name */
    {9, 0,                       /* event ID, trigger mask */
     "SYSTEM",                  /* event buffer */
     EQ_SLOW,                   /* equipment type */
     0,                         /* event source */
     "MIDAS",                   /* format */
     TRUE,                      /* enabled */
     RO_ALWAYS,        /* read when running and on transitions */
     60000,                     /* read every 60 sec */
     0,                         /* stop run after this event limit */
     0,                         /* number of sub events */
     1,                         /* log history every event */
     "", "", ""} ,
    cd_multi_read,                 /* readout routine */
    cd_multi,                      /* class driver main routine */
    sourcemotor_driver,
    NULL,
   },

   {""}
   
};


/*-- Dummy routines ------------------------------------------------*/

INT poll_event(INT source, INT count, BOOL test)
{
   return 1;
};
INT interrupt_configure(INT cmd, INT source, POINTER_T adr)
{
   return 1;
};

void mscb_define(const char *submaster, const char *equipment, const char *devname, DEVICE_DRIVER *driver, int address,
                 unsigned char var_index, const char *name, double threshold) {
   int i, dev_index, chn_index, chn_total;
   std::string str;
   float f_threshold;
   HNDLE hDB;

   cm_get_experiment_database(&hDB, NULL);

   /*
   if (submaster && submaster[0]) {
      str = msprintf("/Equipment/%s/Settings/Devices/%s/MSCB Device", equipment, devname);
      db_set_value(hDB, 0, str.c_str(), submaster, 32, 1, TID_STRING);
      str = msprintf("/Equipment/%s/Settings/Devices/%s/MSCB Pwd", equipment, devname);
      db_set_value(hDB, 0, str.c_str(), "meg", 32, 1, TID_STRING);
   }
   */
   
   /* find device in device driver */
   for (dev_index = 0; driver[dev_index].name[0]; dev_index++)
      if (equal_ustring(driver[dev_index].name, devname))
         break;

   if (!driver[dev_index].name[0]) {
      cm_msg(MERROR, "mscb_define", "Device \"%s\" not present in device driver list", devname);
      return;
   }

   /* count total number of channels */
   for (i = chn_total = 0; i <= dev_index; i++)
      chn_total += driver[i].channels;

   chn_index = driver[dev_index].channels;
   str = msprintf("/Equipment/%s/Settings/Devices/%s/MSCB Address", equipment, devname);
   db_set_value_index(hDB, 0, str.c_str(), &address, sizeof(int), chn_index, TID_INT32, TRUE);
   str = msprintf("/Equipment/%s/Settings/Devices/%s/MSCB Index", equipment, devname);
   db_set_value_index(hDB, 0, str.c_str(), &var_index, sizeof(char), chn_index, TID_UINT8, TRUE);

   if (threshold != -1) {
      str = msprintf("/Equipment/%s/Settings/Update Threshold", equipment);
      f_threshold = (float) threshold;
      db_set_value_index(hDB, 0, str.c_str(), &f_threshold, sizeof(float), chn_total, TID_FLOAT, TRUE);
   }

   if (name && name[0]) {
      str = msprintf("/Equipment/%s/Settings/Names %s", equipment, devname);
      db_set_value_index(hDB, 0, str.c_str(), name, 32, chn_total, TID_STRING, TRUE);
   }

   /* increment number of channels for this driver */
   driver[dev_index].channels++;
}

/*-- Error dispatcher causing communiction alarm -------------------*/

void scfe_error(const char *error) {
   char str[256];

   strlcpy(str, error, sizeof(str));
   cm_msg(MERROR, "scfe_error", "%s", str);
   al_trigger_alarm("MSCB", str, "MSCB Alarm", "Communication Problem", AT_INTERNAL);
}

/*-- Frontend Init -------------------------------------------------*/

INT frontend_init()
{

  int i=0;
  std::string str;
  float val = -1;
  HNDLE hDB;

  for(i=0;i<24;i++){
    mscb_define("mscb399","Environment","Input",environment_driver,0xFFFF,i, NULL, -1);
  }
  for(i=0;i<0;i++){
    mscb_define("mscb399","Environment","Output",environment_driver,0XFFFF,i, NULL, -1);
  }

  cm_get_experiment_database(&hDB, NULL);

  db_set_value_index(hDB, 0, "/Equipment/SourceMotor/Variables/Output", &val, sizeof(float), 0, TID_FLOAT, TRUE);

  return CM_SUCCESS;

}

/*-- Frontend Exit -------------------------------------------------*/

INT frontend_exit()
{
   return CM_SUCCESS;
}

/*-- Frontend Loop -------------------------------------------------*/

INT frontend_loop()
{
   return CM_SUCCESS;
}

/*-- Begin of Run --------------------------------------------------*/

INT begin_of_run(INT run_number, char *error)
{
   return CM_SUCCESS;
}

/*-- End of Run ----------------------------------------------------*/

INT end_of_run(INT run_number, char *error)
{
   return CM_SUCCESS;
}

/*-- Pause Run -----------------------------------------------------*/

INT pause_run(INT run_number, char *error)
{
   return CM_SUCCESS;
}

/*-- Resume Run ----------------------------------------------------*/

INT resume_run(INT run_number, char *error)
{
   return CM_SUCCESS;
}

/*------------------------------------------------------------------*/
