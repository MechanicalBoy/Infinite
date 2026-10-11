// INFINITE_MODAUDIT: a measurement audit of every modulator (IModulator).
//
// The control-signal twin of FXAUDIT and IMGAUDIT. Each section drives the
// real nodes off the real Transport (live sample clock, offline render clock,
// or the no-audio fallback), so "is this as accurate as Bitwig / Ableton /
// Serum" is a table, not an opinion (docs/plans/modulation/README.md):
//
//   CLOCK     Beats() vs exact sample arithmetic over 10 minutes: live audio
//             clock at several rates/blocks/tempos, a tempo change, a loop,
//             a seek, the offline clock, and the no-audio Tick fallback.
//             Drift in samples.
//   SHAPE     LFO shapes, Remap and phase against the analytic formula (near
//             0 and at beat 1e5), the phase origin of each shape, S&H hold,
//             Vibrato against sin(2 pi f t), Random/Pattern smooth continuity.
//   QUANT     each MusicTime division as an LFO rate: does the slider reach
//             it, and how far does float storage drift the phase in 10 min.
//   ZIPPER    the delivery path to an audio destination as it runs today -
//             one Value01() per UI frame, read on the block-quantised audio
//             clock, pushed to ParamMailbox's 5 ms DspMath::OnePole - vs the
//             ideal per-sample curve. "excess" = worst per-sample step beyond
//             the ideal curve's own step, as a fraction of range.
//             (Real Transport, real nodes, real OnePole; only the frame and
//             block scheduling is modelled.)
//   VIDEO     value on each 60 fps frame live (clock read between audio
//             blocks) vs offline (exact video time): render - realtime gap,
//             and bit-exactness where both clocks sit on the same sample.
//   FRATE     stateful nodes run offline at 24..144 fps vs a 1440 fps
//             reference, compared at shared instants: frame-rate dependence.
//   ENV       Envelope ADSR stage times (ms) at 48 kHz-resolution and at
//             60 fps, its output levels; Audio to CV follower time constants.
//   SEEK      seek / loop wrap / tempo change behaviour of pure and stateful
//             nodes.
//   IDEM      1 vs 8 Value01() calls per frame (new-modulator-node 2).
//   SEED      same seed = same output; distinct spawns differ; LFO S&H.
//   CPU       ns per Value01() for every registered modulator, plus its
//             output range over a 4 s run.
//
// Only hard invariants fail the run (non-finite output, or a clamped node
// leaving 0..1). Everything else is reported, with FLAG lines past the
// success-metric thresholds, for a person to triage against the baseline.
#include "app/AppShared.h"
#include "audio/AudioBuffer.h"
#include "audio/DspMath.h"
#include "audio/MusicTime.h"
#include "nodes/MacroNodes.h"
#include "nodes/MidiNodes.h"
#include "nodes/ModulatorNodes.h"
#include "nodes/NoteNodes.h"
#include "nodes/OscNodes.h"
#include "nodes/PathNode.h"
#include "nodes/PredictionNodes.h"
#include "nodes/PredictiveModulatorNode.h"
#include "nodes/GeometryTableNode.h"

#include <chrono>
#include <cmath>
#include <cstring>
#include <functional>
#include <memory>
#include <vector>

namespace app
{
namespace
{
   // Success metrics (docs/plans/modulation/README.md section 4).
   constexpr double kDriftLimitSamples = 1.0;
   constexpr double kStepLimit = 1.0 / 1024.0;
   constexpr double kShapeLimit = 1e-4;
   constexpr double kStatefulLimit = 1e-4;
   constexpr double kSr = 48000.0;
   constexpr double kTwoPi = 6.283185307179586;

   struct Flags
   {
      int count = 0;
      void Add(const char* section, const std::string& who, const char* what, double v)
      {
         printf("MODAUDIT FLAG %-7s %-22s %-14s %.4g\n", section, who.c_str(), what, v);
         count++;
      }
   };

   Transport& T() { return Transport::Instance(); }

   // Every section starts from a clean, stopped clock at time 0.
   void ResetClock(float bpm)
   {
      T().NotifyAudioEngineStopped();
      T().SetOfflineMode(false);
      T().SetLoop(false, 0.0, 0.0);
      T().SetPlaying(false);
      T().SetTempo(bpm);
      T().Seek(0.0); // commits the tempo and zeroes every offset
   }
   void StartLive(float bpm, double sr)
   {
      ResetClock(bpm);
      T().NotifyAudioEngineStarted(sr);
      T().SetPlaying(true);
   }
   void StartOffline(float bpm)
   {
      ResetClock(bpm);
      T().SetOfflineMode(true, kSr);
      T().SetPlaying(true);
      T().SetOfflineVideoTime(0.0);
   }
   void StartFallback(float bpm)
   {
      ResetClock(bpm);
      T().SetPlaying(true);
   }
   void At(double seconds) { T().SetOfflineVideoTime(seconds); }

   // A patched input driven by a function of transport seconds.
   struct FnMod : IModulator
   {
      std::function<float(double)> f;
      float Value01() override { return f(T().Seconds()); }
   };

   template <class N>
   std::unique_ptr<N> Make()
   {
      return std::unique_ptr<N>(static_cast<N*>(N::Create()));
   }

   double LfoRef(int shape, double t)
   {
      t -= std::floor(t);
      switch (shape)
      {
         case 0: return 0.5 + 0.5 * std::sin(t * kTwoPi);
         case 1: return t < 0.5 ? t * 2.0 : 2.0 - t * 2.0;
         case 2: return t;
         case 3: return 1.0 - t;
         default: return t < 0.5 ? 0.0 : 1.0;
      }
   }
   const char* kShapeName[] = { "sine", "triangle", "saw up", "saw down", "square", "S&H" };

