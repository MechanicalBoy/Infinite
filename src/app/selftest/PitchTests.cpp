// INFINITE_PITCHTEST: how cleanly the Pitch Shifter shifts.
//
// Four measurements, through the real AudioEffectNode -> kernel chain at
// 48 kHz, fully wet:
//
//   purity     a sine shifted by N semitones should come out as one sine at
//              the target pitch. Everything else - the grain-rate amplitude
//              modulation and comb sidebands a delay-line shifter makes,
//              spectral smearing - is reported as energy outside the target's
//              window lobe, relative to the target (dB, lower is better).
//              The input is chosen so the *output* lands on an FFT bin.
//   chord      three sines shifted together; energy outside the three target
//              lobes, relative to their sum. Intermodulation and smearing
//              between partials shows up here and not in `purity`.
//   unity      at 0 semitones the effect should be transparent: the output
//              should null against the input delayed by the reported
//              latency (residual, dB re the input).
//   transient  a click train shifted +7 st: the width (ms) of the window
//              holding 90% of each click's output energy. A doubled or
//              smeared click is wider.
//
// Cases with a gate fail the test past it; the rest are reported so the
// numbers are visible before and after a change.
#include "app/AppShared.h"
#include "audio/dsp/PortableFft.h"
#include "audio/dsp/SpectralPitchShifter.h"

namespace app
{
namespace
{
   constexpr double kRate = 48000.0;
   constexpr int kLog2N = 14;
   constexpr int kN = 1 << kLog2N;
   constexpr int kLobe = 4;
   constexpr double kBinHz = kRate / (double)kN;

   const EffectDef* PitchDef()
   {
      for (const EffectDef& d : GetEffectDefs())
         if (d.name == "Pitch Shifter")
            return &d;
      return nullptr;
   }

   std::unique_ptr<AudioEffectNode> MakeShifter(float semitones, float grainMs, float spectral)
   {
      auto node = std::make_unique<AudioEffectNode>(*PitchDef());
      node->mix = 1.0f;
      *node->ParamPtr("pitch") = semitones;
      *node->ParamPtr("grain") = grainMs;
      if (float* p = node->ParamPtr("spectral"))
         *p = spectral;
      node->GetAudioNode()->PrepareToPlay(kRate, 512);
      node->CookIfNeeded(1);
      return node;
   }

   std::vector<float> Render(AudioEffectNode& node, int n, const std::function<float(int)>& sig)
   {
      std::vector<std::vector<float>> out;
      DelayTest::RunSamples(node, n, 1, [&](int i, int) { return sig(i); }, &out);
      return out[0];
   }

   // Power spectrum of the last kN samples, Blackman-Harris windowed.
   std::vector<double> Spectrum(const std::vector<float>& x)
   {
      std::vector<float> w((size_t)kN);
      const size_t off = x.size() - (size_t)kN;
      for (int i = 0; i < kN; i++)
      {
         const double t = 2.0 * M_PI * i / kN;
         w[(size_t)i] = (float)(x[off + (size_t)i] *
                                (0.35875 - 0.48829 * std::cos(t) + 0.14128 * std::cos(2 * t) - 0.01168 * std::cos(3 * t)));
      }
      PortableFft::RealFft fft;
      fft.Prepare(kLog2N);
      std::vector<float> re((size_t)kN / 2), im((size_t)kN / 2);
      fft.Forward(w.data(), kLog2N, re.data(), im.data());
      std::vector<double> p((size_t)kN / 2);
      for (int k = 1; k < kN / 2; k++)
         p[(size_t)k] = (double)re[(size_t)k] * re[(size_t)k] + (double)im[(size_t)k] * im[(size_t)k];
      return p;
   }

   // Energy outside the target bins' lobes (20 Hz .. 20 kHz) re the energy inside them.
   double Spurious(const std::vector<double>& p, const std::vector<int>& targets)
   {
      const int lo = (int)(20.0 / kBinHz), hi = (int)(20000.0 / kBinHz);
      double in = 0.0, out = 0.0;
      for (int k = lo; k <= hi; k++)
      {
         bool inside = false;
         for (int t : targets)
            inside |= std::abs(k - t) <= kLobe;
         (inside ? in : out) += p[(size_t)k];
      }
      return 10.0 * std::log10(std::max(out, 1e-30) / std::max(in, 1e-30));
   }

   double Ratio(float semitones) { return std::pow(2.0, semitones / 12.0); }

   double Purity(float semitones, float grainMs, float spectral, int targetBin)
   {
      auto node = MakeShifter(semitones, grainMs, spectral);
      const double inHz = targetBin * kBinHz / Ratio(semitones);
      const auto y = Render(*node, (int)(0.5 * kRate) + kN,
                            [&](int i) { return 0.5f * (float)std::sin(2.0 * M_PI * inHz * i / kRate); });
      return Spurious(Spectrum(y), { targetBin });
   }

