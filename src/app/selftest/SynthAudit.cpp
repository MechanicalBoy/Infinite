// INFINITE_SYNTHAUDIT: a measurement audit of the pitched free-running synths.
//
// The oscillator twin of FXAUDIT and MODAUDIT (docs/plans/node-audits/README.md,
// block 1). Each synth runs through its real node -> audio node ProcessBlock at
// 256-frame blocks, free-running (no note cable) at a set frequency, and gets
// the same battery of numbers:
//
//   PITCH   fundamental error in cents (parabolic peak of a Blackman-Harris
//           FFT) at 110 / 440 / 1760 / 7040 Hz, at 44.1 / 48 / 96 kHz
//   ALIAS   energy at non-harmonic bins below 20 kHz re the fundamental, dB,
//           at 1.75 kHz and 5 kHz (the metric of ALIASTEST)
//   LEVEL   RMS and peak (dBFS) at defaults, 440 Hz
//   RATE    RMS spread (dB) of the 440 Hz level across the three rates
//   DET     two fresh nodes, same settings: bit-identical output
//   CPU     ns per stereo frame at defaults
//
// and, driven through a real NoteEventQueue (note cable) at defaults:
//
//   NOTE    note 69 pitch error in cents
//   ENV     attack (10..90% of the held peak) and release (note-off to -60 dB
//           re the held peak), ms
//   CLICK   worst second difference within 5 ms of note-on and of note-off,
//           dB re the steady-state worst (FXAUDIT threshold 12 dB)
//   VEL     RMS at velocity 0.25 / 0.5 re velocity 1, dB
//   POLY    1 / 4 / 8 / 32 simultaneous notes (flag: 4-note chord over 0 dBFS): peak, ns per frame, then all-off
//           and the level of the last 0.5 s of 10 s (stuck voices; -100 dBFS)
//
// Only hard invariants fail the run (non-finite output, silence at defaults).
// Everything else is reported, with FLAG lines past the thresholds below.
#include "app/AppShared.h"
#include "audio/AudioBuffer.h"
#include "audio/NoteEventQueue.h"
#include "audio/dsp/PortableFft.h"
#include "nodes/AnalogNode.h"
#include "nodes/DrumSequencerNode.h"
#include "nodes/EquationNode.h"
#include "nodes/FieldSynthNode.h"
#include "nodes/GrainMolderNode.h"
#include "nodes/GranularNode.h"
#include "nodes/ImageSpectralSynthNode.h"
#include "nodes/MolderNode.h"
#include "nodes/SamplerNode.h"
#include "nodes/WaveTerrainNode.h"
#include "nodes/MetallicNode.h"
#include "nodes/OscillatorNode.h"
#include "nodes/WavetableNode.h"

#include <chrono>

namespace app
{
namespace
{
   constexpr int kBlock = 256;
   constexpr int kLog2N = 16;
   constexpr int kN = 1 << kLog2N;
   constexpr int kLobe = 4;

   constexpr double kFlagPitchCents = 1.0;
   constexpr double kFlagAliasDb = -60.0;
   constexpr double kFlagPeakDbfs = 0.0;
   constexpr double kFlagRateDb = 1.0;
   constexpr double kFlagCpuNs = 4000.0;
   constexpr double kFlagClickDb = 12.0;
   constexpr double kFlagTailDbfs = -100.0;

   struct Synth
   {
      const char* name;
      bool pitched;                          // false: inharmonic, PITCH/ALIAS skipped
      std::function<INode*()> create;
      std::function<void(INode*, float)> setFreq;
      std::function<void(INode*)> quiet;     // analog drift / noise off, deterministic
   };