   // ======================================================================== CLOCK
   void AuditClock(Flags& flags)
   {
      const double dur = 600.0;
      struct Case { double sr; int block; float bpm; };
      const Case cases[] = { { 48000, 512, 120.0f }, { 44100, 441, 128.0f }, { 96000, 1024, 174.0f }, { 48000, 128, 97.3f } };
      for (const Case& c : cases)
      {
         StartLive(c.bpm, c.sr);
         const long double bpm = (long double)T().Tempo();
         const long long total = (long long)(dur * c.sr);
         double worst = 0.0;
         for (long long n = 0; n < total;)
         {
            T().AdvanceAudioClock(c.block);
            n += c.block;
            const long double exact = (long double)n * bpm / (60.0L * c.sr);
            const double err = (double)std::fabs((long double)T().Beats() - exact) * 60.0 * c.sr / (double)bpm;
            worst = std::max(worst, err);
         }
         char who[64];
         std::snprintf(who, sizeof(who), "live %g/%d %gbpm", c.sr, c.block, (double)c.bpm);
         printf("MODAUDIT CLOCK %-26s drift %.3g samples over %.0f s\n", who, worst, dur);
         if (worst >= kDriftLimitSamples)
            flags.Add("CLOCK", who, "drift", worst);
      }

      // Tempo change half way: 120 -> 140 lands on the next block.
      {
         StartLive(120.0f, kSr);
         const int block = 512;
         const long long total = (long long)(dur * kSr);
         long long n = 0, n0 = -1;
         double worst = 0.0, jump = 0.0;
         while (n < total)
         {
            if (n0 < 0 && n >= total / 2)
            {
               const double before = T().Beats();
               T().SetTempo(140.0f);
               n0 = n;
               T().AdvanceAudioClock(block);
               n += block;
               jump = std::fabs(T().Beats() - before - block * 140.0 / 60.0 / kSr) * 60.0 * kSr / 140.0;
            }
            else
            {
               T().AdvanceAudioClock(block);
               n += block;
            }
            long double exact = (long double)n * 120.0L / (60.0L * kSr);
            if (n0 >= 0)
               exact = (long double)n0 * 120.0L / (60.0L * kSr) + (long double)(n - n0) * 140.0L / (60.0L * kSr);
            const double bpmNow = n0 >= 0 ? 140.0 : 120.0;
            worst = std::max(worst, (double)std::fabs((long double)T().Beats() - exact) * 60.0 * kSr / bpmNow);
         }
         printf("MODAUDIT CLOCK %-26s drift %.3g samples, jump at change %.3g samples\n", "tempo 120->140 @300 s", worst, jump);
         if (worst >= kDriftLimitSamples || jump >= kDriftLimitSamples)
            flags.Add("CLOCK", "tempo change", "drift/jump", std::max(worst, jump));
      }

      // Loop: 16 beats (block-aligned) and 3.7 beats (not).
      for (double loopEnd : { 16.0, 3.7 })
      {
         StartLive(120.0f, kSr);
         T().SetLoop(true, 0.0, loopEnd);
         const int block = 512;
         const long long total = (long long)(dur * kSr);
         double worst = 0.0;
         for (long long n = 0; n < total;)
         {
            T().AdvanceAudioClock(block);
            n += block;
            const long double lin = (long double)n * 120.0L / (60.0L * kSr);
            const double exact = (double)std::fmod(lin, (long double)loopEnd);
            double d = std::fabs(T().Beats() - exact);
            d = std::min(d, loopEnd - d);
            worst = std::max(worst, d * 60.0 * kSr / 120.0);
         }
         char who[48];
         std::snprintf(who, sizeof(who), "loop 0..%g beats", loopEnd);
         printf("MODAUDIT CLOCK %-26s drift %.3g samples over %.0f s\n", who, worst, dur);
         if (worst >= kDriftLimitSamples)
            flags.Add("CLOCK", who, "drift", worst);
      }

      // Seek while the audio clock runs.
      {
         StartLive(120.0f, kSr);
         for (int i = 0; i < 5000; i++)
            T().AdvanceAudioClock(512);
         T().SeekBeats(37.25);
         const double pending = T().Beats();
         T().AdvanceAudioClock(512);
         const double after = T().Beats();
         const double errPending = std::fabs(pending - 37.25) * 60.0 * kSr / 120.0;
         const double errAfter = std::fabs(after - (37.25 + 512.0 * 2.0 / kSr)) * 60.0 * kSr / 120.0;
         printf("MODAUDIT CLOCK %-26s pending %.3g samples, after block %.3g samples\n", "seek 37.25 beats live", errPending, errAfter);
         if (std::max(errPending, errAfter) >= kDriftLimitSamples)
            flags.Add("CLOCK", "seek live", "error", std::max(errPending, errAfter));
      }

      // Offline render clock: audio blocks and video frames.
      {
         StartOffline(120.0f);
         double worstA = 0.0, worstV = 0.0;
         const long long total = (long long)(dur * kSr);
         for (long long n = 0; n < total;)
         {
            T().BeginOfflineAudioBlock(512);
            n += 512;
            const long double exact = (long double)n * 2.0L / kSr;
            worstA = std::max(worstA, (double)std::fabs((long double)T().Beats() - exact) * 0.5 * kSr);
            T().EndOfflineAudioBlock();
         }
         StartOffline(120.0f);
         for (int k = 0; k <= (int)(dur * 30); k++)
         {
            At(k / 30.0);
            worstV = std::max(worstV, std::fabs(T().Beats() - 2.0 * k / 30.0) * 0.5 * kSr);
         }
         printf("MODAUDIT CLOCK %-26s audio drift %.3g samples, video drift %.3g samples\n", "offline", worstA, worstV);
         if (std::max(worstA, worstV) >= kDriftLimitSamples)
            flags.Add("CLOCK", "offline", "drift", std::max(worstA, worstV));
      }

      // No-audio fallback (Tick with the frame's float dt): accumulation
      // error against the long-double sum of the same dts.
      {
         StartFallback(120.0f);
         long double sum = 0.0L;
         for (int k = 0; k < (int)(dur * 60); k++)
         {
            const float dt = (k & 1) ? 1.0f / 59.0f : 1.0f / 61.0f;
            T().Tick(dt);
            sum += (long double)dt;
         }
         const double err = (double)std::fabs((long double)T().Beats() - sum * 2.0L) * 0.5 * kSr;
         printf("MODAUDIT CLOCK %-26s drift %.3g samples over %.0f s (wall-clock driven, not sample-locked)\n", "no-audio Tick fallback", err, dur);
         if (err >= kDriftLimitSamples)
            flags.Add("CLOCK", "Tick fallback", "drift", err);
      }
   }

