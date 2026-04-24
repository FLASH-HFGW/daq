/********************************************************************	\

  Name:         cold_fe.cxx
  Created by:   Giorgio Dho e Giovanni Mazzitelli

  Contents: Frontend program for Coldlab

  Data:     22/01/2026

\********************************************************************/

//Standard C++ includes
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <iostream>
#include <iomanip>
#include <unistd.h>
#include <cstring>
#include "midas.h"
#include <ctime>
#include <fstream>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <chrono>
#include <thread>


// ----- include standard driver header from library -----
#include "dlltyp.h"
#include "regs.h"
#include "spcerr.h"
#include "spcm_drv.h"

#include "spcm_oswrap.h"
#include "spcm_ostools.h"

using namespace std;

#define DEBUG false


/* make frontend functions callable from the C framework */

/*-- MIDAS Globals -------------------------------------------------------*/

/* The frontend name (client name) as seen by other MIDAS clients   */
char *frontend_name = (char*)"cold_daq";
/* The frontend file name, don't change it */
char *frontend_file_name = (char*)__FILE__;

/* frontend_loop is called periodically if this variable is TRUE    */
BOOL frontend_call_loop = FALSE;

/* a frontend status page is displayed with this frequency in ms */
INT display_period = 3000;

/* maximum event size produced by this frontend */
INT max_event_size = 50000000; //1000000000;

/* maximum event size for fragmented events (EQ_FRAGMENTED) */
INT max_event_size_frag = 40 * 1024 * 1024;

/* buffer size to hold events */
INT event_buffer_size = 100 * 1024 * 1024; //2000000000 

/* flag to create configuration ODB values. Use True to overwrite, otherwise the records are created only if not existing */
BOOL equipment_common_overwrite = FALSE; 

/* Handle for database. Use static so it is valid only in this file. No conflict with midas native handle*/
static HNDLE hDB;

/*Error variable*/
INT db_ret= DB_SUCCESS;

/*-- Function declarations -----------------------------------------*/

INT frontend_init();
INT frontend_exit();
INT begin_of_run(INT run_number, char *error);
INT end_of_run(INT run_number, char *error);
INT pause_run(INT run_number, char *error);
INT resume_run(INT run_number, char *error);
INT frontend_loop();

INT read_event(char *pevent, INT off);

INT poll_event(INT source, INT count, BOOL test);
INT interrupt_configure(INT cmd, INT source, POINTER_T adr);

/* Custom Routines */

INT StartAcq();
INT StopAcq();


/*-- Equipment list ------------------------------------------------*/

EQUIPMENT equipment[] = {

  {"NetBox",               /* equipment name */
   {1, 0,                   /* event ID, trigger mask */
    "SYSTEM",               /* event buffer */
    EQ_POLLED,              /* equipment type */
    0,                      /* event source */
    "MIDAS",                /* format */
    TRUE,                   /* enabled */
    RO_RUNNING              /* read only when running */
    //|
    //RO_ODB                /* and update ODB */
    ,
    300,                    /* poll for 300ms */
    0,                      /* stop run after this event limit */
    0,                      /* number of sub events */
    0,                      /* don't log history */
    "", "", "",},
   read_event,      /* readout routine */
  },

   {""}
};

/********************************************************************\
              Callback routines for system transitions

  These routines are called whenever a system transition like start/
  stop of a run occurs. The routines are called on the following
  occations:

  frontend_init:  When the frontend program is started. This routine
                  should initialize the hardware.

  frontend_exit:  When the frontend program is shut down. Can be used
                  to releas any locked resources like memory, commu-
                  nications ports etc.

  begin_of_run:   When a new run is started. Clear scalers, open
                  rungates, etc.

  end_of_run:     Called on a request to stop a run. Can send
                  end-of-run event and close run gates.

  pause_run:      When a run is paused. Should disable trigger events.

  resume_run:     When a run is resumed. Should enable trigger events.
\********************************************************************/

/* Global custom variable*/
/* Global pointer to digitizer memory address */
int16* pDigiMem = nullptr;

