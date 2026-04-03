/********************************************************************\

  Name:         nulldev.c
  Created by:   Stefan Ritt

  Contents:     NULL Device Driver. This file can be used as a 
                template to write a read device driver

  $Id$

\********************************************************************/

#include <iostream>
#include <fstream>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string>
#include <math.h>
#include <sstream>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include "midas.h"

/*---- globals -----------------------------------------------------*/

#define DEFAULT_TIMEOUT 10000   /* 10 sec. */

/* Store any parameters the device driver needs in following 
   structure. Edit the CSVDEV_SETTINGS_STR accordingly. This 
   contains usually the address of the device. For a CAMAC device
   this could be crate and station for example. */

typedef struct {
   char path[256];
   char basefile[64];
   char extension[16];
} CSVDEV_SETTINGS;

#define CSVDEV_SETTINGS_STR "\
Path =  STRING : [256] /media/Mercury_dati/\n\
Basefile = STRING : [64] Mercury_\n\
Extension = STRING : [16] .txt\n\
"

/* following structure contains private variables to the device
   driver. It is necessary to store it here in case the device
   driver is used for more than one device in one frontend. If it
   would be stored in a global variable, one device could over-
   write the other device's variables. */

typedef struct {
   CSVDEV_SETTINGS csvdev_settings;
   float *array;
   INT num_channels;
    INT(*bd) (INT cmd, ...);    /* bus driver entry function .... we exploit the null.h.. basically we do not use it*/
   void *bd_info;               /* private info of bus driver */
   HNDLE hkey;                  /* ODB key for bus driver info */
} CSVDEV_INFO;

/*---- device driver routines --------------------------------------*/

typedef INT(func_t) (INT cmd, ...);

/*Static global array to store the last line of csv file which will be read*/
static float last_row[64];
/*Static global handle for the database odb*/
static HNDLE hDB;

/*Custom functions*/

// Split string using delimiter
std::vector<std::string> split(const std::string& line, char delimiter)
{
   std::vector<std::string> result;
   std::stringstream ss(line);
   std::string item;

   while (std::getline(ss, item, delimiter))
   {
      result.push_back(item);
   }

   return result;
}
// Take Nth row of file and returns it as a string vector. Firts line is N=0. N=-1 means last
std::vector<std::string> get_N_row_as_list(const std::string& file_path, int N)
{
   std::ifstream file(file_path.c_str());
   if (!file.is_open())
   {
      cm_msg(MERROR,"Device","Impossible to open file %s..",file_path.c_str());
      throw std::runtime_error("Impossible to open file: " + file_path);
   }

   std::string line;
   std::string lastline;

   if(N==-1)
   {
      file.seekg(-300, file.end);     //goes immediately to 300 characters prior to the end of file
      while (std::getline(file, line))
      {
         if(!line.empty())    lastline = line;  
      }
      return split(lastline, '\t');
   }

   int current_row = 0;
   while (std::getline(file, line))
   {
      if (current_row == N)   return split(line, '\t');
      ++current_row;
   }
   cm_msg(MERROR,"Device","Index while reading csv file went out of range..");
   return {""};
}

// Returns string with filename of most recent file in a folder
std::string get_most_recent_file(const char* directory, const char* prefix, const char* extension)
{
   std::filesystem::path most_recent_path;
   std::filesystem::file_time_type most_recent_time;
   bool found = false;

   std::string directory_str = directory;

   for (const auto& entry : std::filesystem::directory_iterator(directory_str))
   {
      if (!entry.is_regular_file())        continue;

      std::string filename = entry.path().filename().string();
      bool has_prefix = filename.rfind(prefix, 0) == 0;
      bool has_extension = entry.path().extension() == extension;

      if (has_prefix && has_extension)
      {
         auto current_time = std::filesystem::last_write_time(entry.path());

         if (!found || current_time > most_recent_time)
         {
            most_recent_time = current_time;
            most_recent_path = entry.path();
            found = true;

         }
      }
   }
   if (!found) return "";

   return most_recent_path.string();

}

/*End custom functions*/

/* the init function creates a ODB record which contains the
   settings and initialized it variables as well as the bus driver */
