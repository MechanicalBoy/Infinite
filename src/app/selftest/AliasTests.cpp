// INFINITE_ALIASTEST: how much aliasing each static nonlinearity produces.
//
// A pure tone goes through the real AudioEffectNode -> AudioEffectRuntime ->
// kernel chain at 48 kHz. Its harmonics above Nyquist fold back to
// frequencies that are not multiples of the tone, so after a
// Blackman-Harris windowed FFT every bin below 20 kHz that is not a harmonic
// (or DC) is audible aliasing. The figure reported is that energy relative
// to the fundamental. Folding into 20-24 kHz is not counted: an oversampler's
// transition band legitimately lets a little of it through, and it is above
// hearing.
//
// The tone sits on an odd FFT bin of a power-of-two transform, so a folded
// harmonic |h*k0 - m*N| can never land on a harmonic bin j*k0: that would
// need (h +- j) * k0 to be a multiple of N, impossible for an odd k0.
//
// Only static nonlinearities are measured. A modulated effect (chorus, wow
// and flutter in an analog mode) spreads sidebands around every harmonic,
// which this metric would misread as aliasing.
//
// Ratchet: a case with a gateDb must reach it or the test fails. A node is
// gated once it has real anti-aliasing (oversampling and/or ADAA), at what
// it measurably achieves; ungated cases are reported so the numbers are
// visible before and after. Drive before its anti-aliasing (same metric):
// -21 dB at 50% drive, -12 dB at 100%.
// A linear effect runs as the rig's own control and must read clean.
#include "app/AppShared.h"
#include "audio/dsp/PortableFft.h"

namespace app
{
namespace
{
   constexpr double kRate = 48000.0;
   constexpr int kLog2N = 14;
   constexpr int kN = 1 << kLog2N;
   constexpr int kFundBin = 1707; // 5001 Hz; odd, see the file comment
   constexpr int kLobe = 4;       // 4-term Blackman-Harris main lobe half-width, bins
   constexpr double kAudibleHz = 20000.0;
   constexpr float kAmplitude = 0.5f;
   constexpr double kControlDb = -100.0;

   struct AliasMeasurement
   {
      double aliasDb = 0.0;    // non-harmonic energy re fundamental
      double harmonicDb = 0.0; // in-band harmonic energy re fundamental
   };

   AliasMeasurement Measure(const std::vector<float>& x)
   {
      std::vector<float> windowed((size_t)kN);
      for (int i = 0; i < kN; i++)
      {
         const double t = 2.0 * M_PI * (double)i / (double)kN;
         const double w = 0.35875 - 0.48829 * std::cos(t) + 0.14128 * std::cos(2.0 * t) - 0.01168 * std::cos(3.0 * t);
         windowed[(size_t)i] = (float)(x[(size_t)i] * w);
      }
      PortableFft::RealFft fft;
      fft.Prepare(kLog2N);
      std::vector<float> re((size_t)kN / 2), im((size_t)kN / 2);
      fft.Forward(windowed.data(), kLog2N, re.data(), im.data());

      std::vector<char> harmonic((size_t)kN / 2, 0);
      for (int k = 0; k <= kLobe; k++)
         harmonic[(size_t)k] = 1; // DC
      for (int h = 1; h * kFundBin - kLobe < kN / 2; h++)
         for (int d = -kLobe; d <= kLobe; d++)
         {
            const int k = h * kFundBin + d;
            if (k > 0 && k < kN / 2)
               harmonic[(size_t)k] = 1;
         }

      double fund = 0.0, alias = 0.0, harm = 0.0;
      const int audibleTop = (int)(kAudibleHz / kRate * kN);
      for (int k = 1; k < kN / 2; k++)
      {
         if (k > audibleTop && !harmonic[(size_t)k])
            continue;
         const double p = (double)re[(size_t)k] * re[(size_t)k] + (double)im[(size_t)k] * im[(size_t)k];
         if (std::abs(k - kFundBin) <= kLobe)
            fund += p;
         else if (harmonic[(size_t)k])
            harm += p;
         else
            alias += p;
      }
      fund = std::max(fund, 1.0e-30);
      AliasMeasurement m;
      m.aliasDb = 10.0 * std::log10(std::max(alias, 1.0e-30) / fund);
      m.harmonicDb = 10.0 * std::log10(std::max(harm, 1.0e-30) / fund);
      return m;
   }