drv_handle  hCardDigi;
int32       g_CardType, g_SerialNumber, g_FncType;
char        szErrorTextBuffer[ERRORTEXTLEN];
uint32      dwError;
/* Bytes available by the PC after interrupt has fired and bit position in memory buffer of the beginning of unanalysed data*/
int64       g_AvailUser, g_PCPos;
/* Size of mirror buffer on the PC*/
int64       g_BufferSize_GB =	GIGA_B(1);    //default but will be changed in ODB
/* Size of chunck of data after which the card signals the data is available*/
int32       g_Notify_size_MB =	MEGA_B(16);   //Fixed here!
int64       g_Len = 0;
/* Sampling rate of card*/
int64       g_Sampling_rate_MS =  MEGA(5);    //default but will be changed in ODB

int32 g_transfered=0;
extern INT run_state;
int g_size = 0;


/*-- Frontend Init -------------------------------------------------*/

INT frontend_init()
{

  /*Attach to ODB */

  cm_get_experiment_database(&hDB, NULL);

  // Sets all the settings variables to default and create keys in the ODB only if not existing (if equipment_common_overwrite is false)
  db_create_record(hDB, 0, "Equipment/Netbox/Settings",
                   "VISA_Connection_string = STRING : [64] TCPIP::192.168.3.109::inst0::INSTR\n"
                   "Channels_enabled = INT : 255\n" 
                   "Channel_range_mV = INT[8]\n"
                   "\n"
                   "Pretrigger_channels = INT : 32\n"
                   "Timeout_ms = INT : 3000\n"
                   "Buffer_size_GB = INT64 : 1\n"
                   //"Notify_size_MB = INT : 16\n"
                   "Sampling_rate_MS = INT64 : 5\n"
                   );
  int setup_Channel_range_mV[8]={5000,5000,5000,5000,5000,5000,5000,5000};
  db_set_value(hDB,0,"Equipment/NetBox/Settings/Channel_range_mV",setup_Channel_range_mV, sizeof(setup_Channel_range_mV),8,TID_INT);
  

  /* put any hardware initialization here */

  char VISA_Connection_string[64];
  g_size = sizeof(VISA_Connection_string);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/VISA_Connection_string",VISA_Connection_string,&g_size,TID_STRING,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }
  hCardDigi = spcm_hOpen (VISA_Connection_string);
  if (!hCardDigi)  {cm_msg(MERROR,"Hardware","Error as no card was found..");     return FE_ERR_HW;}

  // read card type name
  char acCardType[20] = {};
  spcm_dwGetParam_ptr (hCardDigi, SPC_PCITYP, acCardType, sizeof (acCardType));

  // read type, function and sn and check for A/D card
  spcm_dwGetParam_i32 (hCardDigi, SPC_PCITYP,         &g_CardType);
  spcm_dwGetParam_i32 (hCardDigi, SPC_PCISERIALNO,    &g_SerialNumber);
  spcm_dwGetParam_i32 (hCardDigi, SPC_FNCTYPE,        &g_FncType);

  cm_msg(MINFO,"Hardware","Found: %s sn %05d\n", acCardType, g_SerialNumber);

  return SUCCESS;
}

/*-- Frontend Exit -------------------------------------------------*/

INT frontend_exit()
{
  if(pDigiMem != nullptr) vFreeMemPageAligned (pDigiMem, (uint64) g_BufferSize_GB);
  spcm_vClose (hCardDigi);
  return SUCCESS;

}

/*-- Begin of Run --------------------------------------------------*/

