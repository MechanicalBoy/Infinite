// DSP self-test fixtures, part 4: the effect wrapper's dry/wet contract and
// the Limiter's ceiling. Same rig as DelayTest (AppShared.h): a real
// AudioEffectNode -> AudioEffectRuntime -> kernel pipeline, one sample per
// block, so what is measured is what a patch hears.
#include "app/AppShared.h"

namespace
{
   const EffectDef* FindEffectDef(const char* name)
   {
      for (const EffectDef& d : GetEffectDefs())
         if (d.name == name)
            return &d;
      return nullptr;
   }

   std::unique_ptr<AudioEffectNode> MakeEffect(const EffectDef& def, float mix, double sampleRate)
   {
      auto node = std::make_unique<AudioEffectNode>(def);
      node->mix = mix;
      node->GetAudioNode()->PrepareToPlay(sampleRate, 512);
      node->CookIfNeeded(1);
      return node;
   }

   // Deterministic white noise in [-1, 1].
   struct Lcg
   {
      uint32_t s = 12345u;
      float Next()
      {
         s = s * 1664525u + 1013904223u;
         return (float)((s >> 8) & 0xFFFFFF) / (float)0x7FFFFF - 1.0f;
      }
   };

   // Reference true peak: 16x band-limited interpolation with a long
   // (64-tap-per-side) Blackman-windowed sinc - much finer than the
   // limiter's own 4x detector, so it measures the detector rather than
   // agreeing with it.
   float ReferenceTruePeak(const std::vector<float>& x, size_t from)
   {
      constexpr int kUp = 16;
      constexpr int kHalf = 64;
      float peak = 0.0f;
      for (size_t k = from + kHalf; k + kHalf + 1 < x.size(); k++)
      {
         peak = std::max(peak, std::fabs(x[k]));
         for (int p = 1; p < kUp; p++)
         {
            const double frac = (double)p / kUp;
            double acc = 0.0;
            for (int j = -kHalf + 1; j <= kHalf; j++)
            {
               const double d = (double)j - frac;
               const double sinc = std::sin(M_PI * d) / (M_PI * d);
               const double r = (d + kHalf) / (2.0 * kHalf);
               const double win = 0.42 - 0.5 * std::cos(2.0 * M_PI * r) + 0.08 * std::cos(4.0 * M_PI * r);
               acc += x[k + j] * sinc * win;
            }
            peak = std::max(peak, (float)std::fabs(acc));
         }
      }
      return peak;
   }

   float Db(float lin) { return 20.0f * std::log10(std::max(lin, 1.0e-12f)); }
}