INT csv_init(HNDLE hkey, CSVDEV_INFO **pinfo, INT channels, func_t *bd)
{
   int status, size;
   HNDLE hkeydd;
   CSVDEV_INFO *info;

   /* allocate info structure */
   info = (CSVDEV_INFO*) calloc(1, sizeof(CSVDEV_INFO));
   *pinfo = info;

   cm_get_experiment_database(&hDB, NULL);

   /* create NULLDEV settings record */
   status = db_create_record(hDB, hkey, "DD", CSVDEV_SETTINGS_STR);
   if (status != DB_SUCCESS)
      return FE_ERR_ODB;

   db_find_key(hDB, hkey, "DD", &hkeydd);
   size = sizeof(info->csvdev_settings);
   db_get_record(hDB, hkeydd, &info->csvdev_settings, &size, 0);

   //test
   char testo[channels*32];
   HNDLE hkeynamesinput;
   db_find_key(hDB, 0, "/Equipment/Environment/Settings/Names Input", &hkeynamesinput);
   printf("\nvalorekey %d \n",hkeynamesinput);
   size = sizeof(testo);
   db_get_record(hDB, hkeynamesinput, &testo, &size, 0);

   for(int i=0;i<96;i++) std::cout<<testo[i]<<std::endl;

   /* initialize driver */
   info->num_channels = channels;
   info->array = (float*) calloc(channels, sizeof(float));
   info->hkey = hkey;

   return FE_SUCCESS;
}

/*----------------------------------------------------------------------------*/

INT csvdev_exit(CSVDEV_INFO * info)
{
   /* call EXIT function of bus driver, usually closes device */

   /* free local variables */
   if (info->array)
      free(info->array);

   free(info);

   return FE_SUCCESS;
}

/*----------------------------------------------------------------------------*/

INT csvdev_set(CSVDEV_INFO * info, INT channel, float value)
{
   //We do not need set for this

   return FE_SUCCESS;
}

/*----------------------------------------------------------------------------*/

INT csvdev_get(CSVDEV_INFO * info, INT channel, float *pvalue)
{
   char str[80];

   *pvalue = (float) atof(str);

   /* simulate reading by generating some sine wave data */
   /*if (channel < info->num_channels) {
      time_t t = time(NULL);
      *pvalue = 5 + 5 * sin(M_PI * t / 60) + 10 * channel;
   } else
      *pvalue = 0.f;*/

   //Add your read function 
   if(channel==0)
   {
      HNDLE hkeydd;
      db_find_key(hDB, info->hkey, "DD", &hkeydd);
      int size = sizeof(info->csvdev_settings);
      db_get_record(hDB, hkeydd, &info->csvdev_settings, &size, 0);
      std::string filename;
      filename = get_most_recent_file(info->csvdev_settings.path,info->csvdev_settings.basefile,info->csvdev_settings.extension);
      //get last line
      std::vector<std::string> line_pieces;
      line_pieces = get_N_row_as_list(filename,-1);
      for(long unsigned int i=0;i<line_pieces.size()-1;i++)  last_row[i] = stof(line_pieces[i+1]);
   }
   
   *pvalue = last_row[channel];

   return FE_SUCCESS;
}

/*---- device driver entry point -----------------------------------*/

INT csvdev(INT cmd, ...)
{
   va_list argptr;
   HNDLE hKey;
   INT channel, status;
   float value, *pvalue;
   CSVDEV_INFO *info;

   va_start(argptr, cmd);
   status = FE_SUCCESS;

   switch (cmd) {
   case CMD_INIT: {
      hKey = va_arg(argptr, HNDLE);
      CSVDEV_INFO** pinfo = va_arg(argptr, CSVDEV_INFO **);
      channel = va_arg(argptr, INT);
      va_arg(argptr, DWORD);
      func_t *bd = va_arg(argptr, func_t *);
      status = csv_init(hKey, pinfo, channel, bd);
      break;
   }
   case CMD_EXIT:
      info = va_arg(argptr, CSVDEV_INFO *);
      status = csvdev_exit(info);
      break;

   case CMD_SET:
      info = va_arg(argptr, CSVDEV_INFO *);
      channel = va_arg(argptr, INT);
      value = (float) va_arg(argptr, double);   // floats are passed as double
      status = csvdev_set(info, channel, value);
      break;

   case CMD_GET:
      info = va_arg(argptr, CSVDEV_INFO *);
      channel = va_arg(argptr, INT);
      pvalue = va_arg(argptr, float *);
      status = csvdev_get(info, channel, pvalue);
      break;

   default:
      break;
   }

   va_end(argptr);

   return status;
}

/*------------------------------------------------------------------*/