INT begin_of_run(INT run_number, char *error)
{

  if(DEBUG)
  {
	  ofstream myfile;
	  myfile.open("debug.txt");
	  myfile<<"START OF RUN"<<endl;
	  myfile.close();
  }

  int Channels_enabled;
  g_size = sizeof(Channels_enabled);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Channels_enabled",&Channels_enabled,&g_size,TID_INT,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }

  int Channel_range_mV[8];
  g_size = sizeof(Channel_range_mV);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Channel_range_mV",Channel_range_mV,&g_size,TID_INT,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }

  int Pretrigger_channels;
  g_size = sizeof(Pretrigger_channels);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Pretrigger_channels",&Pretrigger_channels,&g_size,TID_INT,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }

  int Timeout_ms;
  g_size = sizeof(Timeout_ms);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Timeout_ms",&Timeout_ms,&g_size,TID_INT,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }

  g_size = sizeof(g_BufferSize_GB);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Buffer_Size_GB",&g_BufferSize_GB,&g_size,TID_INT64,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }
  g_BufferSize_GB= GIGA_B(g_BufferSize_GB);

  /*g_size = sizeof(g_Notify_size_MB);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Notify_size_MB",&g_Notify_size_MB,&g_size,TID_INT,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }
  g_Notify_size_MB= MEGA_B(g_Notify_size_MB);*/

  g_size = sizeof(g_Sampling_rate_MS);
  db_ret = db_get_value(hDB, 0, "/Equipment/Netbox/Settings/Sampling_rate_MS",&g_Sampling_rate_MS,&g_size,TID_INT64,FALSE);
  if(db_ret != DB_SUCCESS)  {cm_msg(MERROR,"ODB","Error in get value ODB with error %s (meaning see midas.h)", cm_get_error(db_ret).c_str());   return FE_ERR_ODB;  }
  g_Sampling_rate_MS= MEGA(g_Sampling_rate_MS);

  // do a simple standard setup
  spcm_dwSetParam_i32 (hCardDigi, SPC_CHENABLE,       Channels_enabled);              // channels enabled. 255=all channels
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP0,           Channel_range_mV[0]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP1,           Channel_range_mV[1]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP2,           Channel_range_mV[2]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP3,           Channel_range_mV[3]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP4,           Channel_range_mV[4]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP5,           Channel_range_mV[5]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP6,           Channel_range_mV[6]);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP7,           Channel_range_mV[7]);
  spcm_dwSetParam_i32 (hCardDigi, SPC_PRETRIGGER,     Pretrigger_channels);                  	// pretrigger data at start of FIFO mode
  spcm_dwSetParam_i32 (hCardDigi, SPC_CARDMODE,       SPC_REC_FIFO_SINGLE);   // single FIFO mode
  spcm_dwSetParam_i32 (hCardDigi, SPC_TIMEOUT,        Timeout_ms);                  // timeout in ms
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_ORMASK,     SPC_TMASK_EXT0);
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_EXT0_MODE,  SPC_TM_POS);            // trigger on positive edge
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_EXT0_LEVEL0,400);                  // trigger level in mV
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_ANDMASK,   0);                     // ...
  /*spcm_dwSetParam_i32 (hCardDigi, SPC_CLOCKMODE,      SPC_CM_EXTREFCLOCK);    // clock mode internal PLL
  spcm_dwSetParam_i32 (hCardDigi, SPC_REFERENCECLOCK,  10000000);              // external clock frequency
  spcm_dwSetParam_i32 (hCardDigi, SPC_CLOCKOUT,        0);                     // no clock output
  spcm_dwSetParam_i32 (hCardDigi, SPC_CLOCK_THRESHOLD, 1);                     // clock threshold, in mV*/


  spcm_dwSetParam_i64 (hCardDigi, SPC_SAMPLERATE, g_Sampling_rate_MS);


  spcm_dwSetParam_i32 (hCardDigi, SPC_M2CMD, M2CMD_CARD_WRITESETUP);

  if(pDigiMem != nullptr) vFreeMemPageAligned (pDigiMem, (uint64) g_BufferSize_GB);

  pDigiMem = (int16*) pvAllocMemPageAligned ((uint64) g_BufferSize_GB);
  if (!pDigiMem)
  {
    cm_msg(MERROR,"Hardware","Error as memory allocation failed..");
    spcm_vClose (hCardDigi);
    return FE_ERR_HW;
  }

  spcm_dwDefTransfer_i64 (hCardDigi, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, g_Notify_size_MB, pDigiMem, 0, g_BufferSize_GB);

  g_transfered=0;
  // start everything

	INT ret = StartAcq();

  return ret;
}

/*-- End of Run ----------------------------------------------------*/

INT end_of_run(INT run_number, char *error)
{
 return StopAcq();
}

/*-- Pause Run -----------------------------------------------------*/

INT pause_run(INT run_number, char *error)
{
  cm_msg(MERROR,"Software","Error: Pause run not implemented");
  return FE_ERR_HW;
}

/*-- Resume Run ----------------------------------------------------*/

INT resume_run(INT run_number, char *error)
{
  cm_msg(MERROR,"Software","Error: Resume run not implemented");
  return FE_ERR_HW;
}

/*-- Frontend Loop -------------------------------------------------*/

INT frontend_loop()
{
  /* if frontend_call_loop is true, this routine gets called when
     the frontend is idle or once between every event */
  return SUCCESS;
}