   // ======================================================================== SHAPE
   double LfoAtBeats(LFONode& lfo, double beats)
   {
      T().SeekBeats(beats); // fallback clock: Beats() returns exactly this
      return lfo.Value01();
   }

   void AuditShapes(Flags& flags)
   {
      ResetClock(120.0f);
      const int N = 4096;
      for (int shape = 0; shape <= 4; shape++)
      {
         auto lfo = Make<LFONode>();
         lfo->shape = shape;
         lfo->rateBeats = 1.0f;
         double worst = 0.0, worstFar = 0.0, worstPhase = 0.0, worstRemap = 0.0;
         for (int i = 0; i < N; i++)
         {
            const double t = (i + 0.5) / N;
            worst = std::max(worst, std::fabs(LfoAtBeats(*lfo, t) - LfoRef(shape, t)));
            worstFar = std::max(worstFar, std::fabs(LfoAtBeats(*lfo, 1e5 + t) - LfoRef(shape, t)));
         }
         lfo->phase = 0.25f;
         for (int i = 0; i < N; i++)
         {
            const double t = (i + 0.5) / N;
            worstPhase = std::max(worstPhase, std::fabs(LfoAtBeats(*lfo, t) - LfoRef(shape, t + 0.25)));
         }
         lfo->phase = 0.0f;
         lfo->low = 0.2f;
         lfo->high = 0.7f;
         for (int i = 0; i < N; i++)
         {
            const double t = (i + 0.5) / N;
            worstRemap = std::max(worstRemap, std::fabs(LfoAtBeats(*lfo, t) - (0.2 + 0.5 * LfoRef(shape, t))));
         }
         lfo->low = 0.0f;
         lfo->high = 1.0f;
         const double v0 = LfoAtBeats(*lfo, 0.0);
         const double v1 = LfoAtBeats(*lfo, 1.0 / N);
         printf("MODAUDIT SHAPE LFO %-9s err %.2e, @beat 1e5 %.2e, phase .25 %.2e, low/high %.2e | origin %.3f %s\n",
                kShapeName[shape], worst, worstFar, worstPhase, worstRemap, v0,
                v1 > v0 ? "rising" : (v1 < v0 ? "falling" : "flat"));
         const double w = std::max(std::max(worst, worstFar), std::max(worstPhase, worstRemap));
         if (w > kShapeLimit)
            flags.Add("SHAPE", std::string("LFO ") + kShapeName[shape], "max err", w);
      }

      // S&H: holds within a cycle, moves between cycles.
      {
         auto lfo = Make<LFONode>();
         lfo->shape = 5;
         lfo->rateBeats = 1.0f;
         double drift = 0.0;
         int changes = 0;
         double prev = -1.0;
         for (int c = 0; c < 64; c++)
         {
            const double first = LfoAtBeats(*lfo, c + 0.001);
            for (int i = 1; i < 64; i++)
               drift = std::max(drift, std::fabs(LfoAtBeats(*lfo, c + i / 64.0) - first));
            if (prev >= 0.0 && first != prev)
               changes++;
            prev = first;
         }
         printf("MODAUDIT SHAPE LFO S&H     hold drift %.2e, new value on %d of 63 cycle edges\n", drift, changes);
      }

      // Vibrato: free-running Hz on Transport::Seconds().
      {
         StartOffline(120.0f);
         auto vib = Make<VibratoNode>();
         double worst = 0.0, worstFar = 0.0;
         for (int i = 0; i < 10000; i++)
         {
            const double s = i / 1000.0;
            At(s);
            worst = std::max(worst, std::fabs(vib->Value01() - (0.5 + 0.5 * std::sin(kTwoPi * vib->rateHz * s))));
            At(3600.0 + s);
            worstFar = std::max(worstFar, std::fabs(vib->Value01() - (0.5 + 0.5 * std::sin(kTwoPi * vib->rateHz * (3600.0 + s)))));
         }
         printf("MODAUDIT SHAPE Vibrato 5 Hz  err %.2e, @1 h %.2e\n", worst, worstFar);
         if (std::max(worst, worstFar) > kShapeLimit)
            flags.Add("SHAPE", "Vibrato", "max err", std::max(worst, worstFar));
         ResetClock(120.0f);
      }

      // Random / Pattern smooth: value and slope continuity, per beat.
      auto continuity = [](const std::function<double(double)>& f, double& valueJump, double& slopeJump) {
         const int perBeat = 8192;
         const double h = 1.0 / perBeat;
         valueJump = slopeJump = 0.0;
         double prevD = std::nan("");
         for (int i = 0; i < perBeat * 16; i++)
         {
            const double b = i * h;
            const double a = f(b), c = f(b + h);
            const double d = (c - a) / h; // slope per beat
            valueJump = std::max(valueJump, std::fabs(c - a));
            if (!std::isnan(prevD))
               slopeJump = std::max(slopeJump, std::fabs(d - prevD));
            prevD = d;
         }
      };
      for (float smooth : { 0.5f, 1.0f })
      {
         auto rnd = Make<RandomNode>();
         rnd->seed = 7.3f;
         rnd->rateBeats = 1.0f;
         rnd->smooth = smooth;
         double vj, sj;
         continuity([&](double b) { T().SeekBeats(b); return (double)rnd->Value01(); }, vj, sj);
         printf("MODAUDIT SHAPE Random smooth %.1f  max value step %.2e per 1/8192 beat, max slope jump %.3g /beat\n", smooth, vj, sj);
      }
      {
         auto rnd = Make<RandomNode>();
         rnd->seed = 7.3f;
         rnd->smooth = 0.0f;
         double vj, sj;
         continuity([&](double b) { T().SeekBeats(b); return (double)rnd->Value01(); }, vj, sj);
         printf("MODAUDIT SHAPE Random stepped    max value step %.3g (a stepped S&H, by design)\n", vj);
      }
      {
         auto pat = Make<PatternNode>();
         double worst = 0.0;
         for (int i = 0; i < pat->length; i++)
         {
            T().SeekBeats(i * pat->stepBeats + 0.5);
            worst = std::max(worst, (double)std::fabs(pat->Value01() - pat->steps[i]));
         }
         pat->smoothSteps = true;
         double vj, sj;
         continuity([&](double b) { T().SeekBeats(b); return (double)pat->Value01(); }, vj, sj);
         printf("MODAUDIT SHAPE Pattern          step value err %.2e | smooth: max value step %.2e, slope jump %.3g /beat\n", worst, vj, sj);
         if (worst > kShapeLimit)
            flags.Add("SHAPE", "Pattern", "step err", worst);
      }
   }

