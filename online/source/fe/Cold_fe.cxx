/********************************************************************	\

  Name:         cold_fe.cxx
  Created by:   Francesco Renga and co

  Contents: Frontend program for CYGNUS_RD

  Data:     28/10/2025

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
#include "../c_header/dlltyp.h"
#include "../c_header/regs.h"
#include "../c_header/spcerr.h"
#include "../c_header/spcm_drv.h"

#include "../common/ostools/spcm_oswrap.h"
#include "../common/ostools/spcm_ostools.h"

using namespace std;

#define DEBUG false

#define HAVE_CAEN_BRD

#ifdef HAVE_CAEN_BRD
  #define HAVE_CAEN_DGTZ
  #ifdef HAVE_CAEN_DGTZ
    #define HAVE_V1742
  #endif
#endif

#ifdef HAVE_CAEN_BRD
#include <CAENVMElib.h>
#endif
#ifdef HAVE_CAEN_DGTZ
  #include "CAENDigitizer.h"
#endif


/* make frontend functions callable from the C framework */

/*-- Globals -------------------------------------------------------*/

/* The frontend name (client name) as seen by other MIDAS clients   */
char *frontend_name = "cold_mnv_daq";
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

INT init_vme_modules();
INT ConfigBridge();
INT ConfigDgtz();
INT ConfigDisc();
INT disable_trigger();
INT enable_trigger();
INT ClearDevice();
INT read_tdc(char *pevent);
INT read_dgtz(char *pevent);
void ReadDgtzConfig();
void Free_arrays();

#ifdef HAVE_CAEN_DGTZ
  #define MAX_BASE_INPUT_FILE_LENGTH 1000

  int SaveCorrectionTables(char *outputFileName, uint32_t groupMask, CAEN_DGTZ_DRS4Correction_t *tables);
#endif


/*-- Equipment list ------------------------------------------------*/
BOOL equipment_common_overwrite = TRUE;