/*------------------------------------------------------------------*/

/********************************************************************\

  Readout routines for different events

\********************************************************************/

/*-- Trigger event routines ----------------------------------------*/

INT poll_event(INT source, INT count, BOOL test)
/* Polling routine for events. Returns TRUE if event
   is available. If test equals TRUE, don't return. The test
   flag is used to time the polling */
{

  while(count--)
  {
    return TRUE;
  }

  return FALSE;

}

/*-- Interrupt configuration ---------------------------------------*/

INT interrupt_configure(INT cmd, INT source, POINTER_T adr)
{
  switch (cmd) {
  case CMD_INTERRUPT_ENABLE:
    break;
  case CMD_INTERRUPT_DISABLE:
    break;
  case CMD_INTERRUPT_ATTACH:
    break;
  case CMD_INTERRUPT_DETACH:
    break;
  }
  return SUCCESS;
}

/*-- Event readout -------------------------------------------------*/

INT read_event(char *pevent, INT off)
{
  dwError = spcm_dwSetParam_i32 (hCardDigi, SPC_M2CMD, M2CMD_DATA_WAITDMA);

  /* init bank structure */
  bk_init32(pevent);
  INT defaultEvSize = bk_size(pevent);
  WORD* pdata16 = NULL;
  bk_create(pevent, "SPEC", TID_WORD, (void**)&pdata16);

  spcm_dwGetParam_i64 (hCardDigi, SPC_DATA_AVAIL_USER_LEN,  &g_AvailUser);
  spcm_dwGetParam_i64 (hCardDigi, SPC_DATA_AVAIL_USER_POS,  &g_PCPos);

  g_Len = g_Notify_size_MB;

  // we take care not to go across the end of the buffer, handling the wrap-around
  if ((g_PCPos + g_Len) >= g_BufferSize_GB) g_Len = g_BufferSize_GB - g_PCPos;

  g_transfered+=g_Notify_size_MB/1024/1024;
  if(g_transfered%4096==0) cm_msg(MINFO,"Data","Data collected: %d MB",g_transfered);
  
  memcpy(pdata16,((char*)pDigiMem)+g_PCPos,g_Len);
  // buffer is free for DMA transfer again
  spcm_dwSetParam_i32 (hCardDigi, SPC_DATA_AVAIL_CARD_LEN,  (int32)g_Len);

  bk_close(pevent,(char*)pdata16+g_Len);


  //////MAYBE : Here checks if the header structure of the bank is as the initialisation done few lines above
  if (bk_size(pevent)==defaultEvSize ) { return 0; }
  return bk_size(pevent);

}

///////CUSTOM ROUTINES

INT StartAcq()
{
  dwError = spcm_dwSetParam_i32 (hCardDigi, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_DATA_STARTDMA);
  if (dwError != ERR_OK)
  {
    spcm_dwGetErrorInfo_i32 (hCardDigi, NULL, NULL, szErrorTextBuffer);
    //printf ("%s\n", szErrorTextBuffer);
    cm_msg(MERROR,"Hardware","Error at StartAcq: %s",szErrorTextBuffer);
    vFreeMemPageAligned (pDigiMem, (uint64) g_BufferSize_GB);
    spcm_vClose (hCardDigi);
    return FE_ERR_HW;
  }
  return SUCCESS;

}
INT StopAcq()
{
  dwError = spcm_dwSetParam_i32 (hCardDigi, SPC_M2CMD, M2CMD_CARD_STOP | M2CMD_DATA_STOPDMA);
  

  if (dwError != ERR_OK)
  {
    spcm_dwGetErrorInfo_i32 (hCardDigi, NULL, NULL, szErrorTextBuffer);
    //printf ("%s\n", szErrorTextBuffer);
    cm_msg(MERROR,"Hardware","Error: %s",szErrorTextBuffer);
    spcm_dwGetParam_i64 (hCardDigi, SPC_DATA_AVAIL_USER_LEN,  &g_AvailUser);
    spcm_dwSetParam_i32 (hCardDigi, SPC_DATA_AVAIL_CARD_LEN,  (int32)g_AvailUser);
    vFreeMemPageAligned (pDigiMem, (uint64) g_BufferSize_GB);
    spcm_vClose (hCardDigi);
    return FE_ERR_HW;
  }
  return SUCCESS;
}
