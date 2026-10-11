#include "CycleShaperKernel.h"

#include "nodes/AudioEffectNode.h"

void CycleShaperKernel::PushParams(const AudioEffectNode& node, double /*sampleRate*/)
{
   const int waveform = std::clamp((int)std::round(node.Param("waveform")), 0, 2);
   const float thresholdDb = std::clamp(node.Param("threshold"), -60.0f, 0.0f);
   const float thresholdLinear = powf(10.0f, thresholdDb / 20.0f);
   const int smooth = std::clamp((int)std::round(node.Param("smooth")), 0, kMaxTail);
   const bool analog = node.Param("analog") > 0.5f;

   mWaveform.store(waveform, std::memory_order_relaxed);
   mThresholdLinear.store(thresholdLinear, std::memory_order_relaxed);
   mSmoothSamples.store(smooth, std::memory_order_relaxed);
   mAnalog.store(analog ? 1 : 0, std::memory_order_relaxed);
}

namespace
{
   // Where the quadratic through (-1, x0), (0, x1), (1, x2) crosses zero
   // upward between 0 and 1, as a fraction past x1. Falls back to the
   // straight line between x1 and x2.
   inline double CrossingFraction(double x0, double x1, double x2)
   {
      const double lin = x1 / (x1 - x2);
      const double a = 0.5 * (x2 + x0) - x1, b = 0.5 * (x2 - x0), c = x1;
      if (std::fabs(a) < 1.0e-12)
         return lin;
      const double disc = b * b - 4.0 * a * c;
      if (disc < 0.0)
         return lin;
      const double sq = std::sqrt(disc);
      for (double r : { (-b + sq) / (2.0 * a), (-b - sq) / (2.0 * a) })
         if (r >= 0.0 && r <= 1.0)
            return r;
      return lin;
   }

   // Vertex height of the quadratic through three samples around a local
   // extreme of |x| (x1 the largest): the crest between samples.
   inline float CrestHeight(float x0, float x1, float x2)
   {
      const float den = x0 - 2.0f * x1 + x2;
      if (std::fabs(den) < 1.0e-12f)
         return std::fabs(x1);
      const float p = std::clamp(0.5f * (x0 - x2) / den, -0.5f, 0.5f);
      return std::fabs(x1 - 0.25f * (x0 - x2) * p);
   }
   inline float ReadTable(const float* t, double phase)
   {
      const double x = phase * CycleShaperKernel::kTableSize;
      const int i = (int)x;
      const float f = (float)(x - i);
      return t[i] + (t[i + 1] - t[i]) * f;
   }
}