bool RunEffectMixAndLimiterFixture()
{
   bool all = true;
   const double sampleRate = 44100.0; // AudioEffectNode::CookIfNeeded's no-device fallback rate

   // 1) Dry path is latency-aligned. At mix 0 the output is the dry signal
   //    alone; the wrapper reports the kernel's latency to PDC, so that dry
   //    signal must come out exactly LatencySamples() late - otherwise any
   //    mix below 100% sums an early dry copy with the late wet one (a comb
   //    for the Limiter, a ~46 ms slapback for the 2048-point spectral
   //    effects). Checked for every effect that reports latency.
   {
      int checked = 0;
      bool ok = true;
      for (const EffectDef& def : GetEffectDefs())
      {
         if (def.forceFullyWet)
            continue;
         auto node = MakeEffect(def, 0.0f, sampleRate);
         const int latency = node->GetAudioNode()->LatencySamples();
         if (latency <= 0)
            continue;
         // Let the mix smoother settle on 0 before the impulse.
         const int warm = (int)(0.1 * sampleRate);
         std::vector<std::vector<float>> out;
         DelayTest::RunSamples(*node, warm + latency + 64, 1,
                               [warm](int i, int) { return i == warm ? 0.5f : 0.0f; }, &out);
         int peakIdx = -1;
         float peakVal = 0.0f;
         for (size_t i = (size_t)warm; i < out[0].size(); i++)
            if (std::fabs(out[0][i]) > peakVal)
            {
               peakVal = std::fabs(out[0][i]);
               peakIdx = (int)i - warm;
            }
         const bool thisOk = peakIdx == latency && std::fabs(peakVal - 0.5f) < 1.0e-4f;
         if (!thisOk)
            printf("DSPTEST   %s: latency %d, dry impulse arrived at %d (%.4f)\n", def.name.c_str(), latency,
                   peakIdx, peakVal);
         ok &= thisOk;
         checked++;
      }
      ok &= checked > 0;
      printf("DSPTEST effect dry path delayed by reported latency: %d latent effects checked  %s\n", checked,
             ok ? "OK" : "FAIL");
      all &= ok;
   }

   const EffectDef* limiterDef = FindEffectDef("Limiter");
   if (limiterDef == nullptr)
   {
      printf("DSPTEST limiter: no Limiter EffectDef registered  FAIL\n");
      return false;
   }

   auto makeLimiter = [&](float thresholdDb, float mix) {
      auto node = std::make_unique<AudioEffectNode>(*limiterDef);
      node->mix = mix;
      *node->ParamPtr("threshold") = thresholdDb;
      *node->ParamPtr("release") = 50.0f;
      *node->ParamPtr("inGain") = 0.0f;
      *node->ParamPtr("outGain") = 0.0f;
      node->GetAudioNode()->PrepareToPlay(sampleRate, 512);
      node->CookIfNeeded(1);
      // Settle the mailbox smoothers on the pushed values before measuring.
      DelayTest::RunSamples(*node, (int)(0.2 * sampleRate), 1, [](int, int) { return 0.0f; }, nullptr);
      return node;
   };

   const float thresholdDb = -6.0f;
   const float ceiling = std::pow(10.0f, thresholdDb / 20.0f);

   // 2) Sample-peak ceiling holds on the signals that broke the old one-pole
   //    attack: a sudden +12 dB tone burst, hot noise, and isolated spikes.
   {
      struct Case
      {
         const char* label;
         std::function<float(int)> fn;
      };
      const int n = (int)(0.5 * sampleRate);
      Lcg noise;
      std::vector<float> noiseBuf((size_t)n);
      for (float& v : noiseBuf)
         v = noise.Next() * 2.0f; // ~ +12 dB over the -6 dB ceiling at its peaks
      const Case cases[] = {
         { "tone burst", [&](int i) {
              const float a = (i > n / 4 && i < n / 2) ? 2.0f : 0.1f;
              return a * std::sin(2.0f * (float)M_PI * 220.0f * (float)i / (float)sampleRate);
           } },
         { "hot noise", [&](int i) { return noiseBuf[(size_t)i]; } },
         { "spikes", [&](int i) { return (i % 2000) == 1000 ? 4.0f : 0.0f; } },
      };
      bool ok = true;
      for (const Case& c : cases)
      {
         auto node = makeLimiter(thresholdDb, 1.0f);
         std::vector<std::vector<float>> out;
         DelayTest::RunSamples(*node, n, 1, [&](int i, int) { return c.fn(i); }, &out);
         float peak = 0.0f;
         for (float v : out[0])
            peak = std::max(peak, std::fabs(v));
         const bool thisOk = peak <= ceiling * (1.0f + 1.0e-5f);
         printf("DSPTEST limiter sample-peak ceiling (%s): peak %+.3f dB vs ceiling %+.1f dB  %s\n", c.label,
                Db(peak), thresholdDb, thisOk ? "OK" : "FAIL");
         ok &= thisOk;
      }
      all &= ok;
   }

   // 3) True peak. A tone at fs/4 sampled 45 degrees off its crest has every
   //    sample at 0.707 of its real peak: sample peaks sit under the ceiling
   //    while the reconstructed wave goes +3 dB over it. The limiter must
   //    catch the inter-sample peak.
   {
      auto node = makeLimiter(thresholdDb, 1.0f);
      const int n = (int)(0.25 * sampleRate);
      const float amp = ceiling * 0.98f / 0.70710678f; // sample peaks 0.98 x ceiling
      std::vector<std::vector<float>> out;
      DelayTest::RunSamples(
         *node, n, 1,
         [amp](int i, int) { return amp * std::sin(0.5f * (float)M_PI * (float)i + 0.25f * (float)M_PI); }, &out);
      const float tp = ReferenceTruePeak(out[0], (size_t)(0.1 * sampleRate));
      const bool ok = Db(tp) <= thresholdDb + 0.1f;
      printf("DSPTEST limiter true-peak ceiling (fs/4 tone, +2.8 dB inter-sample): true peak %+.2f dB vs ceiling "
             "%+.1f dB  %s\n",
             Db(tp), thresholdDb, ok ? "OK" : "FAIL");
      all &= ok;
   }

   // 4) Below the ceiling the limiter is a pure delay of exactly
   //    LatencySamples() - no gain change, no smearing.
   {
      auto node = makeLimiter(thresholdDb, 1.0f);
      const int latency = node->GetAudioNode()->LatencySamples();
      const int n = 4096;
      auto sig = [](int i) { return 0.25f * std::sin(2.0f * (float)M_PI * 997.0f * (float)i / 44100.0f); };
      std::vector<std::vector<float>> out;
      DelayTest::RunSamples(*node, n, 1, [&](int i, int) { return sig(i); }, &out);
      float maxErr = 0.0f;
      for (int i = latency; i < n; i++)
         maxErr = std::max(maxErr, std::fabs(out[0][(size_t)i] - sig(i - latency)));
      const bool ok = latency > 0 && maxErr < 1.0e-5f;
      printf("DSPTEST limiter transparent below ceiling: latency %d, max |out - delayed in| %.2e  %s\n", latency,
             maxErr, ok ? "OK" : "FAIL");
      all &= ok;
   }

   // 5) Mix law. The Limiter's wet signal below the ceiling is the dry signal
   //    itself, so at mix 0.5 the two must sum back to unity - an
   //    equal-power law (cos + sin = 1.414) makes a half-mixed limiter +3 dB
   //    louder than either end of the knob.
   {
      auto node = makeLimiter(thresholdDb, 0.5f);
      const int latency = node->GetAudioNode()->LatencySamples();
      const int n = 4096;
      auto sig = [](int i) { return 0.25f * std::sin(2.0f * (float)M_PI * 997.0f * (float)i / 44100.0f); };
      std::vector<std::vector<float>> out;
      DelayTest::RunSamples(*node, n, 1, [&](int i, int) { return sig(i); }, &out);
      double num = 0.0, den = 0.0;
      for (int i = latency + 1024; i < n; i++)
      {
         num += (double)out[0][(size_t)i] * out[0][(size_t)i];
         den += (double)sig(i - latency) * sig(i - latency);
      }
      const float gainDb = 10.0f * (float)std::log10(num / std::max(den, 1.0e-30));
      const bool ok = std::fabs(gainDb) < 0.05f;
      printf("DSPTEST limiter mix 0.5 below ceiling: level %+.2f dB (want 0.00)  %s\n", gainDb, ok ? "OK" : "FAIL");
      all &= ok;
   }

   return all;
}