   // ======================================================================== QUANT
   void AuditQuant(Flags& flags)
   {
      // LFO/Random rate is a free float slider (ParamBodies1.cpp: 0.05..32
      // beats); nothing snaps it to MusicTime. What a user typing the
      // division in gets, stored as float, after 10 min at 120 bpm:
      const double beats10 = 1200.0;
      double worst = 0.0;
      int outOfRange = 0;
      for (int d = 0; d < MusicTime::kNumRateDivisions; d++)
      {
         const double exact = MusicTime::BeatsFor((MusicTime::RateDivision)d);
         const float stored = (float)exact;
         const bool inRange = stored >= 0.05f && stored <= 32.0f;
         if (!inRange)
            outOfRange++;
         const double cyclesErr = beats10 / (double)stored - beats10 / exact;
         const double samples = std::fabs(cyclesErr) * exact * 0.5 * kSr;
         worst = std::max(worst, samples);
         printf("MODAUDIT QUANT %-6s %8.5f beats  slider %s  float drift %.3g samples / 10 min\n",
                MusicTime::RateDivisionName(d), exact, inRange ? "ok " : "OUT", samples);
      }
      printf("MODAUDIT QUANT summary: %d divisions outside the LFO slider, worst float drift %.3g samples; no division snap offered\n", outOfRange, worst);
      if (worst >= kDriftLimitSamples)
         flags.Add("QUANT", "float rateBeats", "drift", worst);
      if (outOfRange > 0)
         flags.Add("QUANT", "LFO rate slider", "out of range", outOfRange);
   }

   // ======================================================================== ZIPPER
   struct PureSource
   {
      std::string name;
      std::function<std::unique_ptr<INode>()> make;
   };
   std::vector<PureSource> PureSources()
   {
      std::vector<PureSource> s;
      auto lfo = [](int shape, float rate) {
         return [shape, rate]() { auto n = Make<LFONode>(); n->shape = shape; n->rateBeats = rate; return std::unique_ptr<INode>(n.release()); };
      };
      s.push_back({ "LFO sine 1/4 beat", lfo(0, 0.25f) });
      s.push_back({ "LFO sine 1 beat", lfo(0, 1.0f) });
      s.push_back({ "LFO sine 4 beats", lfo(0, 4.0f) });
      s.push_back({ "LFO tri 1 beat", lfo(1, 1.0f) });
      s.push_back({ "Random smooth 1 beat", []() { auto n = Make<RandomNode>(); n->seed = 7.3f; n->smooth = 1.0f; return std::unique_ptr<INode>(n.release()); } });
      s.push_back({ "Pattern smooth", []() { auto n = Make<PatternNode>(); n->smoothSteps = true; return std::unique_ptr<INode>(n.release()); } });
      s.push_back({ "Vibrato 5 Hz", []() { return std::unique_ptr<INode>(Make<VibratoNode>().release()); } });
      return s;
   }
   IModulator* AsMod(INode* n) { return dynamic_cast<IModulator*>(n); }

   void AuditZipper(Flags& flags)
   {
      const double dur = 8.0;
      const int total = (int)(dur * kSr);
      struct Sched { int block; double fps; };
      const Sched scheds[] = { { 512, 60.0 }, { 128, 60.0 }, { 512, 144.0 } };
      for (const PureSource& src : PureSources())
      {
         // Ideal per-sample curve: the same pure node at each sample's exact time.
         std::vector<float> ideal(total);
         {
            StartOffline(120.0f);
            auto node = src.make();
            IModulator* m = AsMod(node.get());
            for (int n = 0; n < total; n++)
            {
               At(n / kSr);
               ideal[n] = m->Value01();
            }
         }
         for (const Sched& sc : scheds)
         {
            StartLive(120.0f, kSr);
            auto node = src.make();
            IModulator* m = AsMod(node.get());
            DspMath::OnePole smoother;
            smoother.SetTimeConstant(0.005f, kSr); // ParamMailbox::PrepareToPlay
            float target = m->Value01();
            smoother.SetImmediate(target);
            int nextFrame = 0;
            double excess = 0.0, sq = 0.0;
            float prevD = target;
            for (int j = 0; j * sc.block < total; j++)
            {
               const double callbackTime = (double)j * sc.block / kSr;
               while (nextFrame / sc.fps <= callbackTime)
               {
                  target = m->Value01(); // UI frame: modulation applied, pushed to the mailbox
                  nextFrame++;
               }
               T().AdvanceAudioClock(sc.block);
               for (int i = 0; i < sc.block; i++)
               {
                  const int n = j * sc.block + i;
                  if (n >= total)
                     break;
                  const float d = smoother.Process(target);
                  if (n > 0)
                     excess = std::max(excess, std::fabs((double)(d - prevD) - (double)(ideal[n] - ideal[n - 1])));
                  sq += (double)(d - ideal[n]) * (d - ideal[n]);
                  prevD = d;
               }
            }
            char who[64];
            std::snprintf(who, sizeof(who), "%s b%d %gfps", src.name.c_str(), sc.block, sc.fps);
            printf("MODAUDIT ZIPPER %-34s excess step %.2e (limit %.2e)  tracking rms %.3g\n", who, excess, kStepLimit, std::sqrt(sq / total));
            if (excess > kStepLimit)
               flags.Add("ZIPPER", src.name, "excess step", excess);
         }
      }
   }