EQUIPMENT equipment[] = {

  {"Trigger",               /* equipment name */
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
    100,                    /* poll for 100ms */
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
#ifdef HAVE_CAEN_BRD
int32_t gVme = 0;
//char ip[20] = "192.168.99.105";


int gDisBase   = 0xEE000000;    //Set correct address
int gTdcBase   = 0x33330000;    //Set correct address
#endif

#ifdef HAVE_CAEN_DGTZ
int nboard = 1;
int *gDGTZ;
char **buffer_dgtz;
int *posttrg;   //=  70;

char ip[20];
double **DGTZ_OFFSET;
uint32_t *NCHDGTZ;        
uint32_t *ndgtz;          //= 1024 or 5000 for the slow;
uint32_t *SAMPLING;    //250;
uint32_t *gDigBase;     //0x22220000;
uint32_t *gDigLink;     //1
char **BoardName;
#endif

int rec_ev = 0;

/*-- Frontend Init -------------------------------------------------*/

INT frontend_init()
{
  /* put any hardware initialization here */


//#ifdef HAVE_BOARD
//  ReadBoardConfig();    //Read from ODB configuration
//#endif

#ifdef HAVE_CAEN_BRD

int size = sizeof(ip);
  HNDLE hDB;
  cm_get_experiment_database(&hDB, NULL);
  db_get_value(hDB, 0, "/Configurations/Bridge_IPAddr",ip,&size,TID_STRING,TRUE);

#ifdef HAVE_CAEN_DGTZ
  ReadDgtzConfig();
#endif
  
  int ret = CAENVME_Init2(cvETH_V4718_LOCAL, ip, 0, &gVme);

   if (ret != cvSuccess)
   {

        printf("Error at init\n");

        return ret;
   }


  //mvme_set_am(gVme, MVME_AM_A24_ND);  //////////////////////Da modificare new_bridge

  printf("gVme %d ret %d\n",gVme,ret);

  init_vme_modules();

#endif

  disable_trigger();


  return SUCCESS;
}

/*-- Frontend Exit -------------------------------------------------*/

INT frontend_exit()
{

  disable_trigger();

#ifdef HAVE_CAEN_DGTZ
  Free_arrays();
#endif

  return SUCCESS;

}

/*-- Begin of Run --------------------------------------------------*/

INT begin_of_run(INT run_number, char *error)
{
  rec_ev = 0;

  if(DEBUG) {
	  ofstream myfile;
	  myfile.open("debug.txt");
	  myfile<<"START OF RUN"<<endl;
	  myfile.close();
  }

  /* put here clear scalers etc. */
#ifdef HAVE_CAEN_BRD

  ConfigBridge();   
  //TO BE CHECKED FOR V3718
  CAENVME_StartPulser(gVme,cvPulserA);    //////////////////////Da modificare new_bridge

  //WRONG FOR V3718
  ////Set LED off
  CAENVME_ClearOutputRegister(gVme,cvOut3Bit);    //////////////////////Da modificare new_bridge

#ifdef HAVE_CAEN_DGTZ
  ConfigDgtz();
#endif


#endif

  enable_trigger();

  return SUCCESS;
}

/*-- End of Run ----------------------------------------------------*/

INT end_of_run(INT run_number, char *error)
{

  disable_trigger();

#ifdef HAVE_CAEN_BRD
  //WRONG FOR V3718
  CAENVME_StopPulser(gVme,cvPulserA);     //////////////////////Da modificare new_bridge
#endif

 return SUCCESS;

}

/*-- Pause Run -----------------------------------------------------*/

INT pause_run(INT run_number, char *error)
{

  disable_trigger();

  return SUCCESS;
}

/*-- Resume Run ----------------------------------------------------*/

INT resume_run(INT run_number, char *error)
{

  enable_trigger();

  return SUCCESS;
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

  int i;
  DWORD flag;

  int lamTDC = 1;
  int lamDGTZ = 1;


  for (i = 0; i < count; i++) {

    /*
#ifdef HAVE_CAEN_BRD
    //////////////////////Sync test//////////////////
    if(rec_ev == 4){
      //Switch LED on through OUT_3
      //WRONG FOR V3718
      CAENVME_SetOutputRegister(gVme,cvOut3Bit|cvOut1Bit);
      sleep(1);
    }
    else if(rec_ev == 5){
      //Switch LED off through OUT_3
      //WRONG FOR V3718
      CAENVME_ClearOutputRegister(gVme,cvOut3Bit);
      sleep(1);
    }
#endif
    */

#ifdef HAVE_CAEN_DGTZ

    vector<uint32_t> st(nboard);
      uint32_t status;
      for(int jj=0;jj<nboard;jj++){
	CAEN_DGTZ_ErrorCode ret = CAEN_DGTZ_ReadRegister(gDGTZ[jj],CAEN_DGTZ_ACQ_STATUS_ADD,&status); /* read status register */
	st[jj] = status;
	lamDGTZ &= ((status & 0x8)>>3); /* 4th bit is data ready */
      }
#endif

    flag = (lamTDC && lamDGTZ);

    if (flag){
      if (!test){

#ifdef HAVE_CAEN_BRD
	//SET OUT_1 to 0 (busy)
	//WRONG FOR V3718
	CAENVME_ClearOutputRegister(gVme,cvOut1Bit);    //////////////////////Da modificare new_bridge
#endif

	return TRUE;

      }

    }

//#ifdef HAVE_CAEN_BRD
//
//    //Reset GATE (pulser B)
//    //WRONG FOR V3718
//    CAENVME_StopPulser(gVme,cvPulserB);   //////////////////////Da modificare new_bridge

//#endif

  }

  return 0;

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

  rec_ev++;

  /* init bank structure */
  bk_init32(pevent);
  INT defaultEvSize = bk_size(pevent);

  //////READ SYSTEMS

#ifdef HAVE_CAEN_BRD

#ifdef HAVE_CAEN_DGTZ
  read_dgtz(pevent);
#endif

#endif

  //////MAYBE : Here checks if the header structure of the bank is as the initialisation done few lines above
  if (bk_size(pevent)==defaultEvSize ) { return 0; }
  return bk_size(pevent);

}

///////CUSTOM ROUTINES

#ifdef HAVE_CAEN_DGTZ
void ReadDgtzConfig(){

  CAEN_DGTZ_ErrorCode ret;
  HNDLE hDB;

  cm_get_experiment_database(&hDB, NULL);

  /////Number of boards
  int size = sizeof(int);
  db_get_value(hDB, 0, "/Configurations/Number of Digitizers",&nboard,&size,TID_INT,TRUE);

  gDGTZ = new int[nboard];          //handle of digitizer
  gDigBase = new uint32_t[nboard];     //logic address on the crate ... like 0x22220000;
  gDigLink = new uint32_t[nboard];     //logic link (depends on USB port or etherne... like 1;
  BoardName = new char*[nboard];    //Name of the board
  buffer_dgtz = new char*[nboard];    //buffer of digitizer (mostly null pointers which will be loaded with data by the readout function)
  NCHDGTZ = new uint32_t[nboard];        // number of input channels of the digitizer. The V1742 has 32 but the firmware of the board when asked will return 4 as the board has 4 groups each of 8 channels;
  DGTZ_OFFSET = new double*[nboard];  //offset of the digitizer which defines the middle of the range of 1 V of dynamic range
  /////Number of samples per waveform and sampling rate
  ndgtz = new uint32_t[nboard];          //Number of samples per waveform.. like 1024;
  SAMPLING = new uint32_t[nboard] ;    //Sampling rate... like 250;
  /////Horizontal offset
  posttrg = new int[nboard];   //Post trigger value. It depends on the board. For V1742 it is a percentage of the waveform;

  //read from the database and initialise gDigBase
  for(int i=0;i<nboard;i++){

    /////Open the board
    char query[100];
    sprintf(query,"/Configurations/Digitizer Base Address[%d]",i);
    db_get_value(hDB, 0, query,&gDigBase[i],&size,TID_INT,TRUE);
    sprintf(query,"/Configurations/Digitizer Link Number[%d]",i);
    db_get_value(hDB, 0, query,&gDigLink[i],&size,TID_INT,TRUE);
    CAEN_DGTZ_ErrorCode ret = CAEN_DGTZ_OpenDigitizer2(CAEN_DGTZ_ETH_V4718,(void*)ip,0,gDigBase[i],&gDGTZ[i]);
    if(ret != CAEN_DGTZ_Success) {
      printf("Can't open digitizer, board number %d %d\n-- Error %d\n",i,gDigBase[i],ret);
    }

    ////Board name
    CAEN_DGTZ_BoardInfo_t BoardInfo;
    CAEN_DGTZ_GetInfo(gDGTZ[i], &BoardInfo);
    BoardName[i] = new char[10];
    strcpy(BoardName[i],BoardInfo.ModelName);
    printf("%s\n",BoardName[i]);

    ////Buffer preparation
    buffer_dgtz[i]=NULL;

    ////Number of channels
    NCHDGTZ[i] = BoardInfo.Channels;
    if(strcmp(BoardName[i],"V1742")==0)
      NCHDGTZ[i] *= 8;

    ////Vertical Offsets
    DGTZ_OFFSET[i]=new double[32];
    for(int j=0;j<32;j++) DGTZ_OFFSET[i][j]=0.;

  }

}
#endif

#ifdef HAVE_CAEN_BRD

INT init_vme_modules(){

  /* BRIDGE INITIALIZATION */
  unsigned int data;

  //SET POSITIVE POLARITIES OF LEDS AND SIGNALS
  //TO BE CHECKED FOR V3718
  data = 0x7F;
  CAENVME_WriteRegister(gVme,cvLedPolRegClear,data);    //////////////////////Da modificare new_bridge
  //WRONG FOR V3718
  data = 0x3E0;
  CAENVME_WriteRegister(gVme,cvOutMuxRegClear,data);    //////////////////////Da modificare new_bridge

  //USE OUT_1 as VME VETO and OUT_3 as LED driver
  //data = 0xCC;
  //CAENVME_WriteRegister(gVme,cvOutMuxRegSet,data);

  //TO BE CHECKED FOR V3718
  //Set OUT_0 as pulser A for periodic trigger to the camera
  CAENVME_SetOutputConf(gVme,cvOutput0,cvDirect,cvActiveHigh,cvMiscSignals);    //////////////////////Da modificare new_bridge

  //TO BE CHECKED FOR V3718
  //Set OUT_2 as pulser B for a single gate
  CAENVME_SetOutputConf(gVme,cvOutput2,cvInverted,cvActiveHigh,cvMiscSignals);    //////////////////////Da modificare new_bridge

  //WRONG FOR V3718
  //USE OUT_1 as VME VETO
  data = 0xC;
  CAENVME_WriteRegister(gVme,cvOutMuxRegSet,data);        //////////////////////Da modificare new_bridge
  data = 0xC0;
  CAENVME_WriteRegister(gVme,cvOutMuxRegSet,data);        //////////////////////Da modificare new_bridge

  ConfigBridge();


#ifdef HAVE_CAEN_DGTZ

  /* DIGITIZER INITIALIZATION */

  CAEN_DGTZ_BoardInfo_t *BoardInfo= new CAEN_DGTZ_BoardInfo_t[nboard] ;
  CAEN_DGTZ_ErrorCode ret;

  for(int i=0;i<nboard;i++)
    {
      ret = CAEN_DGTZ_GetInfo(gDGTZ[i], &BoardInfo[i]);

      printf("\nConnected to CAEN Digitizer Model %s %d -- %d channels\n", BoardInfo[i].ModelName,BoardInfo[i].FamilyCode,NCHDGTZ[i]);

      if(NCHDGTZ[i] > 32) {
	      printf("Error in NCHDGTZ %d\n",NCHDGTZ[i]);
	      exit(EXIT_FAILURE);
      }

      ////Reset the board
      ret = CAEN_DGTZ_Reset(gDGTZ[i]);                                               /* Reset Digitizer */
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer Reset, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer Reset, board number %d.", i);
      }
      ret = CAEN_DGTZ_ClearData(gDGTZ[i]);
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer ClearData, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer ClearData, board number %d.", i);
      }

      ////Waveform Setup
      if(strcmp(BoardName[i],"V1742")==0)
	          CAEN_DGTZ_SetGroupEnableMask(gDGTZ[i],0xF);

      ret = CAEN_DGTZ_SetSWTriggerMode(gDGTZ[i],CAEN_DGTZ_TRGMODE_DISABLED);
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer TriggerMode, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer TriggerMode, board number %d.", i);
      }
      ret = CAEN_DGTZ_SetExtTriggerInputMode(gDGTZ[i],CAEN_DGTZ_TRGMODE_ACQ_ONLY);
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer TriggerInputMode, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer TriggerInputMode, board number %d.", i);
      }
      ret = CAEN_DGTZ_SetMaxNumEventsBLT(gDGTZ[i],256);//128);                                /* Set the max number of events to transfer in a sigle readout */
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer SetMaxNumEventsBLT, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer SetMaxNumEventsBLT, board number %d.", i);
      }

      //Acquisition mode
      ret = CAEN_DGTZ_SetAcquisitionMode(gDGTZ[i],CAEN_DGTZ_SW_CONTROLLED);          /* Set the acquisition mode */

      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer SetAcquisitionMode, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer SetAcquisitionMode, board number %d.", i);
      }

    }
 ConfigDgtz();

 delete[] BoardInfo;
