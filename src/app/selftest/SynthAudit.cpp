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
// Only hard invariants fail the run (non-finite output, silence at defaults).
// Everything else is reported, with FLAG lines past the thresholds below.
#include "app/AppShared.h"
#include "audio/AudioBuffer.h"
#include "audio/dsp/PortableFft.h"
#include "nodes/AnalogNode.h"
#include "nodes/EquationNode.h"
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
