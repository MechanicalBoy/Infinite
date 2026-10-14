#pragma once

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>

#include "core/ModShapes.h"

// Per-voice modulation (docs/plans/modulation/per-voice.md).
//
// A modulator whose `per voice` switch is on, cabled straight into a synth
// knob, runs once per voice on the audio thread instead of once per frame on
// the main thread. The main thread describes what to run as a Plan - plain
// data copied from the modulator's params, nothing that points back at a
// node - and the synth's audio half runs it with a Runtime:
//
//   main (CookFrame apply loop)        audio (synth ProcessBlock)
//   IVoiceModSource::VoiceSpec  ->  Plan  ->  PlanBox  ->  Runtime::BeginBlock
//   IVoiceModTarget::VoiceParamFor                       NoteOn / NoteOff / Apply
//
// Real-time: Plan is fixed-size POD, PlanBox is a lock-free triple buffer, the
// Runtime allocates nothing and takes no locks.
namespace VoiceMod
{
   constexpr int kMaxSources = 8;
   constexpr int kMaxRoutes = 16;
   constexpr int kMaxPoints = 32;

   enum Kind
   {
      kNone = 0,
      kLfo,
      kRandom,
      kMseg,
      kSpread // a fixed value per note, by its place among the held notes
   };

   // One modulator, as data.
   struct Spec
   {
      int kind = kNone;
      uint64_t id = 0; // the modulator node's uid: a plan that keeps it keeps its voices' state
      // Rate: Hz mode runs `rateHz` cycles a second; otherwise one cycle every
      // `periodBeats` beats at the current tempo (Synced already resolved).
      bool hz = false;
      float rateHz = 1.0f;
      double periodBeats = 1.0;
      float low = 0.0f;
      float high = 1.0f;
      uint64_t salt = 0; // the node's seed (ModShapes::SeedSalt), mixed with each note's serial
      // LFO
      int shape = 0;
      float phase = 0.0f;
      // Random
      float smooth = 0.0f;
      // MSEG
      bool loop = false;
      float loopStart = 0.0f;
      float loopEnd = 1.0f;
      int numPoints = 0;
      ModShapes::MsegPoint points[kMaxPoints];
      // Voice Spread (shape = ModShapes::SpreadMode)
      int count = 4;
   };

   // One binding: source -> one of the synth's voice params, shaped exactly
   // as CookFrame shapes the shared value (curve, smoothing, lo/hi, snap).
   struct Route
   {
      int source = 0;
      int param = -1;
      float lo = 0.0f;
      float hi = 1.0f;
      float curve = 0.0f;
      float smoothMs = 0.0f;
      float minValue = 0.0f;
      float maxValue = 1.0f;
      float step = 0.0f;
   };

   struct Plan
   {
      int numSources = 0;
      Spec sources[kMaxSources];
      int numRoutes = 0;
      Route routes[kMaxRoutes];
   };

   // A modulator that can run per voice. Main thread. False while its
   // switch is off (the binding then stays on the shared path).
   class IVoiceModSource
   {
   public:
      virtual ~IVoiceModSource() {}
      virtual bool VoiceSpec(Spec& out) = 0;
   };

   // A synth whose voices take per-voice modulation. Main thread.
   class IVoiceModTarget
   {
   public:
      virtual ~IVoiceModTarget() {}
      // The voice param that the control editing `member` drives, or -1 when
      // that control acts on the whole instrument.
      virtual int VoiceParamFor(const float* member) const = 0;
      virtual void PublishVoicePlan(const Plan& plan) = 0;
   };

   // Single writer (main), single reader (audio). The reader always sees a
   // whole plan, the latest one published.
   class PlanBox
   {
   public:
      void Publish(const Plan& plan)
      {
         mSlots[mWrite] = plan;
         mWrite = mShared.exchange(mWrite | kDirty, std::memory_order_acq_rel) & kIndex;
      }

      const Plan& Acquire()
      {
         if (mShared.load(std::memory_order_acquire) & kDirty)
            mRead = mShared.exchange(mRead, std::memory_order_acq_rel) & kIndex;
         return mSlots[mRead];
      }

   private:
      static constexpr int kDirty = 4;
      static constexpr int kIndex = 3;
      Plan mSlots[3];
      std::atomic<int> mShared { 1 };
      int mWrite = 0; // main thread
      int mRead = 2;  // audio thread
   };

   // Per-voice state for one synth. kVoices = the synth's voice count.
   template <int kVoices>
   class Runtime
   {
   public:
      void Prepare(double sampleRate) { mSampleRate = sampleRate > 0.0 ? sampleRate : 48000.0; }

      // Audio thread, top of each block.
      void BeginBlock(PlanBox& box, double bpm)
      {
         mPlan = &box.Acquire();
         const double beatsPerSecond = std::max(1.0, bpm) / 60.0;
         for (int s = 0; s < mPlan->numSources; s++)
         {
            const Spec& sp = mPlan->sources[s];
            if (sp.id != mIds[s] || sp.kind != mKinds[s])
            {
               // A new modulator in this slot: held voices start it now.
               mIds[s] = sp.id;
               mKinds[s] = sp.kind;
               for (int v = 0; v < kVoices; v++)
                  Restart(mSrc[v][s], mSrc[v][s].gate);
            }
            const double perSecond = sp.hz ? (double)std::max(0.001f, sp.rateHz) : beatsPerSecond / std::max(1.0e-3, sp.periodBeats);
            mInc[s] = perSecond / mSampleRate;
         }
         for (int r = 0; r < mPlan->numRoutes; r++)
         {
            const float ms = mPlan->routes[r].smoothMs;
            mRouteA[r] = ms > 0.0f ? (float)std::exp(-1000.0 / ((double)ms * mSampleRate)) : 0.0f;
         }
      }