   struct AliasCase
   {
      const char* label;
      const char* effect;
      std::vector<std::pair<const char*, float>> params; // value as a fraction of the param's range
      double gateDb = 0.0; // 0 = report only; otherwise the case must reach this
      bool control = false;
   };

   bool RunCase(const AliasCase& c, AliasMeasurement& out)
   {
      const EffectDef* def = nullptr;
      for (const EffectDef& d : GetEffectDefs())
         if (d.name == c.effect)
            def = &d;
      if (def == nullptr)
         return false;

      auto node = std::make_unique<AudioEffectNode>(*def);
      node->mix = 1.0f;
      for (const auto& [name, frac] : c.params)
      {
         const EffectParamDef* pd = FindEffectParamDef(c.effect, name);
         float* p = node->ParamPtr(name);
         if (pd == nullptr || p == nullptr)
            return false;
         *p = pd->minVal + frac * (pd->maxVal - pd->minVal);
      }
      node->GetAudioNode()->PrepareToPlay(kRate, 512);
      node->CookIfNeeded(1);

      const double omega = 2.0 * M_PI * (double)kFundBin / (double)kN;
      const int warm = (int)(0.3 * kRate);
      std::vector<std::vector<float>> rendered;
      DelayTest::RunSamples(
         *node, warm + kN, 1,
         [omega](int i, int) { return kAmplitude * (float)std::sin(omega * (double)i); }, &rendered);
      std::vector<float> tail(rendered[0].begin() + warm, rendered[0].end());
      out = Measure(tail);
      return true;
   }
}

bool RunAliasTest()
{
   // Fractions of each param's declared range, so a range change in
   // EffectDefs.cpp moves the probe with it instead of silently clamping.
   const std::vector<AliasCase> cases = {
      { "Stereo (linear control)", "Stereo", {}, 0.0, true },
      // Drive: 8x oversampling + first-order ADAA (DriveKernel.h).
      { "Drive tanh, drive 50%", "Drive", { { "drive", 0.5f }, { "color", 0.0f } }, -100.0 },
      { "Drive atan, drive 50%", "Drive", { { "drive", 0.5f }, { "color", 1.0f } }, -100.0 },
      { "Drive tanh, drive 100%", "Drive", { { "drive", 1.0f }, { "color", 0.0f } }, -60.0 },
      { "Drive asymmetric, drive 50%", "Drive", { { "drive", 0.5f }, { "bias", 0.75f } }, -100.0 },
      { "Wavetable Shaper, drive 50%", "Wavetable Shaper", { { "drive", 0.5f } } },
      { "Wavetable Shaper, drive 100%", "Wavetable Shaper", { { "drive", 1.0f } } },
      { "Dynamics analog, -30 dB / 8:1", "Dynamics",
        { { "analog", 1.0f }, { "threshold", 0.5f }, { "ratio", 7.0f / 19.0f } } },
      { "Cycle Shaper (default)", "Cycle Shaper", {} },
      { "Bitcrush (aliasing is the effect)", "Bitcrush", {} },
   };

   bool all = true;
   int gated = 0;
   for (const AliasCase& c : cases)
   {
      AliasMeasurement m;
      if (!RunCase(c, m))
      {
         printf("ALIASTEST %s: could not build the case  FAIL\n", c.label);
         all = false;
         continue;
      }
      const char* verdict = "info";
      if (c.control)
      {
         const bool ok = m.aliasDb <= kControlDb;
         verdict = ok ? "control OK" : "control FAIL";
         all &= ok;
      }
      else if (c.gateDb < 0.0)
      {
         const bool ok = m.aliasDb <= c.gateDb;
         static char buf[48];
         snprintf(buf, sizeof(buf), "gate %.0f dB %s", c.gateDb, ok ? "OK" : "FAIL");
         verdict = buf;
         all &= ok;
         gated++;
      }
      printf("ALIASTEST %-36s alias<20k %7.1f dB  harmonics %7.1f dB  (re fundamental, 5 kHz @ -6 dBFS, 48 kHz)  %s\n",
             c.label, m.aliasDb, m.harmonicDb, verdict);
   }
   printf("ALIASTEST %d gated case(s) at their limits  %s\n", gated, all ? "OK" : "FAIL");
   return all;
}
}
