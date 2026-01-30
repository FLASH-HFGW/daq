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
#include <unistd.h>
#include <cstring>
#include "midas.h"
#include <ctime>
#include <fstream>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <chrono>

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

/*-- Globals -------------------------------------------------------*/

/* The frontend name (client name) as seen by other MIDAS clients   */
char *frontend_name = "cold_daq";
/* The frontend file name, don't change it */
char *frontend_file_name = __FILE__;

/* frontend_loop is called periodically if this variable is TRUE    */
BOOL frontend_call_loop = FALSE;

/* a frontend status page is displayed with this frequency in ms */
INT display_period = 3000;

/* maximum event size produced by this frontend */
INT max_event_size = 50000000; //1000000000;

/* maximum event size for fragmented events (EQ_FRAGMENTED) */
INT max_event_size_frag = 5 * 1024 * 1024;

/* buffer size to hold events */
INT event_buffer_size = 100000000; //2000000000


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
BOOL equipment_common_overwrite = TRUE;

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
int16* pDigiMem = NULL;

drv_handle  hCardDigi;
int32       lCardType, lSerialNumber, lFncType;
char        szErrorTextBuffer[ERRORTEXTLEN];
uint32      dwError;
int32       lStatus;
int32       lTrigCount = 0;
int64       llAvailUser, llPCPos;	//data
uint64      qwTotalMem = 0;
uint64      qwToTransfer =0;
/* Size of mirror buffer on the PC*/
int64       llBufferSize =	GIGA_B(1);
/* Size of chunck of data after which the card signals the data is available*/
int32       lNotifySize =	MEGA_B(32);
uint64      llLen = 0;
/* Sampling rate of card*/
int64       llSamplerate =  MEGA(5);

FILE* hFile = NULL;


/*-- Frontend Init -------------------------------------------------*/

INT frontend_init()
{
  /* put any hardware initialization here */

  hCardDigi = spcm_hOpen ("TCPIP::192.168.3.109::inst0::INSTR");
    if (!hCardDigi)
    {
        printf ("no card found...\n");
        return FE_ERR_HW;
    }

  // read card type name
  char acCardType[20] = {};
  spcm_dwGetParam_ptr (hCardDigi, SPC_PCITYP, acCardType, sizeof (acCardType));

  // read type, function and sn and check for A/D card
  spcm_dwGetParam_i32 (hCardDigi, SPC_PCITYP,         &lCardType);
  spcm_dwGetParam_i32 (hCardDigi, SPC_PCISERIALNO,    &lSerialNumber);
  spcm_dwGetParam_i32 (hCardDigi, SPC_FNCTYPE,        &lFncType);

  printf ("Found: %s sn %05d\n", acCardType, lSerialNumber);

  hFile = fopen ("fileDati.txt", "w");

  return SUCCESS;
}

/*-- Frontend Exit -------------------------------------------------*/

INT frontend_exit()
{
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

  /* put here clear scalers etc. */

  // do a simple standard setup
  spcm_dwSetParam_i32 (hCardDigi, SPC_CHENABLE,       255);              // channels enabled. 255=all channels
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP0,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP1,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP2,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP3,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP4,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP5,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP6,           5000);                  // max voltage amplitude
  spcm_dwSetParam_i32 (hCardDigi, SPC_AMP7,           5000);
  spcm_dwSetParam_i32 (hCardDigi, SPC_PRETRIGGER,     32);                  	// pretrigger data at start of FIFO mode
  spcm_dwSetParam_i32 (hCardDigi, SPC_CARDMODE,       SPC_REC_FIFO_SINGLE);   // single FIFO mode
  spcm_dwSetParam_i32 (hCardDigi, SPC_TIMEOUT,        100000);                  // timeout 5 s
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_ORMASK,     SPC_TMASK_EXT0);
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_EXT0_MODE,  SPC_TM_POS);            // trigger on positive edge
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_EXT0_LEVEL0,400);                  // trigger level in mV
  spcm_dwSetParam_i32 (hCardDigi, SPC_TRIG_ANDMASK,   0);                     // ...
  spcm_dwSetParam_i32 (hCardDigi, SPC_CLOCKMODE,      SPC_CM_EXTREFCLOCK);    // clock mode internal PLL
  spcm_dwSetParam_i32 (hCardDigi, SPC_REFERENCECLOCK,  10000000);              // external clock frequency
  spcm_dwSetParam_i32 (hCardDigi, SPC_CLOCKOUT,        0);                     // no clock output
  spcm_dwSetParam_i32 (hCardDigi, SPC_CLOCK_THRESHOLD, 1);                     // clock threshold, in mV


  spcm_dwSetParam_i64 (hCardDigi, SPC_SAMPLERATE, llSamplerate);


  spcm_dwSetParam_i32 (hCardDigi, SPC_M2CMD, M2CMD_CARD_WRITESETUP);

  pDigiMem = (int16*) pvAllocMemPageAligned ((uint64) llBufferSize);
  if (!pDigiMem)
  {
    printf ("memory allocation failed\n");
    spcm_vClose (hCardDigi);
    return FE_ERR_HW;
  }

  spcm_dwDefTransfer_i64 (hCardDigi, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, lNotifySize, pDigiMem, 0, llBufferSize);


  // start everything
	INT ret = StartAcq();
  
  return ret;
}

/*-- End of Run ----------------------------------------------------*/

INT end_of_run(INT run_number, char *error)
{
 return StopAcq();
 fclose(hFile);
}

/*-- Pause Run -----------------------------------------------------*/

INT pause_run(INT run_number, char *error)
{
  return StopAcq();
}

/*-- Resume Run ----------------------------------------------------*/

INT resume_run(INT run_number, char *error)
{
  return StartAcq();
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
    spcm_dwGetParam_i32 (hCardDigi, SPC_M2STATUS, &lStatus);

    if((lStatus >> 8 & 0x1))
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

  dwError = spcm_dwSetParam_i32 (hCardDigi, SPC_M2CMD, M2CMD_DATA_WAITDMA);

  return SUCCESS;
}

/*-- Event readout -------------------------------------------------*/

INT read_event(char *pevent, INT off)
{

  /* init bank structure */
  bk_init32(pevent);
  INT defaultEvSize = bk_size(pevent);

  WORD* pdata16 = NULL;
  bk_create(pevent, "SPEC", TID_WORD, (void**)&pdata16);

  spcm_dwGetParam_i64 (hCardDigi, SPC_DATA_AVAIL_USER_LEN,  &llAvailUser);
  spcm_dwGetParam_i64 (hCardDigi, SPC_DATA_AVAIL_USER_POS,  &llPCPos);

  llLen = lNotifySize;
  // we take care not to go across the end of the buffer, handling the wrap-around
  if ((llPCPos + llLen) >= llBufferSize) llLen = llBufferSize - llPCPos;

  fwrite( ((char*)pDigiMem)+llPCPos, llLen, 1, hFile);
  memcpy(pdata16,pDigiMem+llPCPos/2,llLen);

  // buffer is free for DMA transfer again
  spcm_dwSetParam_i32 (hCardDigi, SPC_DATA_AVAIL_CARD_LEN,  (int32)llLen);

 
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
    printf ("%s\n", szErrorTextBuffer);
    vFreeMemPageAligned (pDigiMem, (uint64) llBufferSize);
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
    printf ("%s\n", szErrorTextBuffer);
    vFreeMemPageAligned (pDigiMem, (uint64) llBufferSize);
    spcm_vClose (hCardDigi);
    return FE_ERR_HW;
  }
  return SUCCESS;
}