   // ======================================================================== VIDEO
   void AuditVideo(Flags& flags)
   {
      const double dur = 10.0, fps = 60.0;
      const int frames = (int)(dur * fps);
      std::vector<PureSource> sources = PureSources();
      sources.push_back({ "Macro Step Gate", []() { return std::unique_ptr<INode>(Make<MacroStepGateNode>().release()); } });
      for (const PureSource& src : sources)
      {
         std::vector<float> offline(frames);
         {
            StartOffline(120.0f);
            auto node = src.make();
            for (int k = 0; k < frames; k++)
            {
               At(k / fps);
               offline[k] = AsMod(node.get())->Value01();
            }
         }
         double worst = 0.0, minOff = 1e9, maxOff = -1e9;
         {
            StartLive(120.0f, kSr);
            auto node = src.make();
            long long n = 0;
            for (int k = 0; k < frames; k++)
            {
               const double tw = k / fps;
               while ((double)n / kSr <= tw) // callbacks due by this frame's wall time
               {
                  T().AdvanceAudioClock(512);
                  n += 512;
               }
               const double off = (T().Seconds() - tw) * 1000.0;
               minOff = std::min(minOff, off);
               maxOff = std::max(maxOff, off);
               worst = std::max(worst, (double)std::fabs(AsMod(node.get())->Value01() - offline[k]));
            }
         }
         // Same sample on both clocks: bit-exact?
         int mismatches = 0;
         {
            auto a = src.make();
            auto b = src.make();
            for (int k = 1; k <= 200; k++)
            {
               const long long n = (long long)k * 512 * 7;
               StartLive(120.0f, kSr);
               for (long long done = 0; done < n; done += 512)
                  T().AdvanceAudioClock(512);
               const float live = AsMod(a.get())->Value01();
               StartOffline(120.0f);
               At((double)n / kSr);
               const float off = AsMod(b.get())->Value01();
               if (std::memcmp(&live, &off, sizeof(float)) != 0)
                  mismatches++;
            }
         }
         printf("MODAUDIT VIDEO %-22s render-realtime %.3g of range | live clock %+.1f..%+.1f ms off frame time | same-sample bit mismatches %d/200\n",
                src.name.c_str(), worst, minOff, maxOff, mismatches);
         if (worst > kShapeLimit)
            flags.Add("VIDEO", src.name, "render!=live", worst);
         if (mismatches > 0)
            flags.Add("VIDEO", src.name, "bit mismatch", mismatches);
      }
   }

   // ======================================================================== FRATE
   struct StatefulCase
   {
      std::string name;
      std::function<std::unique_ptr<INode>(FnMod*)> make;
      std::function<float(double)> input;
   };
   float StepInput(double s) { return s < 1.0 ? 0.2f : (s < 2.5 ? 0.8f : 0.4f); }
   float GateInput(double s) { return (s >= 0.5 && s < 2.0) ? 1.0f : 0.0f; }
   float SineInput(double s) { return (float)(0.5 + 0.5 * std::sin(kTwoPi * 1.3 * s)); }

   std::vector<StatefulCase> StatefulCases()
   {
      std::vector<StatefulCase> c;
      auto smooth = [](int mode) {
         return [mode](FnMod* in) { auto n = Make<SmoothNode>(); n->mode = mode; n->input = in; return std::unique_ptr<INode>(n.release()); };
      };
      c.push_back({ "Smooth per-frame (default)", smooth(SmoothNode::kPerFrame), StepInput });
      c.push_back({ "Smooth time 0.25 s", smooth(SmoothNode::kTime), StepInput });
      c.push_back({ "Smooth time, sine in", smooth(SmoothNode::kTime), SineInput });
      c.push_back({ "Smooth spring 3 Hz", smooth(SmoothNode::kSpring), StepInput });
      c.push_back({ "Envelope ADSR", [](FnMod* in) { auto n = Make<EnvelopeNode>(); n->input = in; return std::unique_ptr<INode>(n.release()); }, GateInput });
      c.push_back({ "CV to Pitch glide 100ms", [](FnMod* in) { auto n = Make<CVToPitchNode>(); n->glideMs = 100.0f; n->input = in; return std::unique_ptr<INode>(n.release()); }, StepInput });
      return c;
   }

   // Runs a stateful case offline at fps for 4 s, calling Value01() `calls`
   // times per frame; returns the value at every 1/6 s checkpoint.
   std::vector<float> RunAtFps(const StatefulCase& sc, double fps, int calls = 1)
   {
      StartOffline(120.0f);
      FnMod in;
      in.f = sc.input;
      auto node = sc.make(&in);
      IModulator* m = AsMod(node.get());
      std::vector<float> out;
      const int perCheck = (int)std::lround(fps / 6.0);
      for (int k = 0; k <= (int)std::lround(4.0 * fps); k++)
      {
         At(k / fps);
         float v = 0.0f;
         for (int c = 0; c < calls; c++)
            v = m->Value01();
         if (k % perCheck == 0)
            out.push_back(v);
      }
      return out;
   }

   void AuditFrameRate(Flags& flags)
   {
      for (const StatefulCase& sc : StatefulCases())
      {
         const std::vector<float> ref = RunAtFps(sc, 1440.0);
         printf("MODAUDIT FRATE %-27s", sc.name.c_str());
         double worstAll = 0.0;
         for (double fps : { 24.0, 30.0, 60.0, 120.0, 144.0 })
         {
            const std::vector<float> got = RunAtFps(sc, fps);
            double worst = 0.0;
            for (size_t i = 0; i < std::min(ref.size(), got.size()); i++)
               worst = std::max(worst, (double)std::fabs(got[i] - ref[i]));
            worstAll = std::max(worstAll, worst);
            printf(" %g:%.3g", fps, worst);
         }
         printf("  (max diff vs 1440 fps)\n");
         if (worstAll > kStatefulLimit)
            flags.Add("FRATE", sc.name, "fps dependence", worstAll);
      }
   }