#endif

  return SUCCESS;

}

#endif

#ifdef HAVE_CAEN_BRD
INT ConfigBridge(){

  //TO BE CHECKD FOR V3718
  //Configure pulser A for camera trigger
  //---Start and reset from SW
  CVTimeUnits unit = cvUnit410us;
  DWORD period = 100000/410; //in units of 410 us
  DWORD width = 10; //in units of 410 us

  CAENVME_SetPulserConf(gVme,cvPulserA,period,width,unit,0,cvManualSW,cvManualSW);    //////////////////////Da modificare new_bridge

  //TO BE CHECKD FOR V3718
  //Configure pulser B for a single gate
  //---Start from IN_0, reset from SW, infinite length
  unit = cvUnit25ns;
  period = 100; //in units of 104 ms
  width = 255; //in units of 104 ms
  CAENVME_SetPulserConf(gVme,cvPulserB,period,width,unit,0,cvInputSrc0,cvManualSW);     //////////////////////Da modificare new_bridge

  return SUCCESS;

}
#endif

#ifdef HAVE_CAEN_DGTZ
INT ConfigDgtz(){

  cout<<"STo configurando\n";
  int size = sizeof(int);

  HNDLE hDB;
  char query[64];
  int  maxtriggersize;
  cm_get_experiment_database(&hDB, NULL);

  db_get_value(hDB, 0,"/Configurations/MultiTriggerMaxSize",&maxtriggersize,&size,TID_INT,TRUE);

  for(int i=0;i<nboard;i++){

    CAEN_DGTZ_ErrorCode ret = CAEN_DGTZ_Success;

    sprintf(query,"/Configurations/DigitizerSamples[%d]",i);
    db_get_value(hDB, 0, query,&ndgtz[i],&size,TID_INT,TRUE);

    CAEN_DGTZ_DRS4Frequency_t DRS4Frequency = CAEN_DGTZ_DRS4_5GHz;

   if(strcmp(BoardName[i],"V1742")==0)
    {
      ndgtz[i] = 1024;
      int fsampling = 0;
      sprintf(query,"/Configurations/SamplingFrequency[%d]",i);
      db_get_value(hDB, 0, query,&fsampling,&size,TID_INT,TRUE);
      switch(fsampling)
      {
        case 750:
          SAMPLING[i] = (int)((1000.0/750.0)*1000.0);
                  DRS4Frequency=CAEN_DGTZ_DRS4_750MHz;
                  break;
        case 1000:
          SAMPLING[i] = (int)1000;
          DRS4Frequency=CAEN_DGTZ_DRS4_1GHz;
          break;
        case 2500:
          SAMPLING[i] = (int)400;
          DRS4Frequency=CAEN_DGTZ_DRS4_2_5GHz;
          break;
        case 5000:
          SAMPLING[i] = (int)200;
          DRS4Frequency=CAEN_DGTZ_DRS4_5GHz;
          break;
        default:
          SAMPLING[i] = (int)200;
          printf("You should set the sampling frequency is MS/s. Allowed values are 750 1000 2500 5000.\n Now set to 750 MS/s.\n");
          cm_msg(MERROR, "cupid_daq", "You should set the sampling frequency is MS/s. Allowed values are 750 1000 2500 5000. Now set to 5000 MS/s.");
          DRS4Frequency=CAEN_DGTZ_DRS4_5GHz;
          break;
	    }   
	    ret = CAEN_DGTZ_SetDRS4SamplingFrequency(gDGTZ[i],DRS4Frequency);
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer SetDRS4SamplingFrequency, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer SetDRS4SamplingFrequency, board number %d.", i);
      }
    }

    sprintf(query,"/Configurations/DigitizerPostTrg[%d]",i);
    db_get_value(hDB, 0, query,&posttrg[i],&size,TID_INT,TRUE);
    ret = CAEN_DGTZ_SetPostTriggerSize(gDGTZ[i],posttrg[i]);                               /* Trigger position */
    if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer SetPostTriggerSize, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer SetPostTriggerSize, board number %d.", i);
      }

    size = sizeof(double);
    for(int ich=0;ich<NCHDGTZ[i];ich++){

      sprintf(query,"/Configurations/DigitizerOffset[%d]",i*32+ich);
      db_get_value(hDB,0,query,&DGTZ_OFFSET[i][ich],&size,TID_DOUBLE,TRUE);

      if(DGTZ_OFFSET[i][ich] > 0.5) DGTZ_OFFSET[i][ich] = 0.5;
      else if(DGTZ_OFFSET[i][ich] < -0.5) DGTZ_OFFSET[i][ich] = -0.5;

      
      if(strcmp(BoardName[i],"V1742")==0){   
      int grreg = 0x1098 | (ich/8 << 8);
      int data = (ich%8<<16) | (int)(DGTZ_OFFSET[i][ich]/2.*65536 + 32767);
      ret = CAEN_DGTZ_WriteRegister(gDGTZ[i],grreg,data);
      if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer WriteRegister, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer WriteRegister, board number %d.", i);
      }

      }
    }

    //Uploading and enabling the automatic correction for the 1742 digitizer
    bool enable_corrections;
    size = 4*sizeof(bool);
    db_get_value(hDB,0,"/Configurations/DRS4Correction",&enable_corrections, &size, TID_BOOL,TRUE);

    CAEN_DGTZ_ErrorCode ret2;


    cout<<"STo configurando per davvero\n";
    if(strcmp(BoardName[i],"V1742")==0)      //da decidere
      {
      	if(!enable_corrections) {
            //std::cout<<"DEBUG NO CORRECTION"<<std::endl;
            ret2 = CAEN_DGTZ_DisableDRS4Correction(gDGTZ[i]);
            if(ret2 != CAEN_DGTZ_Success) {
            cerr<<"Error in DisableDRS4Correction"<<endl;
		        }
	      } else {

		      if ((ret2 = CAEN_DGTZ_LoadDRS4CorrectionData(gDGTZ[i],DRS4Frequency)) != CAEN_DGTZ_Success)
          {
              cerr<<"Error in LoadDRS4Correction"<<endl;
              exit(EXIT_FAILURE);
          }
          if ((ret2 = CAEN_DGTZ_EnableDRS4Correction(gDGTZ[i])) != CAEN_DGTZ_Success)
          {
              cerr<<"Error in EnableDRS4Correction"<<endl;
              exit(EXIT_FAILURE);
          }
          cout<<"Dovrei aver fatto\n";
        // Print correction tables
//         CAEN_DGTZ_DRS4Correction_t CTable[MAX_X742_GROUP_SIZE];
//         ret = CAEN_DGTZ_GetCorrectionTables(gDGTZ[i], DRS4Frequency, (void*)CTable);
//         if(ret != CAEN_DGTZ_Success) {
//             throw std::runtime_error("DEBUG ctables.\n");
//         } else {
//             SaveCorrectionTables("./ctables/ctables_DCO", (uint32_t)(pow(2,NCHDGTZ[i]))-1, CTable);
//         }
        }
      }

      else{

      //Calibration
      //ret |= CAEN_DGTZ_Calibrate(gDGTZ[i]);

      }


    //Buffer allocation
    uint32_t bsize;
    ret = CAEN_DGTZ_MallocReadoutBuffer(gDGTZ[i],&buffer_dgtz[i],&bsize);
    if(ret != CAEN_DGTZ_Success) {
	      printf("Errors during Digitizer MallocReadoutBuffer, board number %d.\n",i);
        cm_msg(MERROR, "cupid_daq", "Errors during Digitizer MallocReadoutBuffer, board number %d.", i);
      }

    if(ret != CAEN_DGTZ_Success) {
      printf("Errors during Digitizer Configuration.\n");
      //cm_msg(MERROR, "cygnus_daq", "Errors during Digitizer Configuration.");
      //throw runtime_error("Errors during Digitizer Digitizer Configuration.");
    }

  }//end for cycle on boards
  return SUCCESS;

}
#endif