   double Chord(float semitones, float grainMs, float spectral)
   {
      auto node = MakeShifter(semitones, grainMs, spectral);
      const std::vector<int> targets = { 101, 127, 151 }; // ~296, 372, 442 Hz: a major-ish triad
      const double r = Ratio(semitones);
      const auto y = Render(*node, (int)(0.5 * kRate) + kN, [&](int i) {
         double v = 0.0;
         for (int t : targets)
            v += std::sin(2.0 * M_PI * (t * kBinHz / r) * i / kRate);
         return (float)(0.25 * v);
      });
      return Spurious(Spectrum(y), targets);
   }

   double Unity(float grainMs, float spectral)
   {
      auto node = MakeShifter(0.0f, grainMs, spectral);
      const int latency = node->GetAudioNode()->LatencySamples();
      uint32_t seed = 1;
      std::vector<float> in((size_t)kRate);
      for (float& v : in)
      {
         seed = seed * 1664525u + 1013904223u;
         v = 0.3f * ((float)((seed >> 8) & 0xFFFF) / 32768.0f - 1.0f);
      }
      const auto y = Render(*node, (int)in.size(), [&](int i) { return in[(size_t)i]; });
      double e = 0.0, s = 0.0;
      for (size_t i = (size_t)(0.3 * kRate); i < in.size(); i++)
      {
         const double d = y[i] - in[i - (size_t)latency];
         e += d * d;
         s += (double)in[i] * in[i];
      }
      return 10.0 * std::log10(std::max(e, 1e-30) / s);
   }

   double TransientWidthMs(float grainMs, float spectral, float semitones = 7.0f)
   {
      auto node = MakeShifter(semitones, grainMs, spectral);
      const int period = (int)(0.25 * kRate);
      const auto y = Render(*node, period * 8, [&](int i) { return (i % period) == period / 2 ? 1.0f : 0.0f; });
      // Average the 90%-energy width over clicks 3..7 (past start-up).
      double total = 0.0;
      int count = 0;
      for (int c = 3; c < 8; c++)
      {
         const size_t a = (size_t)(c * period), b = a + (size_t)period;
         double e = 0.0;
         for (size_t i = a; i < b; i++)
            e += (double)y[i] * y[i];
         // A dropped click (a forward splice skipping it) is the worst
         // transient result there is, not one to leave out of the average.
         if (e < 0.1)
         {
            total += 1000.0;
            count++;
            continue;
         }
         // Smallest window around the energy centroid holding 90%.
         std::vector<double> cum(b - a + 1, 0.0);
         for (size_t i = a; i < b; i++)
            cum[i - a + 1] = cum[i - a] + (double)y[i] * y[i];
         size_t best = b - a;
         size_t lo = 0;
         for (size_t hi = 0; hi <= b - a; hi++)
            while (lo < hi && cum[hi] - cum[lo] >= 0.9 * e)
            {
               best = std::min(best, hi - lo);
               lo++;
            }
         total += 1000.0 * (double)best / kRate;
         count++;
      }
      return count > 0 ? total / count : 0.0;
   }

