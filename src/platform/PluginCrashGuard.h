#pragma once

// Which plugin was running when the app died (v0.6 2.6).
//
// Plugins run inside Infinite's process, so a fault in a plugin's render or
// instantiation is the app's crash (plugin-host-hardening, tier 3), and a
// patch holding that plugin would crash again on every reopen. This does not
// catch the fault. It only leaves a one-line marker naming the plugin the
// crashing thread was inside, and the next launch reads it:
//
//   - an Audio Unit that crashed is from then on loaded out of process
//     (macOS's AU hosting service), where a second crash silences the node
//     instead of ending the app;
//   - a VST3 has no such service, so a patch does not reload it: the node
//     keeps the plugin's identity and says why. Picking the plugin again
//     by hand is the retry.
//
// Plugins that never crashed stay in process: hosting every plugin out of
// process costs render time on every block (tools/re-survey/au_oop.py).

#include <string>

namespace PluginCrashGuard
{
   // Main thread, once at startup, before any plugin loads. `dir` is the
   // app-support directory. Folds a marker left by a crashed run into the
   // remembered list and returns that plugin's identifier (empty if the last
   // run did not die inside a plugin).
   std::string Init(const std::string& dir);

   // This thread is inside the plugin `identifier` names until the scope
   // ends. One thread-local pointer store each way: safe on the audio
   // thread. `identifier` must outlive the scope (a handle's own desc does).
   class Scope
   {
   public:
      explicit Scope(const char* identifier);
      ~Scope();
      Scope(const Scope&) = delete;
      Scope& operator=(const Scope&) = delete;

   private:
      const char* mPrevious;
   };

   // Called from the platform's crash handler, on the crashing thread, while
   // the process is dying. Async-signal-safe: open/write/close on a path
   // resolved in Init, no allocation. Does nothing outside a Scope.
   void NoteCrash();

   // Main thread.
   bool CrashedBefore(const std::string& identifier);
   void Forget(const std::string& identifier);
}
