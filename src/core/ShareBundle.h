#pragma once

#include <string>
#include <utility>
#include <vector>

// --- Share bundle ---------------------------------------------------------
// A patch sent to someone else, as one file (a zip, extension .infshare):
//   patch.inf      the patch with every file path blanked and every user folder
//                  rewritten to ~, so it carries no name and opens anywhere
//   thumbnail.png  one frame of the picture
//   preview.mp4    a few seconds of it playing (left out when it could not render)
//   share.json     name, author, description, app version and the media the
//                  patch used, which the person opening it has to supply
// No GL or UI here, so it can be tested on its own and reused by the website tool.
namespace ShareBundle
{
   struct Meta
   {
      std::string name, author, description, appVersion;
      std::vector<std::string> blankedMedia;   // file paths the patch pointed at, base names only
   };

   // The patch text with `s path`, `s *Path`, `s *File` and `s file` values emptied and user
   // folders rewritten to ~. Every blanked value's file name is appended to `blanked`.
   std::string CleanPatchText(const std::string& text, std::vector<std::string>* blanked);

   std::string MetaJson(const Meta& meta);

   // A name that is safe as a file name on every platform.
   std::string SafeName(const std::string& name);

   using Entry = std::pair<std::string, std::string>;   // zip path, bytes
   bool WriteZip(const std::string& zipPath, const std::vector<Entry>& entries, std::string& error);

   // Unpacks into `outDir` (created if needed). Entry names that climb out of it are refused.
   bool ExtractZip(const std::string& zipPath, const std::string& outDir, std::string& error);
}