INT disable_trigger()
{
#ifdef HAVE_CAEN_BRD

  //WRONG FOR V3718
  //SET OUT_1 to 0 (busy)
  CAENVME_ClearOutputRegister(gVme,cvOut1Bit);        //////////////////////Da modificare new_bridge

#ifdef HAVE_CAEN_DGTZ
  for(int i=0;i<nboard;i++){
    CAEN_DGTZ_SWStopAcquisition(gDGTZ[i]);
  }
#endif

#endif

  return 0;
}

INT enable_trigger()
{

  ClearDevice();

#ifdef HAVE_CAEN_DGTZ
  for(int i=0;i<nboard;i++){
    CAEN_DGTZ_SWStartAcquisition(gDGTZ[i]);
  }
#endif

  return 0;

}

INT ClearDevice()
{

#ifdef HAVE_CAEN_BRD

#ifdef HAVE_CAEN_DGTZ
  for(int i=0;i<nboard;i++){
    CAEN_DGTZ_ClearData(gDGTZ[i]);
  }
#endif

  //WRONG FOR V3718
  //SET OUT_1 to 1 (not busy)
  CAENVME_SetOutputRegister(gVme,cvOut1Bit);        //////////////////////Da modificare new_bridge

  //TO BE CHECKD FOR V3718
  //Reset GATE (pulser B)
  CAENVME_StopPulser(gVme,cvPulserB);        //////////////////////Da modificare new_bridge

#endif

  return 0;

}