void CycleShaperKernel::ProcessBlock(const AudioBuffer& in, const AudioBuffer* /*sidechain*/, AudioBuffer& out)
{
   const int waveform = mWaveform.load(std::memory_order_relaxed);
   const float threshLinear = mThresholdLinear.load(std::memory_order_relaxed);
   const int smoothSamples = mSmoothSamples.load(std::memory_order_relaxed);
   const bool analog = mAnalog.load(std::memory_order_relaxed) != 0;
   const ShapeTables& tables = Tables();
   const double edgeSamples = (double)std::max(1, smoothSamples);

   const int numChannels = std::min({ in.numChannels, out.numChannels, kMaxChannels });

   for (int ch = 0; ch < numChannels; ch++)
   {
      ChannelState& s = mChannels[ch];
      const float* inData = in.channels[ch];
      float* outData = out.channels[ch];

      for (int i = 0; i < out.numFrames; i++)
      {
         const float x = inData[i];
         s.sinceCrossing += 1.0;

         if (s.prevSample <= 0.0f && x > 0.0f)
         {
            // Crossing between the previous sample and this one, `after`
            // samples before this one.
            const double frac = CrossingFraction(s.prevSample2, s.prevSample, x);
            const double after = 1.0 - frac;
            const double measured = s.sinceCrossing - after;
            // Smooth the period across cycles: steady pitch stays steady,
            // a real change still lands within a couple of cycles.
            const double period = (s.period > 0.0 && std::fabs(measured - s.period) < 0.1 * s.period)
                                     ? 0.5 * (s.period + measured)
                                     : measured;
            const bool valid = s.haveCrossing && period >= 4.0 && period <= (double)kMaxCycleSamples;
            if (valid && s.cyclePeak >= threshLinear)
            {
               const double target = after / period; // where the phase should be now
               if (!s.locked)
               {
                  s.phase = target;
                  s.inc = 1.0 / period;
                  s.amp = s.cyclePeak;
                  s.ampSteps = 0;
                  s.locked = true;
               }
               else
               {
                  double err = target - s.phase;
                  err -= std::floor(err + 0.5); // wrap to [-0.5, 0.5)
                  s.inc = (1.0 + 0.5 * err) / period;
                  s.ampSteps = std::max(1, (int)period);
                  s.ampStep = (s.cyclePeak - s.amp) / (float)s.ampSteps;
               }
               s.gateTarget = 1.0f;
               s.lastCycleLen = (float)period;
               s.lastCyclePeak = s.cyclePeak;
            }
            else if (s.haveCrossing)
            {
               s.gateTarget = 0.0f; // below threshold, or not a usable cycle
            }
            s.haveCrossing = true;
            s.period = (valid ? period : 0.0);
            s.sinceCrossing = after;
            s.cyclePeak = std::fabs(x);
         }
         else
         {
            // The previous sample was a crest of |x|: take the true peak
            // between samples, not the nearest sample.
            if (std::fabs(s.prevSample) >= std::fabs(s.prevSample2) && std::fabs(s.prevSample) >= std::fabs(x))
               s.cyclePeak = std::max(s.cyclePeak, CrestHeight(s.prevSample2, s.prevSample, x));
            s.cyclePeak = std::max(s.cyclePeak, std::fabs(x));
            if (s.sinceCrossing > (double)kMaxCycleSamples)
            {
               // No crossing for longer than the longest cycle: DC or
               // sub-audio. Hand back to the dry signal.
               s.gateTarget = 0.0f;
               s.locked = false;
               s.haveCrossing = false;
            }
         }

         s.gate = s.gateTarget + (s.gate - s.gateTarget) * mGateCoeff;
         if (s.gateTarget == 0.0f && s.gate < 1.0e-6f)
         {
            s.gate = 0.0f;
            s.locked = false;
         }

         float y = 0.0f;
         if (s.gate > 0.0f)
         {
            if (s.ampSteps > 0)
            {
               s.amp += s.ampStep;
               s.ampSteps--;
            }
            s.phase += s.inc;
            s.phase -= std::floor(s.phase);

            float shape;
            if (waveform == 0)
               shape = (float)std::sin(2.0 * M_PI * s.phase);
            else
            {
               // Harmonic ceiling: under Nyquist, and no more than an
               // `smooth`-sample edge allows (see the header). Level L is
               // safe when L >= log2(1024 * edge * inc); the +1 keeps the
               // brighter of the two crossfaded levels safe too - this runs
               // at the base rate, so there is no decimator to remove a
               // harmonic that slips over Nyquist.
               const float mipPos = std::clamp(
                  1.0f + (float)std::log2(std::max(1.0e-9, (double)kTableSize * edgeSamples * s.inc)), 0.0f,
                  (float)(kMips - 1));
               const int lo = (int)mipPos;
               const int hi = std::min(lo + 1, kMips - 1);
               const float f = mipPos - (float)lo;
               const auto& t = (waveform == 1) ? tables.square : tables.triangle;
               const float a = ReadTable(t[lo], s.phase);
               shape = (f > 0.0f) ? a + (ReadTable(t[hi], s.phase) - a) * f : a;
            }
            y = s.amp * shape;
            if (analog)
               y = AnalogDsp::AsymTanh(y);
         }

         outData[i] = DspMath::FlushDenormal(s.gate * y + (1.0f - s.gate) * x);
         s.prevSample2 = s.prevSample;
         s.prevSample = x;
      }
   }

   for (int ch = numChannels; ch < out.numChannels; ch++)
   {
      for (int i = 0; i < out.numFrames; i++)
         out.channels[ch][i] = 0.0f;
   }
}
