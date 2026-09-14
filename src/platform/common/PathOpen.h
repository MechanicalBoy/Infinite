#pragma once

#include <cstdio>
#include <fstream>
#include <string>

#if defined(_WIN32)
   #include "../win/WinCommon.h"

   inline FILE* OpenFileUtf8(const std::string& pathUtf8, const char* mode)
   {
      std::wstring widePath = WinCommon::Utf8ToWide(pathUtf8);
      std::wstring wideMode = WinCommon::Utf8ToWide(mode);
      return _wfopen(widePath.c_str(), wideMode.c_str());
   }

   inline std::ifstream OpenIfstreamUtf8(const std::string& pathUtf8,
                                         std::ios_base::openmode mode = std::ios_base::in)
   {
      return std::ifstream(WinCommon::Utf8ToWide(pathUtf8), mode);
   }
#else
   inline FILE* OpenFileUtf8(const std::string& pathUtf8, const char* mode)
   {
      return std::fopen(pathUtf8.c_str(), mode);
   }

   inline std::ifstream OpenIfstreamUtf8(const std::string& pathUtf8,
                                         std::ios_base::openmode mode = std::ios_base::in)
   {
      return std::ifstream(pathUtf8, mode);
   }
#endif