#ifdef HAVE_CAEN_DGTZ
int read_dgtz(char* pevent){

  uint32_t bsize;
  char * evtptr = NULL;
  uint32_t NumEvents;
  uint32_t events_max = 128;
  CAEN_DGTZ_EventInfo_t eventInfo;



  WORD* pdata16 = NULL;
  bk_create(pevent, "DIG0", TID_WORD, (void**)&pdata16);

  std::vector<std::vector<uint32_t>> TRGTTAG(nboard);
  std::vector<int> EVTSNUM(nboard);
  std::vector<uint16_t> StartIndexCell(128);

  // DEBUG
  //ofstream myfile;
  //myfile.open("debug.txt", ios_base::app);
  //myfile << "read_dgtz ------"<<endl;


  for(int i=0;i<nboard;i++){

    int event_i = 0;

    std::vector<uint32_t> tmp_trgttag(128);

    CAEN_DGTZ_ReadData(gDGTZ[i],CAEN_DGTZ_SLAVE_TERMINATED_READOUT_MBLT,buffer_dgtz[i],&bsize);
    CAEN_DGTZ_GetNumEvents(gDGTZ[i],buffer_dgtz[i],bsize,&NumEvents);
    NumEvents =std::min(NumEvents, events_max);
    //myfile<<"i = "<<i<<" numevents = "<<NumEvents<<endl;
    //if(NumEvents != 1) cout << "---------- ERROR!!!!! DGTZ > 1 event!!! ----------" << endl;
    //cout << "NumEvents = " << NumEvents << endl;

    if(strcmp(BoardName[i],"V1742")==0){

      CAEN_DGTZ_X742_EVENT_t *Evt = NULL;

      for(int iev=0;iev<NumEvents;iev++){

          CAEN_DGTZ_AllocateEvent(gDGTZ[i], (void**)&Evt);

          CAEN_DGTZ_GetEventInfo(gDGTZ[i],buffer_dgtz[i],bsize,iev,&eventInfo,&evtptr);

          CAEN_DGTZ_ErrorCode ret = CAEN_DGTZ_DecodeEvent(gDGTZ[i],evtptr,(void**)&Evt);

          tmp_trgttag[iev]    = Evt->DataGroup[0].TriggerTimeTag;
          StartIndexCell[iev] = Evt->DataGroup[0].StartIndexCell;
          //tmp_trgttag[event_i] = Evt->DataGroup[0].TriggerTimeTag;
                //event_i++;

          for(int j=0;j<NCHDGTZ[i];j++){          ////Wouldn't it be better with a full memory transfer of the buffer of the board? (if the waveforms are stored consecutively) See DecodeEvent

            uint32_t ig = j/8;
            uint32_t ich = j%8;

            for (uint32_t k=0; k<ndgtz[i]; ++k) {

              uint16_t temp = (uint16_t)(Evt->DataGroup[ig].DataChannel[ich][k]);
              *pdata16++ = temp;

            }

          }

          CAEN_DGTZ_FreeEvent(gDGTZ[i],(void**)&Evt);

      }
    }

    //#endif
    TRGTTAG[i] = tmp_trgttag;
    EVTSNUM[i] = NumEvents; //event_i;

    //cout<<"       "<< endl<<endl<<endl<<endl;
    //cout<<atoi(&BoardName[i][1])<<endl;
    //for(unsigned int j=0; j<EVTSNUM[i]; j++) {
    //  cout<<TRGTTAG[i][j]<<" "<<endl;
    //}
    //if(i==1) throw std::runtime_error("DEBUG");


  }//end for on boards for reading data

  bk_close(pevent, pdata16);

  uint32_t* hdata = NULL;
  uint32_t header_data = 0;
  bk_create(pevent, "DGH0", TID_DWORD, (void **)&hdata);

  header_data = nboard;
  *hdata++ = header_data;

  for(int i=0;i<nboard;i++){

    // uint32_t* hdata = NULL;
    // sprintf(query,"DGH%d",i);
    //bk_create(pevent, query, TID_DWORD, (void **)&hdata);

    // uint32_t header_data = 0;

    header_data = atoi(&BoardName[i][1]);
    *hdata++ = header_data;

    header_data = ndgtz[i];
    *hdata++ = header_data;

    header_data = NCHDGTZ[i];
    *hdata++ = header_data;

    header_data = EVTSNUM[i];
    *hdata++ = header_data;

    CAEN_DGTZ_BoardInfo_t BoardInfo;
    CAEN_DGTZ_GetInfo(gDGTZ[i], &BoardInfo);
    header_data = (uint32_t)pow(2,BoardInfo.ADC_NBits);
    *hdata++ = header_data;

    header_data = SAMPLING[i];
    *hdata++ = header_data;

    for(int j=0;j<NCHDGTZ[i];j++){
      header_data = (uint32_t)(DGTZ_OFFSET[i][j]*65536 + 32768);
      *hdata++ = header_data;
    }

    //cout<<"=========="<<endl;
    for(unsigned int j=0; j<EVTSNUM[i]; j++) {
      //cout<<TRGTTAG[i][j]<<" "<<endl;
      *hdata++ = TRGTTAG[i][j];
    }

    if(strcmp(BoardName[i], "V1742")==0) {
    	for(unsigned int j=0; j<EVTSNUM[i]; j++) {
      		*hdata++ = (uint32_t)StartIndexCell[j];
    	}
    }

  }//end for on boards for header


  //myfile.close();  //debug

  bk_close(pevent, hdata);

  //throw std::runtime_error("DEBUG");

  return 0;

}
#endif

