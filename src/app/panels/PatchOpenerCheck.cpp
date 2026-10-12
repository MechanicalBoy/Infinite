// Once per launch: if double-clicking a patch would open a different copy of Infinite, say so with one notice and a
// "Use this copy" action. Several copies on one machine (an old download, a build folder) share one identity and the
// OS picks among them by version number or at random, so users kept opening patches in an old copy and saw fixed bugs
// as still there. Nothing changes without the click; the notice expires on its own and comes back next launch while
// the other copy still opens patches.
#include "app/AppShared.h"
#include "core/Notices.h"

namespace app
{
bool PatchOpenerNotice(const Platform::PatchOpener& o, std::string& title, std::string& detail)
{
   if (o.self.empty() || o.isSelf || o.otherApp || o.selfTemporary)
      return false;
   if (o.opener.empty())
   {
      title = "Double-clicking a patch doesn't open Infinite";
      detail = "Patches still open from File > Open. Use this copy to open them from your file manager too.";
      return true;
   }
   title = "Patches open in another copy of Infinite";
   // Same version is common (two builds of one release), so only a different number is worth naming.
   const bool named = !o.version.empty() && o.version != INFINITE_VERSION_STRING;
   detail = "Double-clicking a patch opens " + (named ? "Infinite " + o.version : std::string("another copy")) + " at " +
            o.opener + (named ? ", not this " INFINITE_VERSION_STRING "." : ", not this one.");
   return true;
}

void CheckPatchOpener()
{
   Platform::PatchOpener o;
   std::string title, detail;
   if (!Platform::QueryPatchOpener(o) || !PatchOpenerNotice(o, title, detail))
      return;
   Notices::Post(Notices::Level::Warning, "patch.opener", title, detail, "Use this copy", [o]
   {
      std::string error;
      if (Platform::MakeThisCopyPatchOpener(o, error))
         Notices::Post(Notices::Level::Info, "patch.opener", "Patches now open in this copy");
      else
         Notices::Post(Notices::Level::Warning, "patch.opener", "Patches still open in the other copy", error);
   });
}
}