   // ======================================================================== ENV
   void AuditEnvelope(Flags& flags)
   {
      for (double rate : { kSr, 60.0 })
      {
         StartOffline(120.0f);
         FnMod in;
         in.f = GateInput;
         auto env = Make<EnvelopeNode>();
         env->input = &in;
         double attackEnd = -1, decayEnd = -1, releaseEnd = -1;
         float rest = -1, peak = 0, sustainOut = 0, releaseMin = 1;
         for (long long k = 0; k <= (long long)(3.0 * rate); k++)
         {
            const double s = k / rate;
            At(s);
            const float out = env->Value01();
            const float gate = GateInput(s);
            const float level = gate > 0.5f ? (out - 0.5f) * 2.0f : (0.5f - out) * 2.0f;
            if (s < 0.5 && rest < 0)
               rest = out;
            peak = std::max(peak, out);
            if (s >= 0.5 && s < 2.0)
            {
               if (attackEnd < 0 && level >= 0.9999f)
                  attackEnd = s;
               if (attackEnd >= 0 && decayEnd < 0 && level <= env->sustainLevel + 1e-4f)
                  decayEnd = s;
               if (s > 1.9)
                  sustainOut = out;
            }
            if (s >= 2.0)
            {
               releaseMin = std::min(releaseMin, out);
               if (releaseEnd < 0 && level <= 1e-4f)
                  releaseEnd = s;
            }
         }
         const double aMs = (attackEnd - 0.5) * 1000.0, dMs = (decayEnd - attackEnd) * 1000.0, rMs = (releaseEnd - 2.0) * 1000.0;
         printf("MODAUDIT ENV   Envelope @%-6g attack %.2f ms (set %.0f) decay %.2f ms (set %.0f) release %.2f ms (set %.0f) | out: rest %.3f peak %.3f sustain %.3f release-min %.3f\n",
                rate, aMs, env->attackMs, dMs, env->decayMs, rMs, env->releaseMs, rest, peak, sustainOut, releaseMin);
         auto check = [&](const char* what, double got, double want) {
            const double tol = std::max(0.01 * want, 1000.0 / kSr);
            if (std::fabs(got - want) > tol)
               flags.Add("ENV", rate == kSr ? "Envelope @48k" : "Envelope @60fps", what, got - want);
         };
         check("attack ms", aMs, env->attackMs);
         check("decay ms", dMs, env->decayMs);
         check("release ms", rMs, env->releaseMs);
         if (rate == kSr && (std::fabs(rest) > 1e-4f || releaseMin < rest - 1e-4f))
            flags.Add("ENV", "Envelope output", "rest/dip", releaseMin);
      }

      // Audio to CV follower: DC step 0 -> 1 -> 0, time to 63.2% / 36.8%.
      {
         auto cv = Make<AudioToCVNode>();
         cv->CookIfNeeded(1); // pushes params
         AudioNode* an = cv->AudioNodeForNotePorts();
         an->PrepareToPlay(kSr, 64);
         std::vector<float> l(64), r(64), outL(64), outR(64);
         float* inCh[2] = { l.data(), r.data() };
         float* outCh[2] = { outL.data(), outR.data() };
         AudioBuffer inBuf{ inCh, 2, 64 }, outBuf{ outCh, 2, 64 };
         const AudioBuffer* ins[1] = { &inBuf };
         auto runUntil = [&](float level, std::function<bool(float)> done) {
            std::fill(l.begin(), l.end(), level);
            std::fill(r.begin(), r.end(), level);
            for (int blocks = 0; blocks < 48000; blocks++)
            {
               an->ProcessBlock(ins, 1, outBuf);
               if (done(cv->RawEnvelope()))
                  return (blocks + 1) * 64 * 1000.0 / kSr;
            }
            return -1.0;
         };
         const double att = runUntil(1.0f, [](float e) { return e >= 0.632f; });
         runUntil(1.0f, [](float e) { return e >= 0.9999f; });
         const double rel = runUntil(0.0f, [](float e) { return e <= 0.368f; });
         printf("MODAUDIT ENV   Audio to CV  attack tau %.2f ms (set %.1f), release tau %.2f ms (set %.1f), 64-sample resolution; delivered to params once per UI frame\n",
                att, cv->attackMs, rel, cv->releaseMs);
         if (std::fabs(att - cv->attackMs) > std::max(0.01 * cv->attackMs, 64000.0 / kSr))
            flags.Add("ENV", "Audio to CV", "attack ms", att - cv->attackMs);
         if (std::fabs(rel - cv->releaseMs) > std::max(0.01 * cv->releaseMs, 64000.0 / kSr))
            flags.Add("ENV", "Audio to CV", "release ms", rel - cv->releaseMs);
      }
   }

