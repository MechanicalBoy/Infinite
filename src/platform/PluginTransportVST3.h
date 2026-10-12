#pragma once

// One mapping from the host clock (Platform::PluginTransport) to a VST3
// ProcessContext, shared by the macOS, Windows and Linux VST3 hosts so the
// three can't drift. Real-time safe: plain stores, no allocation.

#include <cmath>

#include "platform/Platform.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"

namespace Platform
{
   inline void FillVST3ProcessContext(Steinberg::Vst::ProcessContext& ctx, const PluginTransport* t,
                                      double sampleRate, Steinberg::int64 continuousSamples)
   {
      using PC = Steinberg::Vst::ProcessContext;
      static const PluginTransport kNoHostClock;
      const PluginTransport& tr = t != nullptr ? *t : kNoHostClock;
      const double tempo = tr.tempo > 0.0 ? tr.tempo : 120.0;

      ctx.sampleRate = sampleRate;
      ctx.tempo = tempo;
      ctx.timeSigNumerator = tr.timeSigNumerator > 0 ? tr.timeSigNumerator : 4;
      ctx.timeSigDenominator = tr.timeSigDenominator > 0 ? tr.timeSigDenominator : 4;
      ctx.projectTimeMusic = tr.beats;
      ctx.barPositionMusic = tr.barStartBeats;
      // Project time in samples from the musical position at the current
      // tempo: the same axis a plugin derives from projectTimeMusic, so the
      // two never disagree (a tempo ramp would bend real time, not beats).
      ctx.projectTimeSamples = (Steinberg::int64)std::llround(tr.beats * 60.0 / tempo * sampleRate);
      ctx.continousTimeSamples = continuousSamples;
      ctx.cycleStartMusic = tr.loopStartBeats;
      ctx.cycleEndMusic = tr.loopEndBeats;

      Steinberg::uint32 state = PC::kTempoValid | PC::kTimeSigValid | PC::kProjectTimeMusicValid |
                                PC::kBarPositionValid | PC::kContTimeValid;
      if (tr.playing)
         state |= PC::kPlaying;
      if (tr.loopActive && tr.loopEndBeats > tr.loopStartBeats)
         state |= PC::kCycleActive | PC::kCycleValid;
      ctx.state = state;
   }

   // The reverse, for PluginHostClockSeen: what a plugin reads out of `ctx`.
   inline PluginTransport ReadVST3ProcessContext(const Steinberg::Vst::ProcessContext& ctx)
   {
      using PC = Steinberg::Vst::ProcessContext;
      PluginTransport t;
      t.tempo = ctx.tempo;
      t.beats = ctx.projectTimeMusic;
      t.barStartBeats = ctx.barPositionMusic;
      t.timeSigNumerator = ctx.timeSigNumerator;
      t.timeSigDenominator = ctx.timeSigDenominator;
      t.playing = (ctx.state & PC::kPlaying) != 0;
      t.loopActive = (ctx.state & PC::kCycleActive) != 0;
      t.loopStartBeats = ctx.cycleStartMusic;
      t.loopEndBeats = ctx.cycleEndMusic;
      return t;
   }
}