      bool Active() const { return mPlan != nullptr && mPlan->numRoutes > 0; }

      void NoteOn(int voice)
      {
         if (voice < 0 || voice >= kVoices)
            return;
         // Its place among the keys held now: a chord counts 0, 1, 2...
         int index = 0;
         for (int v = 0; v < kVoices; v++)
            index += v != voice && mHeld[v] ? 1 : 0;
         mHeld[voice] = true;
         for (int s = 0; s < kMaxSources; s++)
         {
            Restart(mSrc[voice][s], true);
            mSrc[voice][s].serial = ++mSerial;
            mSrc[voice][s].index = index;
         }
         for (int r = 0; r < kMaxRoutes; r++)
            mRoute[voice][r].primed = false;
      }

      void NoteOff(int voice)
      {
         if (voice < 0 || voice >= kVoices)
            return;
         mHeld[voice] = false;
         for (int s = 0; s < kMaxSources; s++)
            mSrc[voice][s].gate = false;
      }

      // One sample of one sounding voice: advances its sources and calls
      // write(param, value) for every route, in the param's own units.
      template <class Write>
      void Apply(int voice, Write&& write)
      {
         if (!Active() || voice < 0 || voice >= kVoices)
            return;
         float value[kMaxSources];
         for (int s = 0; s < mPlan->numSources; s++)
            value[s] = Step(mPlan->sources[s], mSrc[voice][s], mInc[s]);
         for (int r = 0; r < mPlan->numRoutes; r++)
         {
            const Route& rt = mPlan->routes[r];
            if (rt.source < 0 || rt.source >= mPlan->numSources)
               continue;
            float v = std::clamp(value[rt.source], 0.0f, 1.0f);
            if (std::fabs(rt.curve) >= 0.0001f)
               v = std::pow(v, std::exp2(rt.curve * 3.0f));
            RouteState& st = mRoute[voice][r];
            if (!st.primed || mRouteA[r] <= 0.0f)
               st.y = v;
            else
               st.y = v + (st.y - v) * mRouteA[r];
            st.primed = true;
            float out = rt.lo + (rt.hi - rt.lo) * std::clamp(st.y, 0.0f, 1.0f);
            if (rt.step > 0.0f)
               out = std::round(out / rt.step) * rt.step;
            write(rt.param, std::clamp(out, rt.minValue, rt.maxValue));
         }
      }

      // Tests: the unshaped value of `source` for `voice` at its current position.
      float Peek(int voice, int source) const
      {
         if (mPlan == nullptr || source < 0 || source >= mPlan->numSources || voice < 0 || voice >= kVoices)
            return 0.0f;
         return Value(mPlan->sources[source], mSrc[voice][source]);
      }

   private:
      struct SourceState
      {
         double pos = 0.0; // cycles (LFO, Random) or shape-lengths (MSEG) since note-on
         double x = 1.0;   // MSEG position; at rest on the last value
         bool gate = false;
         bool released = true;
         uint64_t serial = 0;
         int index = 0; // place among the held notes at note-on (Voice Spread)
      };

      struct RouteState
      {
         float y = 0.0f;
         bool primed = false;
      };

      static void Restart(SourceState& st, bool gate)
      {
         st.pos = 0.0;
         st.x = gate ? 0.0 : 1.0;
         st.gate = gate;
         st.released = !gate;
      }

      static float Value(const Spec& sp, const SourceState& st)
      {
         const uint64_t salt = sp.salt ^ ModShapes::Mix64(st.serial);
         switch (sp.kind)
         {
            case kLfo:
               return ModShapes::Remap(ModShapes::Lfo(sp.shape, st.pos + (double)sp.phase, 1, salt), sp.low, sp.high);
            case kRandom:
            {
               const long long step = (long long)std::floor(st.pos);
               const float cur = ModShapes::HashSeeded(step, salt);
               const float next = sp.smooth > 0.0f ? ModShapes::HashSeeded(step + 1, salt) : cur;
               return ModShapes::Remap(ModShapes::RandomGlide(cur, next, ModShapes::Frac(st.pos), sp.smooth), sp.low, sp.high);
            }
            case kMseg:
               return std::clamp(ModShapes::MsegEvaluate(sp.points, sp.numPoints, (float)st.x), 0.0f, 1.0f);
            case kSpread:
               return ModShapes::Remap(ModShapes::Spread(sp.shape, st.index, sp.count), sp.low, sp.high);
            default:
               return 0.0f;
         }
      }

      // Value now, then advance one sample.
      static float Step(const Spec& sp, SourceState& st, double inc)
      {
         const float v = Value(sp, st);
         st.pos += inc;
         if (sp.kind == kMseg)
            st.x = ModShapes::MsegStep(st.x, inc, st.gate, st.released, sp.loop, sp.loopStart, sp.loopEnd);
         return v;
      }

      const Plan* mPlan = nullptr;
      double mSampleRate = 48000.0;
      uint64_t mSerial = 0;
      uint64_t mIds[kMaxSources] = {};
      int mKinds[kMaxSources] = {};
      double mInc[kMaxSources] = {};
      float mRouteA[kMaxRoutes] = {};
      bool mHeld[kVoices] = {};
      SourceState mSrc[kVoices][kMaxSources];
      RouteState mRoute[kVoices][kMaxRoutes];
   };
}