   struct Line
   {
      const char* label;
      double value;
      double gate; // 0 = report only; purity/chord/unity gates are maxima, width gates maxima too
      const char* unit;
   };
}

bool RunPitchTest()
{
   if (PitchDef() == nullptr)
   {
      printf("PITCHTEST no Pitch Shifter EffectDef  FAIL\n");
      return false;
   }
   // Classic (time-domain, correlation-spliced) engine. Before it, the
   // two-tap kernel read: purity -27.9 / -25.6 / -9.1 dB (+7 / -12 / +12 st),
   // chord -28.0 dB, unity null 0.0 dB (a permanent comb), transient 14.4 ms.
   std::vector<Line> lines = {
      { "classic purity +7 st (80 ms grain)", Purity(7.0f, 80.0f, 0.0f, 241), -60.0, "dB" },
      { "classic purity -12 st (80 ms grain)", Purity(-12.0f, 80.0f, 0.0f, 121), -75.0, "dB" },
      { "classic purity +12 st (80 ms grain)", Purity(12.0f, 80.0f, 0.0f, 481), -68.0, "dB" },
      { "classic chord +5 st (80 ms grain)", Chord(5.0f, 80.0f, 0.0f), -28.0, "dB" },
      { "classic unity 0 st null (80 ms grain)", Unity(80.0f, 0.0f), -120.0, "dB" },
      // Splices steer around the last onset: before that, a click that fell
      // inside a jump came out doubled (32 ms at +7 st) or dropped.
      { "classic transient +7 st 90% width", TransientWidthMs(80.0f, 0.0f), 15.0, "ms" },
      { "classic transient -7 st 90% width", TransientWidthMs(80.0f, 0.0f, -7.0f), 15.0, "ms" },
      // Spectral (phase-vocoder) mode - the chord is what it is for.
      { "spectral purity +7 st", Purity(7.0f, 80.0f, 1.0f, 241), -65.0, "dB" },
      { "spectral purity -12 st", Purity(-12.0f, 80.0f, 1.0f, 121), -50.0, "dB" },
      { "spectral purity +12 st", Purity(12.0f, 80.0f, 1.0f, 481), -57.0, "dB" },
      { "spectral chord +5 st", Chord(5.0f, 80.0f, 1.0f), -48.0, "dB" },
      { "spectral unity 0 st null", Unity(80.0f, 1.0f), -120.0, "dB" },
      { "spectral transient +7 st 90% width", TransientWidthMs(80.0f, 1.0f), 20.0, "ms" },
   };
   bool all = true;
   int gated = 0;
   for (const Line& l : lines)
   {
      const char* verdict = "info";
      static char buf[48];
      if (l.gate != 0.0)
      {
         const bool ok = l.value <= l.gate;
         snprintf(buf, sizeof(buf), "gate %.1f %s %s", l.gate, l.unit, ok ? "OK" : "FAIL");
         verdict = buf;
         all &= ok;
         gated++;
      }
      printf("PITCHTEST %-42s %8.1f %s  %s\n", l.label, l.value, l.unit, verdict);
   }
   // The dry path follows a mode switch mid-stream: at mix 0 the output is the
   // dry signal alone, and it must arrive exactly LatencySamples() late
   // whichever mode is on - including after switching on a live node.
   {
      auto node = MakeShifter(7.0f, 80.0f, 0.0f);
      node->mix = 0.0f;
      node->CookIfNeeded(2);
      bool ok = true;
      int frame = 3;
      for (float mode : { 1.0f, 0.0f, 1.0f })
      {
         *node->ParamPtr("spectral") = mode;
         node->CookIfNeeded(frame++);
         const int latency = node->GetAudioNode()->LatencySamples();
         const int warm = 4800;
         const auto y = Render(*node, warm + latency + 64, [&](int i) { return i == warm ? 0.5f : 0.0f; });
         int peak = -1;
         float pv = 0.0f;
         for (size_t i = (size_t)warm; i < y.size(); i++)
            if (std::fabs(y[i]) > pv)
            {
               pv = std::fabs(y[i]);
               peak = (int)i - warm;
            }
         const bool thisOk = peak == latency && std::fabs(pv - 0.5f) < 1e-3f;
         printf("PITCHTEST   dry path after switching spectral=%d: latency %d, impulse at %d (%.3f)\n", (int)mode,
                latency, peak, pv);
         ok &= thisOk;
      }
      printf("PITCHTEST dry path follows a live mode switch  %s\n", ok ? "OK" : "FAIL");
      all &= ok;
   }

   // PDC follows it too: a Pitch Shifter wired to an Audio Out, the topology
   // built in classic mode, then switched to spectral. PollAudioLatencyChanges
   // (once a frame in the app) must rebuild PDC with the new latency.
   {
      // Indices, not pointers: SpawnNode returns &gNodes.back(), which the
      // next spawn's push_back can move.
      GraphNode* g1 = SpawnNode("Pitch Shifter", "AudioEffects", 0.0f, 0.0f);
      const int shifterIdx = g1 ? g1->index : -1;
      GraphNode* g2 = SpawnNode("Audio Out", "Utility", 400.0f, 0.0f);
      const int outIdx = g2 ? g2->index : -1;
      GraphNode* shifter = shifterIdx >= 0 ? FindNodeByIndex(shifterIdx) : nullptr;
      GraphNode* out = outIdx >= 0 ? FindNodeByIndex(outIdx) : nullptr;
      bool ok = shifter != nullptr && out != nullptr && dynamic_cast<AudioEffectNode*>(shifter->node.get()) != nullptr;
      if (ok)
      {
         auto* fx = static_cast<AudioEffectNode*>(shifter->node.get());
         *fx->ParamPtr("pitch") = 7.0f;
         fx->CookIfNeeded(100);
         static_cast<AudioOutputNode*>(out->node.get())->input.Connect(fx);
         RebuildAudioTopology();
         AudioNode* an = fx->GetAudioNode();
         const int before = AudioTopologyLatencyOf(an);
         *fx->ParamPtr("spectral") = 1.0f;
         fx->CookIfNeeded(101);
         PollAudioLatencyChanges();
         const int after = AudioTopologyLatencyOf(an);
         ok = before == 1 && after == SpectralPitchShifter::kFftSize;
         printf("PITCHTEST PDC rebuilt on a latency change: built with %d, after switching %d (want 1 -> %d)  %s\n",
                before, after, SpectralPitchShifter::kFftSize, ok ? "OK" : "FAIL");
      }
      else
         printf("PITCHTEST PDC rebuilt on a latency change: could not spawn nodes  FAIL\n");
      all &= ok;
   }

   printf("PITCHTEST %d gated case(s) at their limits  %s\n", gated, all ? "OK" : "FAIL");
   return all;
}
}