   const std::vector<Synth>& Synths()
   {
      static const std::vector<Synth> s = {
         { "Analog", true, [] { return AnalogNode::Create(); },
           [](INode* n, float f) { static_cast<AnalogNode*>(n)->freq = f; },
           [](INode* n) {
              auto* a = static_cast<AnalogNode*>(n);
              a->analog = false;
              a->filterType = kAFilterOff;
              a->voices = 1.0f;
              a->sub = 0.0f;
              a->noise = 0.0f;
           } },
         { "Wavetable", true, [] { return WavetableNode::Create(); },
           [](INode* n, float f) { static_cast<WavetableNode*>(n)->frequency = f; }, [](INode*) {} },
         { "Oscillator", true, [] { return OscillatorNode::Create(); },
           [](INode* n, float f) { static_cast<OscillatorNode*>(n)->frequency = f; }, [](INode*) {} },
         { "Equation Synth", true, [] { return EquationNode::Create(); },
           [](INode* n, float f) { static_cast<EquationNode*>(n)->frequency = f; }, [](INode*) {} },
         { "Metallic", false, [] { return MetallicNode::Create(); },
           [](INode* n, float f) { static_cast<MetallicNode*>(n)->frequency = f; }, [](INode*) {} },
         // Not pitch-driven (or need loaded content): level, rate, determinism, CPU, notes.
         { "Field Synth", false, [] { return FieldSynthNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Wave Terrain", false, [] { return WaveTerrainNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Spectral Synth", false, [] { return ImageSpectralSynthNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Grain Molder", false, [] { return GrainMolderNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Molder", false, [] { return MolderNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Granular", false, [] { return GranularNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Sampler", false, [] { return SamplerNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
         { "Drum Sequencer", false, [] { return DrumSequencerNode::Create(); }, [](INode*, float) {}, [](INode*) {} },
      };
      return s;
   }

   IAudioSource* AsSource(INode* n) { return dynamic_cast<IAudioSource*>(n); }

   // Renders `frames` of the left channel after a 0.3 s warm-up.
   bool Render(const Synth& s, double sr, float freq, int frames, std::vector<float>& out, bool quiet = true)
   {
      std::unique_ptr<INode> node(s.create());
      IAudioSource* src = AsSource(node.get());
      if (src == nullptr)
         return false;
      if (quiet)
         s.quiet(node.get());
      s.setFreq(node.get(), freq);
      AudioNode* an = src->GetAudioNode();
      an->PrepareToPlay(sr, kBlock);
      node->CookIfNeeded(1);
      std::vector<float> l(kBlock), r(kBlock);
      float* ch[2] = { l.data(), r.data() };
      AudioBuffer buf;
      buf.channels = ch;
      buf.numChannels = 2;
      buf.numFrames = kBlock;
      const int warm = (int)(0.3 * sr);
      out.clear();
      int done = 0;
      while ((int)out.size() < frames)
      {
         node->CookIfNeeded(2 + done / kBlock);
         an->ProcessBlock(nullptr, 0, buf);
         if (done >= warm)
            out.insert(out.end(), l.begin(), l.end());
         done += kBlock;
      }
      out.resize((size_t)frames);
      return true;
   }

   bool AllFinite(const std::vector<float>& x)
   {
      for (float v : x)
         if (!std::isfinite(v))
            return false;
      return true;
   }

   double Db(double x) { return 20.0 * std::log10(std::max(x, 1e-12)); }

   double Rms(const std::vector<float>& x)
   {
      double e = 0.0;
      for (float v : x)
         e += (double)v * v;
      return std::sqrt(e / (double)std::max<size_t>(x.size(), 1));
   }

   double Peak(const std::vector<float>& x)
   {
      double p = 0.0;
      for (float v : x)
         p = std::max(p, (double)std::fabs(v));
      return p;
   }

   std::vector<double> Spectrum(const std::vector<float>& x)
   {
      std::vector<float> w((size_t)kN);
      for (int i = 0; i < kN; i++)
      {
         const double t = 2.0 * M_PI * i / kN;
         w[(size_t)i] = (float)(x[(size_t)i] * (0.35875 - 0.48829 * std::cos(t) + 0.14128 * std::cos(2 * t) - 0.01168 * std::cos(3 * t)));
      }
      PortableFft::RealFft fft;
      fft.Prepare(kLog2N);
      std::vector<float> re((size_t)kN / 2), im((size_t)kN / 2);
      fft.Forward(w.data(), kLog2N, re.data(), im.data());
      std::vector<double> p((size_t)kN / 2);
      for (int k = 0; k < kN / 2; k++)
         p[(size_t)k] = (double)re[(size_t)k] * re[(size_t)k] + (double)im[(size_t)k] * im[(size_t)k];
      return p;
   }

   // Parabolic-interpolated peak near `hz`, returned in Hz.
   double PeakHz(const std::vector<double>& p, double hz, double sr)
   {
      const double bin = sr / kN;
      const int c = (int)std::lround(hz / bin);
      int best = c;
      for (int k = std::max(c - 3, 2); k <= std::min(c + 3, kN / 2 - 2); k++)
         if (p[(size_t)k] > p[(size_t)best])
            best = k;
      const double a = std::log(std::max(p[(size_t)best - 1], 1e-30));
      const double b = std::log(std::max(p[(size_t)best], 1e-30));
      const double g = std::log(std::max(p[(size_t)best + 1], 1e-30));
      const double d = 0.5 * (a - g) / (a - 2 * b + g);
      return (best + d) * bin;
   }

   // Non-harmonic energy below 20 kHz re the fundamental (dB).
   double AliasDb(const std::vector<double>& p, double hz, double sr)
   {
      const double bin = sr / kN;
      std::vector<char> harm((size_t)kN / 2, 0);
      for (int k = 0; k <= kLobe + 2; k++)
         harm[(size_t)k] = 1;
      for (int h = 1; h * hz < sr * 0.5 + 10 * bin; h++)
         for (int d = -kLobe - 1; d <= kLobe + 1; d++)
         {
            const int k = (int)std::lround(h * hz / bin) + d;
            if (k > 0 && k < kN / 2)
               harm[(size_t)k] = 1;
         }
      const int hi = std::min((int)(20000.0 / bin), kN / 2 - 1);
      double fund = 0.0, alias = 0.0;
      const int fk = (int)std::lround(hz / bin);
      for (int k = fk - kLobe; k <= fk + kLobe; k++)
         fund += p[(size_t)k];
      for (int k = 1; k <= hi; k++)
         if (!harm[(size_t)k])
            alias += p[(size_t)k];
      return 10.0 * std::log10(std::max(alias, 1e-30) / std::max(fund, 1e-30));
   }

   struct Flags
   {
      int n = 0;
      void Flag(const char* sec, const char* node, const char* what, double v)
      {
         printf("SYNTHAUDIT FLAG %-5s %-15s %s %.2f\n", sec, node, what, v);
         n++;
      }
   };

   // A synth wired to a NoteEventQueue the way the topology builder does.
   struct NoteRig
   {
      std::unique_ptr<INode> node;
      AudioNode* audio = nullptr;
      NoteEventQueue queue;
      double sr = 48000.0;
      int frame = 1;
      std::vector<float> l, r;
      std::vector<int> ids;

      bool Init(const Synth& s, double rate)
      {
         sr = rate;
         node.reset(s.create());
         IAudioSource* src = AsSource(node.get());
         if (src == nullptr)
            return false;
         s.quiet(node.get());
         audio = src->GetAudioNode();
         audio->PrepareToPlay(sr, kBlock);
         node->CookIfNeeded(frame++);
         const int cursor = queue.RegisterConsumer();
         int slot = 0;
         for (int i = 0; i < 8; i++)
            if (node->NoteInputSlot(i) != nullptr)
            {
               slot = i;
               break;
            }
         audio->SetNoteInbox(slot, &queue, cursor);
         l.assign(kBlock, 0.0f);
         r.assign(kBlock, 0.0f);
         return true;
      }
      int On(int note, float vel)
      {
         NoteEvent e;
         e.note = note;
         e.velocity = vel;
         e.isNoteOn = true;
         e.voiceId = NextVoiceId();
         queue.Push(e);
         return e.voiceId;
      }
      void Off(int note, int id)
      {
         NoteEvent e;
         e.note = note;
         e.isNoteOn = false;
         e.voiceId = id;
         queue.Push(e);
      }
      // Appends `frames` of the left channel (rounded up to whole blocks).
      void Run(int frames, std::vector<float>& out)
      {
         float* ch[2] = { l.data(), r.data() };
         AudioBuffer buf;
         buf.channels = ch;
         buf.numChannels = 2;
         buf.numFrames = kBlock;
         for (int done = 0; done < frames; done += kBlock)
         {
            node->CookIfNeeded(frame++);
            audio->ProcessBlock(nullptr, 0, buf);
            out.insert(out.end(), l.begin(), l.end());
         }
      }
   };

   // Peak of |x| over 1 ms windows.
   std::vector<double> Envelope(const std::vector<float>& x, double sr)
   {
      const size_t w = std::max<size_t>(1, (size_t)(sr * 0.001));
      std::vector<double> e;
      for (size_t i = 0; i + w <= x.size(); i += w)
      {
         double p = 0.0;
         for (size_t j = 0; j < w; j++)
            p = std::max(p, (double)std::fabs(x[i + j]));
         e.push_back(p);
      }
      return e;
   }

   double MaxD2(const std::vector<float>& x, size_t a, size_t b)
   {
      double m = 0.0;
      b = std::min(b, x.size());
      for (size_t i = std::max<size_t>(a, 2); i < b; i++)
         m = std::max(m, (double)std::fabs((double)x[i] - 2.0 * x[i - 1] + x[i - 2]));
      return m;
   }

   bool AuditNotes(const Synth& s, Flags& flags)
   {
      const double sr = 48000.0;
      const size_t hold = (size_t)(1.6 * sr);

      // Held note 69: pitch, envelope, click.
      {
         NoteRig rig;
         if (!rig.Init(s, sr))
            return false;
         std::vector<float> x;
         rig.Run(kBlock * 4, x); // silence before
         const size_t onAt = x.size();
         const int id = rig.On(69, 1.0f);
         rig.Run((int)hold, x);
         const size_t offAt = x.size();
         rig.Off(69, id);
         rig.Run((int)(10.0 * sr), x);
         if (!AllFinite(x))
         {
            printf("SYNTHAUDIT FAIL %-15s non-finite on a note\n", s.name);
            return false;
         }
         double sustain = 0.0;
         for (size_t i = onAt + hold / 2; i < offAt; i++)
            sustain = std::max(sustain, (double)std::fabs(x[i]));
         if (sustain < 1e-5)
         {
            printf("SYNTHAUDIT NOTE  %-15s SILENT on note 69%s\n", s.name,
                   s.pitched ? " (note cable has no effect)" : " (needs loaded content, not audited here)");
            if (s.pitched)
               flags.Flag("NOTE", s.name, "silent on note-on", 1.0);
            return true;
         }
         if (s.pitched && hold >= (size_t)kN)
         {
            std::vector<float> seg(x.begin() + (long)offAt - kN, x.begin() + (long)offAt);
            const double got = PeakHz(Spectrum(seg), 440.0, sr);
            const double cents = 1200.0 * std::log2(got / 440.0);
            printf("SYNTHAUDIT NOTE  %-15s note 69 pitch %+.2f cents\n", s.name, cents);
            if (std::fabs(cents) > kFlagPitchCents)
               flags.Flag("NOTE", s.name, "cents", cents);
         }
         const std::vector<double> env = Envelope(x, sr);
         const size_t eOn = onAt / (size_t)(sr * 0.001), eOff = offAt / (size_t)(sr * 0.001);
         double a10 = -1, a90 = -1, rel60 = -1;
         for (size_t i = eOn; i < eOff; i++)
         {
            if (a10 < 0 && env[i] >= 0.1 * sustain)
               a10 = (double)(i - eOn);
            if (a90 < 0 && env[i] >= 0.9 * sustain)
               a90 = (double)(i - eOn);
         }
         for (size_t i = eOff; i < env.size(); i++)
            if (env[i] < sustain * 0.001)
            {
               rel60 = (double)(i - eOff);
               break;
            }
         printf("SYNTHAUDIT ENV   %-15s attack %.0f ms | release to -60 dB %s%.0f ms\n", s.name,
                a10 >= 0 && a90 >= 0 ? a90 - a10 : -1.0, rel60 < 0 ? ">" : "", rel60 < 0 ? 10000.0 : rel60);
         const double steady = MaxD2(x, onAt + hold / 2, onAt + hold / 2 + (size_t)(0.1 * sr));
         const size_t w = (size_t)(0.005 * sr);
         const double cOn = Db(MaxD2(x, onAt, onAt + w) / std::max(steady, 1e-12));
         const double cOff = Db(MaxD2(x, offAt, offAt + w) / std::max(steady, 1e-12));
         printf("SYNTHAUDIT CLICK %-15s note-on %+.1f dB | note-off %+.1f dB re steady\n", s.name, cOn, cOff);
         if (cOn > kFlagClickDb)
            flags.Flag("CLICK", s.name, "note-on dB", cOn);
         if (cOff > kFlagClickDb)
            flags.Flag("CLICK", s.name, "note-off dB", cOff);
      }

      // Velocity.
      {
         double rms[3] = {};
         const float vel[3] = { 1.0f, 0.5f, 0.25f };
         for (int k = 0; k < 3; k++)
         {
            NoteRig rig;
            rig.Init(s, sr);
            std::vector<float> x;
            rig.On(69, vel[k]);
            rig.Run((int)(0.5 * sr), x);
            std::vector<float> seg(x.begin() + (long)(0.25 * sr), x.end());
            rms[k] = Rms(seg);
         }
         printf("SYNTHAUDIT VEL   %-15s vel 0.5 %+.1f dB | vel 0.25 %+.1f dB re vel 1\n", s.name,
                Db(rms[1] / std::max(rms[0], 1e-12)), Db(rms[2] / std::max(rms[0], 1e-12)));
      }

      // Polyphony and stuck voices.
      for (int n : { 1, 4, 8, 32 })
      {
         NoteRig rig;
         rig.Init(s, sr);
         std::vector<float> x;
         std::vector<int> notes, ids;
         for (int i = 0; i < n; i++)
         {
            notes.push_back(36 + i * 2);
            ids.push_back(rig.On(notes.back(), 0.8f));
         }
         rig.Run((int)(0.3 * sr), x);
         x.clear();
         const int blocks = 400;
         const auto t0 = std::chrono::steady_clock::now();
         rig.Run(blocks * kBlock, x);
         const double ns = std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count() /
                           ((double)blocks * kBlock);
         const double pk = Db(Peak(x));
         for (int i = 0; i < n; i++)
            rig.Off(notes[(size_t)i], ids[(size_t)i]);
         std::vector<float> tail;
         rig.Run((int)(10.0 * sr), tail);
         const bool fin = AllFinite(x) && AllFinite(tail);
         std::vector<float> last(tail.end() - (long)(0.5 * sr), tail.end());
         const double tl = Db(Peak(last));
         printf("SYNTHAUDIT POLY  %-15s %2d notes: peak %6.1f dBFS | %7.1f ns/frame | tail %7.1f dBFS%s\n", s.name, n, pk,
                ns, tl, fin ? "" : " NON-FINITE");
         if (!fin)
            return false;
         if (tl > kFlagTailDbfs)
            flags.Flag("POLY", s.name, "tail dBFS after all-off", tl);
         // A 4-note chord at velocity 0.8 must fit under 0 dBFS at defaults; 8 and
         // 32 notes are reported only (a polysynth sums its voices, see F5).
         if (n == 4 && pk > kFlagPeakDbfs)
            flags.Flag("POLY", s.name, "4-note chord peak dBFS", pk);
      }
      return true;
   }
}

bool RunSynthAudit()
{
   const char* only = getenv("INFINITE_SYNTHAUDIT_ONLY");
   auto want = [&](const char* sec) { return only == nullptr || *only == 0 || strstr(only, sec) != nullptr; };
   Flags flags;
   bool ok = true;
   const double rates[3] = { 44100.0, 48000.0, 96000.0 };
   const float notes[4] = { 110.0f, 440.0f, 1760.0f, 7040.0f };

   for (const Synth& s : Synths())
   {
      std::vector<float> x;
      if (!Render(s, 48000.0, 440.0f, kN, x))
      {
         printf("SYNTHAUDIT %-15s not an IAudioSource\n", s.name);
         ok = false;
         continue;
      }
      if (AllFinite(x) && Peak(x) < 1e-5 && !s.pitched && strcmp(s.name, "Metallic") != 0)
      {
         printf("SYNTHAUDIT SKIP %-15s silent at defaults (needs loaded content or a note)\n", s.name);
         if (want("NOTE") || want("POLY"))
            ok = AuditNotes(s, flags) && ok;
         continue;
      }
      if (!AllFinite(x) || Peak(x) < 1e-5)
      {
         printf("SYNTHAUDIT FAIL %-15s %s at defaults\n", s.name, AllFinite(x) ? "silent" : "non-finite");
         ok = false;
         continue;
      }

      if (want("LEVEL"))
      {
         const double pk = Db(Peak(x));
         printf("SYNTHAUDIT LEVEL %-15s rms %6.1f dBFS | peak %6.1f dBFS\n", s.name, Db(Rms(x)), pk);
         if (pk > kFlagPeakDbfs)
            flags.Flag("LEVEL", s.name, "peak dBFS", pk);
      }

      if (want("PITCH") && s.pitched)
      {
         for (double sr : rates)
         {
            std::string row;
            for (float hz : notes)
            {
               std::vector<float> y;
               Render(s, sr, hz, kN, y);
               const double got = PeakHz(Spectrum(y), hz, sr);
               const double cents = 1200.0 * std::log2(got / hz);
               char b[48];
               snprintf(b, sizeof b, " %6.0fHz %+6.2fc", hz, cents);
               row += b;
               if (std::fabs(cents) > kFlagPitchCents)
                  flags.Flag("PITCH", s.name, "cents", cents);
            }
            printf("SYNTHAUDIT PITCH %-15s %6.0f Hz |%s\n", s.name, sr, row.c_str());
         }
      }

      if (want("ALIAS") && s.pitched)
      {
         for (float hz : { 1750.0f, 5000.0f })
         {
            std::vector<float> y;
            Render(s, 48000.0, hz, kN, y);
            const double a = AliasDb(Spectrum(y), hz, 48000.0);
            printf("SYNTHAUDIT ALIAS %-15s %5.0f Hz  %7.1f dB\n", s.name, hz, a);
            if (a > kFlagAliasDb)
               flags.Flag("ALIAS", s.name, "dB", a);
         }
      }

      if (want("RATE"))
      {
         double lo = 1e9, hi = -1e9;
         for (double sr : rates)
         {
            std::vector<float> y;
            Render(s, sr, 440.0f, kN, y);
            const double d = Db(Rms(y));
            lo = std::min(lo, d);
            hi = std::max(hi, d);
         }
         printf("SYNTHAUDIT RATE  %-15s level spread %.2f dB over 44.1/48/96 kHz\n", s.name, hi - lo);
         if (hi - lo > kFlagRateDb)
            flags.Flag("RATE", s.name, "spread dB", hi - lo);
      }

      if (want("DET"))
      {
         std::vector<float> a, b;
         Render(s, 48000.0, 440.0f, 1 << 14, a);
         Render(s, 48000.0, 440.0f, 1 << 14, b);
         const bool same = a == b;
         printf("SYNTHAUDIT DET   %-15s %s\n", s.name, same ? "bit-identical" : "DIFFERS");
         if (!same)
            flags.Flag("DET", s.name, "not bit-identical", 1.0);
      }

      if (want("NOTE") || want("ENV") || want("CLICK") || want("VEL") || want("POLY"))
         ok = AuditNotes(s, flags) && ok;

      if (want("CPU"))
      {
         std::unique_ptr<INode> node(s.create());
         IAudioSource* src = AsSource(node.get());
         s.setFreq(node.get(), 440.0f);
         AudioNode* an = src->GetAudioNode();
         an->PrepareToPlay(48000.0, kBlock);
         node->CookIfNeeded(1);
         std::vector<float> l(kBlock), r(kBlock);
         float* ch[2] = { l.data(), r.data() };
         AudioBuffer buf;
         buf.channels = ch;
         buf.numChannels = 2;
         buf.numFrames = kBlock;
         for (int i = 0; i < 50; i++)
            an->ProcessBlock(nullptr, 0, buf);
         const int blocks = 2000;
         const auto t0 = std::chrono::steady_clock::now();
         for (int i = 0; i < blocks; i++)
            an->ProcessBlock(nullptr, 0, buf);
         const double ns = std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count() /
                           ((double)blocks * kBlock);
         printf("SYNTHAUDIT CPU   %-15s %7.1f ns/frame\n", s.name, ns);
         if (ns > kFlagCpuNs)
            flags.Flag("CPU", s.name, "ns/frame", ns);
      }
   }

   printf("SYNTHAUDIT %s (%d flags)\n", ok ? "done" : "FAILED", flags.n);
   return ok;
}
}