   // ======================================================================== SEEK
   void AuditSeek(Flags& flags)
   {
      // Pure nodes: a jump lands exactly where a fresh node would be.
      for (const PureSource& src : PureSources())
      {
         StartOffline(120.0f);
         auto a = src.make();
         auto b = src.make();
         double worst = 0.0;
         for (int i = 0; i < 100; i++)
         {
            At(i * 0.37);
            AsMod(a.get())->Value01();
            const double t2 = std::fmod(i * 1.913, 30.0);
            At(t2);
            const float va = AsMod(a.get())->Value01();
            const float vb = AsMod(b.get())->Value01();
            worst = std::max(worst, (double)std::fabs(va - vb));
         }
         printf("MODAUDIT SEEK  %-22s jump vs fresh node %.2e\n", src.name.c_str(), worst);
         if (worst > 0.0)
            flags.Add("SEEK", src.name, "seek err", worst);
      }

      // Envelope: seek back inside the attack while the gate stays open.
      {
         StartOffline(120.0f);
         FnMod in;
         in.f = GateInput;
         auto env = Make<EnvelopeNode>();
         env->input = &in;
         for (int k = 0; k <= 727; k++) // 1440 fps to 0.505 s
         {
            At(k / 1440.0);
            env->Value01();
         }
         const float before = env->Value01();
         At(0.501);
         const float after = env->Value01();
         printf("MODAUDIT SEEK  Envelope back 4 ms in attack: out %.3f -> %.3f (stage time recomputed from gate-on: follows the clock)\n", before, after);
         if (after < 0.5f)
            flags.Add("SEEK", "Envelope", "back-seek out", after);
      }
      // Smooth time: seek back snaps to the input.
      {
         StartOffline(120.0f);
         FnMod in;
         in.f = StepInput;
         auto sm = Make<SmoothNode>();
         sm->mode = SmoothNode::kTime;
         sm->input = &in;
         for (int k = 0; k <= 66; k++)
         {
            At(1.0 + k / 60.0);
            sm->Value01();
         }
         const float before = sm->Value01();
         At(1.05);
         const float after = sm->Value01();
         printf("MODAUDIT SEEK  Smooth time back-seek: %.3f -> %.3f (snaps to input %.3f)\n", before, after, StepInput(1.05));
      }

      // Loop wrap with a live clock: 1-beat LFO stays continuous; a 3-beat
      // LFO in a 4-beat loop jumps (phase follows the transport, as Bitwig Sync).
      for (float rate : { 1.0f, 3.0f })
      {
         StartLive(120.0f, kSr);
         T().SetLoop(true, 0.0, 4.0);
         auto lfo = Make<LFONode>();
         lfo->rateBeats = rate;
         float prev = lfo->Value01();
         double normal = 0.0, atWrap = 0.0;
         double prevBeats = T().Beats();
         for (int j = 0; j < 2000; j++)
         {
            T().AdvanceAudioClock(512);
            const float v = lfo->Value01();
            const bool wrapped = T().Beats() < prevBeats;
            const double d = std::fabs(v - prev);
            if (wrapped)
               atWrap = std::max(atWrap, d);
            else
               normal = std::max(normal, d);
            prev = v;
            prevBeats = T().Beats();
         }
         printf("MODAUDIT SEEK  LFO %g beat(s), loop 0..4: per-block step %.3g normally, %.3g at the wrap\n", rate, normal, atWrap);
      }

      // Tempo change: LFO phase continuous across it.
      {
         StartLive(120.0f, kSr);
         auto lfo = Make<LFONode>();
         lfo->rateBeats = 1.0f;
         lfo->shape = 2; // saw: value = phase
         double maxNormal = 0.0, atChange = 0.0;
         float prev = lfo->Value01();
         for (int j = 0; j < 2000; j++)
         {
            if (j == 1000)
               T().SetTempo(90.0f);
            T().AdvanceAudioClock(512);
            const float v = lfo->Value01();
            double d = v - prev;
            if (d < -0.5)
               d += 1.0; // saw wrap
            if (j == 1000)
               atChange = d;
            else if (j < 1000)
               maxNormal = std::max(maxNormal, d);
            prev = v;
         }
         const double expected = 512.0 / kSr * 90.0 / 60.0;
         printf("MODAUDIT SEEK  tempo 120->90: phase step %.6f at the change (expected %.6f at the new tempo, %.6f before)\n", atChange, expected, maxNormal);
         if (std::fabs(atChange - expected) > 1.0 / kSr)
            flags.Add("SEEK", "tempo change", "phase jump", atChange - expected);
      }
   }

   // ======================================================================== IDEM
   void AuditIdempotency(Flags& flags)
   {
      for (const StatefulCase& sc : StatefulCases())
      {
         const std::vector<float> one = RunAtFps(sc, 60.0, 1);
         const std::vector<float> eight = RunAtFps(sc, 60.0, 8);
         double worst = 0.0;
         for (size_t i = 0; i < one.size(); i++)
            worst = std::max(worst, (double)std::fabs(one[i] - eight[i]));
         printf("MODAUDIT IDEM  %-27s 1 vs 8 calls per frame: %.2e\n", sc.name.c_str(), worst);
         if (worst > 0.0)
            flags.Add("IDEM", sc.name, "fan-out diff", worst);
      }
   }

   // ======================================================================== SEED
   void AuditSeed(Flags& flags)
   {
      ResetClock(120.0f);
      auto seq = [](IModulator* m, int steps) {
         std::vector<float> v;
         for (int i = 0; i < steps; i++)
         {
            T().SeekBeats(i + 0.5);
            v.push_back(m->Value01());
         }
         return v;
      };
      auto a = Make<RandomNode>(), b = Make<RandomNode>();
      a->seed = b->seed = 3.0f;
      const bool same = seq(a.get(), 1000) == seq(b.get(), 1000);
      auto c = Make<RandomNode>(), d = Make<RandomNode>(); // two spawns: NextSeed
      const bool spawnsDiffer = seq(c.get(), 1000) != seq(d.get(), 1000);
      auto e = Make<RandomNode>(), f = Make<RandomNode>();
      e->seed = 1.0f;
      f->seed = 1.0005f;
      const bool nearSeedsCollide = seq(e.get(), 1000) == seq(f.get(), 1000);
      auto l1 = Make<LFONode>(), l2 = Make<LFONode>();
      l1->shape = l2->shape = 5;
      const bool shLockstep = seq(l1.get(), 1000) == seq(l2.get(), 1000);
      printf("MODAUDIT SEED  Random same seed same output: %s | two spawns differ: %s | seeds 1.0 vs 1.0005 collide: %s | two LFO S&H identical (no seed): %s\n",
             same ? "yes" : "NO", spawnsDiffer ? "yes" : "NO", nearSeedsCollide ? "YES" : "no", shLockstep ? "YES" : "no");
      if (!same)
         flags.Add("SEED", "Random", "same seed", 0);
      if (!spawnsDiffer)
         flags.Add("SEED", "Random", "spawns equal", 0);
      if (nearSeedsCollide)
         flags.Add("SEED", "Random", "seed collision", 1.0005);
      if (shLockstep)
         flags.Add("SEED", "LFO S&H", "lockstep", 1);

      // Offline render twice: every stateful case reproduces bit for bit.
      int diffs = 0;
      for (const StatefulCase& sc : StatefulCases())
         if (RunAtFps(sc, 60.0) != RunAtFps(sc, 60.0))
            diffs++;
      printf("MODAUDIT SEED  offline run twice, stateful cases differing: %d\n", diffs);
      if (diffs > 0)
         flags.Add("SEED", "offline rerun", "differs", diffs);
   }