#ifdef HAVE_CAEN_DGTZ
void Free_arrays(){

  delete[] gDGTZ;
  delete[] gDigBase;
  delete[] NCHDGTZ;
  delete[] ndgtz;
  delete[] SAMPLING;
  delete[] posttrg;
  for(int i=0;i<nboard;i++){
    delete[] BoardName[i];
    delete[] buffer_dgtz[i];      //This may raise a break for multiple free of memory, in case just comment this line
    delete[] DGTZ_OFFSET[i];
  }
  delete[]  BoardName;
  delete[]  buffer_dgtz;
  delete[]  DGTZ_OFFSET;
}
#endif


#ifdef HAVE_CAEN_DGTZ
int SaveCorrectionTables(char *outputFileName, uint32_t groupMask, CAEN_DGTZ_DRS4Correction_t *tables) {
    char fnStr[MAX_BASE_INPUT_FILE_LENGTH + 1];
    int ch,i,j, gr;
    FILE *outputfile;

    if((int)(strlen(outputFileName) - 17) > MAX_BASE_INPUT_FILE_LENGTH)
        return -1; // Too long base filename

    std::cout<<"DEBUG MAX_X742_GROUP_SIZE = "<<MAX_X742_GROUP_SIZE<<std::endl<<std::flush;

    for(gr = 0; gr < MAX_X742_GROUP_SIZE; gr++) {
        std::cout<<"DEBUG (start) gr = "<<gr<<std::endl<<std::flush;
        CAEN_DGTZ_DRS4Correction_t *tb;

        if(!((groupMask>>gr)&0x1))
            continue;
        tb = &tables[gr];
        sprintf(fnStr, "%s_gr%d_cell.txt", outputFileName, gr);
        printf("Saving correction table cell values to %s\n", fnStr);
        if((outputfile = fopen(fnStr, "w")) == NULL)
            return -2;
        for(ch=0; ch<MAX_X742_CHANNEL_SIZE; ch++) {
            fprintf(outputfile, "Calibration values from cell 0 to 1024 for channel %d:\n\n", ch);
            for(i=0; i<1024; i+=8) {
                for(j=0; j<8; j++)
                    fprintf(outputfile, "%d\t", tb->cell[ch][i+j]);
                fprintf(outputfile, "cell = %d to %d\n", i, i+7);
            }
        }
        fclose(outputfile);

        sprintf(fnStr, "%s_gr%d_nsample.txt", outputFileName, gr);
        printf("Saving correction table nsamples values to %s\n", fnStr);
        if((outputfile = fopen(fnStr, "w")) == NULL)
            return -3;
        for(ch=0; ch<MAX_X742_CHANNEL_SIZE; ch++) {
            fprintf(outputfile, "Calibration values from cell 0 to 1024 for channel %d:\n\n", ch);
            for(i=0; i<1024; i+=8) {
                for(j=0; j<8; j++)
                    fprintf(outputfile, "%d\t", tb->nsample[ch][i+j]);
                fprintf(outputfile, "cell = %d to %d\n", i, i+7);
            }
        }
        fclose(outputfile);

        sprintf(fnStr, "%s_gr%d_time.txt", outputFileName, gr);
        printf("Saving correction table time values to %s\n", fnStr);
        if((outputfile = fopen(fnStr, "w")) == NULL)
            return -4;
        fprintf(outputfile, "Calibration values (ps) from cell 0 to 1024 :\n\n");
        for(i=0; i<1024; i+=8) {
            for(ch=0; ch<8; ch++)
                fprintf(outputfile, "%09.3f\t", tb->time[i+ch]);
            fprintf(outputfile, "cell = %d to %d\n", i, i+7);
        }
        fclose(outputfile);
    }

    return 0;
}
#endif