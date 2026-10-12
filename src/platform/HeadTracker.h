#pragma once

// Listener head tracking for the Spatial Mixer (docs/plans/spatial, Block A).
// Yaw only: it is the cue that resolves front/back. Reference counted, so two
// Spatial Mixers share one sensor. Main thread only.
namespace HeadTracker
{
   enum Source { kOff = 0, kHeadphones = 1, kWebcam = 2 };

   // macOS: AirPods Pro/Max/3rd-gen (and Beats Fit Pro) via CoreMotion, macOS 14+.
   // Windows / Linux: no headphone-motion API exists; the webcam fallback is not
   // built yet, so these report false there.
   bool Supported(Source source);

   // Headless and self-test runs: Start becomes a no-op. A process started
   // from a terminal has the terminal as its privacy-responsible parent, and
   // macOS kills it on the first CoreMotion call (no motion usage string).
   void Disable();

   void Start(Source source);
   void Stop(Source source);

   // Latest yaw in degrees relative to the pose captured at Start/Recenter;
   // positive = head turned right. False when no fresh sample (sensor absent,
   // out of the ears, permission denied).
   bool ReadYaw(float& yawDegrees);
   void Recenter();

   // One short line for the UI ("AirPods connected", "Allow Motion access ...").
   const char* Status();
}
