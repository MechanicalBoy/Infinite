#pragma once

#include <string>

// In-place update: download the release asset UpdateCheck found, verify its SHA-256 against GitHub's digest, stage it
// beside this copy (Platform::PrepareSelfUpdate), and on the user's "Restart to update" swap it in once Infinite exits.
// One copy, updated where it is - so the OS never has an older Infinite to open patches with.
// Same worker + mutex shape as Extensions; everything here is main-thread except the worker itself.
namespace SelfUpdate
{
   enum class Stage { Idle, Downloading, Ready, Failed };

   // Offered only when the platform can replace this copy and the release names a matching asset with a digest.
   // `whyNot` explains a false return (shown beside the plain Download button).
   bool Available(std::string& whyNot);

   // Starts the download for UpdateCheck::ResultVersion(). No-op while one is running or ready.
   void Start();

   Stage GetStage();
   float Progress();                  // 0..1, or -1 when the size is unknown
   const std::string& LastError();    // valid when Failed

   // Ready only: starts the swap helper; the caller quits normally (after its unsaved-changes prompt) right after.
   bool LaunchHelper(bool relaunch, std::string& outError);

   // Cancels and joins the worker. Call before the process exits.
   void Shutdown();

   // Test seam: stage a local payload (DMG / unpacked folder / AppImage) without the network or the digest check.
   bool StageLocal(const std::string& payload, const std::string& version, std::string& outError);
}
