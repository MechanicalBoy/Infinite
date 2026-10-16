#include "ShareBundle.h"

#include <cstring>
#include <filesystem>
#include <fstream>
#include <regex>
#include <sstream>

#include "miniz.h"

namespace ShareBundle
{
   namespace
   {
      std::string JsonEscape(const std::string& s)
      {
         std::string out;
         for (const char c : s)
         {
            switch (c)
            {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
               if ((unsigned char)c < 0x20)
               {
                  char buf[8];
                  snprintf(buf, sizeof(buf), "\\u%04x", (unsigned)c);
                  out += buf;
               }
               else
                  out += c;
            }
         }
         return out;
      }

      std::string BaseName(const std::string& path)
      {
         const size_t slash = path.find_last_of("/\\");
         return slash == std::string::npos ? path : path.substr(slash + 1);
      }
   }

   std::string CleanPatchText(const std::string& text, std::vector<std::string>* blanked)
   {
      static const std::regex pathLine(R"(^(\s+s (?:path|[A-Za-z]*Path|[A-Za-z]*File|file)) (.*)$)");
      static const std::regex userDir(R"(/Users/[^/\s]+|[A-Za-z]:\\+Users\\+[^\\/\s]+)");
      std::string out;
      std::istringstream in(text);
      std::string line;
      bool first = true;
      while (std::getline(in, line))
      {
         if (!line.empty() && line.back() == '\r')
            line.pop_back();
         std::smatch m;
         if (std::regex_match(line, m, pathLine))
         {
            if (blanked != nullptr && !m[2].str().empty())
            {
               const std::string base = BaseName(m[2].str());
               bool seen = false;
               for (const std::string& b : *blanked)
                  seen = seen || b == base;
               if (!seen)
                  blanked->push_back(base);
            }
            line = m[1].str() + " ";
         }
         else
            line = std::regex_replace(line, userDir, "~");
         if (!first)
            out += '\n';
         out += line;
         first = false;
      }
      if (!text.empty() && text.back() == '\n')
         out += '\n';
      return out;
   }

   std::string SafeName(const std::string& name)
   {
      std::string out;
      for (const char c : name)
      {
         const bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == ' ';
         out += ok ? c : '_';
      }
      while (!out.empty() && (out.back() == ' ' || out.back() == '.'))
         out.pop_back();
      return out.empty() ? std::string("Untitled") : out;
   }

   std::string MetaJson(const Meta& meta)
   {
      std::string j = "{\n";
      j += "  \"name\": \"" + JsonEscape(meta.name) + "\",\n";
      j += "  \"author\": \"" + JsonEscape(meta.author) + "\",\n";
      j += "  \"description\": \"" + JsonEscape(meta.description) + "\",\n";
      j += "  \"appVersion\": \"" + JsonEscape(meta.appVersion) + "\",\n";
      j += "  \"needsMedia\": [";
      for (size_t i = 0; i < meta.blankedMedia.size(); i++)
         j += std::string(i ? ", " : "") + "\"" + JsonEscape(meta.blankedMedia[i]) + "\"";
      j += "]\n}\n";
      return j;
   }

   bool WriteZip(const std::string& zipPath, const std::vector<Entry>& entries, std::string& error)
   {
      error.clear();
      std::error_code ec;
      std::filesystem::remove(std::filesystem::u8path(zipPath), ec);
      for (const Entry& e : entries)
      {
         if (!mz_zip_add_mem_to_archive_file_in_place(zipPath.c_str(), e.first.c_str(), e.second.data(),
                                                      e.second.size(), nullptr, 0, MZ_DEFAULT_LEVEL))
         {
            error = "could not write " + e.first + " into the bundle";
            return false;
         }
      }
      return true;
   }

   bool ExtractZip(const std::string& zipPath, const std::string& outDir, std::string& error)
   {
      error.clear();
      mz_zip_archive zip;
      memset(&zip, 0, sizeof(zip));
      if (!mz_zip_reader_init_file(&zip, zipPath.c_str(), 0))
      {
         error = "not a share bundle";
         return false;
      }
      std::error_code ec;
      std::filesystem::create_directories(std::filesystem::u8path(outDir), ec);
      bool ok = true;
      const mz_uint count = mz_zip_reader_get_num_files(&zip);
      for (mz_uint i = 0; i < count && ok; i++)
      {
         if (mz_zip_reader_is_file_a_directory(&zip, i))
            continue;
         char name[512];
         mz_zip_reader_get_filename(&zip, i, name, sizeof(name));
         const std::string n = name;
         if (n.empty() || n[0] == '/' || n[0] == '\\' || n.find("..") != std::string::npos || n.find(':') != std::string::npos)
         {
            error = "the bundle holds an unsafe path: " + n;
            ok = false;
            break;
         }
         size_t size = 0;
         void* data = mz_zip_reader_extract_to_heap(&zip, i, &size, 0);
         if (data == nullptr)
         {
            error = "could not read " + n + " from the bundle";
            ok = false;
            break;
         }
         const std::filesystem::path dest = std::filesystem::u8path(outDir) / std::filesystem::u8path(n);
         std::filesystem::create_directories(dest.parent_path(), ec);
         std::ofstream f(dest, std::ios::binary);
         f.write((const char*)data, (std::streamsize)size);
         if (!f.good())
         {
            error = "could not write " + n;
            ok = false;
         }
         mz_free(data);
      }
      mz_zip_reader_end(&zip);
      return ok;
   }
}