   // ======================================================================== CPU
   struct Registered
   {
      const char* name;
      std::function<INode*()> create;
      bool clamped;
   };
   template <class N>
   Registered Reg(const char* name, bool clamped = true)
   {
      return { name, []() { return N::Create(); }, clamped };
   }

   bool AuditCpu(Flags& flags)
   {
      const Registered all[] = {
         Reg<LFONode>("LFO"), Reg<ConstantNode>("Constant"), Reg<RandomNode>("Random"), Reg<PatternNode>("Pattern"),
         Reg<MathNode>("Math"), Reg<CompareNode>("Compare"), Reg<RangeToRangeNode>("Range to Range", false),
         Reg<SmoothNode>("Smooth"), Reg<CVRecorderNode>("CV Recorder"), Reg<ModDepthNode>("Mod Depth"),
         Reg<EnvelopeNode>("Envelope"), Reg<CVToPitchNode>("CV to Pitch"), Reg<NullModulatorNode>("Null"),
         Reg<InvertNode>("Invert", false), Reg<ModCurveNode>("Mod Curve"), Reg<AudioToCVNode>("Audio to CV"),
         Reg<VibratoNode>("Vibrato"), Reg<NoteToCVNode>("Note to CV"), Reg<VelocityToCVNode>("Velocity to CV"),
         Reg<MacroKnobNode>("Macro Knob"), Reg<MacroXYNode>("Macro XY"), Reg<MacroSliderNode>("Macro Slider"),
         Reg<MacroBipolarKnobNode>("Macro Bipolar"), Reg<MacroToggleNode>("Macro Toggle"), Reg<MacroTriggerNode>("Macro Trigger"),
         Reg<MacroNumBoxNode>("Macro NumBox"), Reg<MacroRadioSelectorNode>("Macro Radio"), Reg<MacroStepGateNode>("Macro Step Gate"),
         Reg<MidiCCNode>("MIDI CC"), Reg<MidiTriggerNode>("MIDI Trigger"), Reg<OscReceiveNode>("OSC Receive"),
         Reg<PathNode>("Path"), Reg<GeometryTableNode>("Geometry Table"), Reg<DriftNode>("Drift"),
         Reg<MovesNode>("Moves"), Reg<PredictiveModulatorNode>("Predictive"),
      };
      bool ok = true;
      FnMod lfoIn;
      lfoIn.f = SineInput;
      for (const Registered& r : all)
      {
         std::unique_ptr<INode> node(r.create());
         IModulator* m = AsMod(node.get());
         if (m == nullptr)
         {
            printf("MODAUDIT CPU   %-16s not an IModulator?\n", r.name);
            continue;
         }
         // Patch an LFO-like input into slot 0 where there is one, so
         // transforms do real work.
         if (node->ModulatorInputCount() > 0)
            if (IModulator** slot = node->ModulatorInputSlot(0))
               *slot = &lfoIn;
         StartOffline(120.0f);
         float lo = 1e9f, hi = -1e9f;
         bool finite = true;
         const int calls = 200000;
         const auto t0 = std::chrono::steady_clock::now();
         for (int i = 0; i < calls; i++)
         {
            At(i * (4.0 / calls)); // 4 s, a new instant every call
            const float v = m->Value01();
            if (!std::isfinite(v))
               finite = false;
            lo = std::min(lo, v);
            hi = std::max(hi, v);
         }
         const double ns = std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count() / calls;
         // Subtract the clock store.
         printf("MODAUDIT CPU   %-16s %7.1f ns/call | range %.3f..%.3f%s\n", r.name, ns, lo, hi, finite ? "" : " NON-FINITE");
         if (!finite || (r.clamped && (lo < 0.0f || hi > 1.0f)))
         {
            printf("MODAUDIT FAIL  %s: %s\n", r.name, finite ? "left 0..1" : "non-finite output");
            ok = false;
         }
      }
      {
         StartOffline(120.0f);
         const int calls = 200000;
         volatile double sink = 0.0;
         const auto t0 = std::chrono::steady_clock::now();
         for (int i = 0; i < calls; i++)
         {
            At(i * (4.0 / calls));
            sink = sink + T().Beats();
         }
         const double ns = std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count() / calls;
         printf("MODAUDIT CPU   %-16s %7.1f ns/call (clock set + Beats(), included in every row above)\n", "(harness)", ns);
      }
      (void)flags;
      return ok;
   }
}

bool RunModAudit()
{
   Flags flags;
   const char* only = getenv("INFINITE_MODAUDIT_ONLY");
   auto want = [only](const char* s) { return only == nullptr || *only == 0 || std::strstr(only, s) != nullptr; };
   bool ok = true;
   if (want("CLOCK")) AuditClock(flags);
   if (want("SHAPE")) AuditShapes(flags);
   if (want("QUANT")) AuditQuant(flags);
   if (want("ZIPPER")) AuditZipper(flags);
   if (want("VIDEO")) AuditVideo(flags);
   if (want("FRATE")) AuditFrameRate(flags);
   if (want("ENV")) AuditEnvelope(flags);
   if (want("SEEK")) AuditSeek(flags);
   if (want("IDEM")) AuditIdempotency(flags);
   if (want("SEED")) AuditSeed(flags);
   if (want("CPU")) ok = AuditCpu(flags) && ok;
   ResetClock(120.0f);
   printf("MODAUDIT %d flags\n", flags.count);
   printf("MODAUDIT: %s\n", ok ? "PASS" : "FAIL");
   fflush(stdout);
   return ok;
}
} // namespace app
