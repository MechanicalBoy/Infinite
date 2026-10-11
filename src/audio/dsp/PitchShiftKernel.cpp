#include "PitchShiftKernel.h"

#include "nodes/AudioEffectNode.h"

void PitchShiftKernel::PushParams(const AudioEffectNode& node, double sampleRate)
{
   mSampleRate = sampleRate;
   mMailbox.Push(kSemitones, node.Param("pitch"));
   mMailbox.Push(kGrainMs, node.Param("grain"));
   mAnalog.store(node.Param("analog") != 0.0f ? 1 : 0, std::memory_order_relaxed);
}

double PitchShiftKernel::FindSplice(double from, int jMin, int jMax, int sign, int window) const
{
   // Integer part of each candidate's delay; the fractional part of `from`
   // carries over, so the comparison is on the sample grid.
   const int base = (int)std::floor(from);
   auto mono = [&](int k) { return mLineL.SampleAtDelay(k) + mLineR.SampleAtDelay(k); };

   double refEnergy = 0.0;
   for (int m = 0; m < window; m += 2)
   {
      const double r = mono(base + m);
      refEnergy += r * r;
   }
   const int nominal = jMax;
   if (refEnergy < 1.0e-12)
      return from + sign * nominal;

   auto score = [&](int j, int step) {
      const int cand = base + sign * j;
      double dot = 0.0, e = 0.0;
      for (int m = 0; m < window; m += step)
      {
         const double c = mono(cand + m);
         dot += c * mono(base + m);
         e += c * c;
      }
      return (e < 1.0e-12) ? -1.0 : dot / std::sqrt(e);
   };

   // Coarse pass on every other lag and sample, then refine around the best.
   int best = nominal;
   double bestScore = -1.0e30;
   for (int j = jMin; j <= jMax; j += 2)
   {
      const double sc = score(j, 2);
      if (sc > bestScore)
      {
         bestScore = sc;
         best = j;
      }
   }
   const int coarse = best;
   bestScore = -1.0e30;
   for (int j = std::max(jMin, coarse - 2); j <= std::min(jMax, coarse + 2); j++)
   {
      const double sc = score(j, 1);
      if (sc > bestScore)
      {
         bestScore = sc;
         best = j;
      }
   }
   return from + sign * best;
}

void PitchShiftKernel::ProcessBlock(const AudioBuffer& in, const AudioBuffer* /*sidechain*/, AudioBuffer& out)
{
   const int numChannels = std::min(in.numChannels, std::min(out.numChannels, 2));
   const bool analog = mAnalog.load(std::memory_order_relaxed) != 0;
   const double maxDelay = (double)mLineL.size - 4.0;

   for (int i = 0; i < out.numFrames; i++)
   {
      const float semitones = mMailbox.SmoothedValue(kSemitones);
      const float grainMs = std::clamp(mMailbox.SmoothedValue(kGrainMs), 10.0f, kMaxGrainMs);
      const double grain = grainMs * 0.001 * mSampleRate;
      const double ratio = std::pow(2.0, semitones / 12.0);
      const double drift = 1.0 - ratio; // delay change per sample: < 0 shifting up

      const float inL = in.channels[0][i];
      const float inR = numChannels >= 2 ? in.channels[1][i] : inL;
      mLineL.Write(inL);
      mLineR.Write(inR);

      // Splice geometry, from the grain: jump by 0.5..1 grain (the search
      // range), crossfade over 0.3 grain (3..30 ms), compare 15 ms of signal.
      const int jMax = std::max(4, (int)grain);
      const int jMin = std::max(2, jMax / 2);
      const int fadeLen = (int)std::clamp(0.3 * grain, 0.003 * mSampleRate, 0.030 * mSampleRate);
      const int window = (int)std::min((double)fadeLen, 0.015 * mSampleRate);

      if (mFadeLen == 0)
      {
         if (drift < -1.0e-9 && mDelay + drift * fadeLen <= 2.0)
         {
            // Shifting up: about to run into the newest sample - jump back.
            const double target = std::min(FindSplice(mDelay, jMin, jMax, +1, window), maxDelay);
            mNextDelay = target;
            mFadeLen = fadeLen;
            mFadePos = 0;
         }
         else if (drift > 1.0e-9 && mDelay + drift * fadeLen >= std::min(maxDelay, (double)jMax + fadeLen + 2.0))
         {
            // Shifting down: about to fall off the end - jump forward.
            const double target = std::max(FindSplice(mDelay, jMin, jMax, -1, window), 1.0);
            mNextDelay = target;
            mFadeLen = fadeLen;
            mFadePos = 0;
         }
         else if (std::fabs(drift) <= 1.0e-9 && mDelay != 1.0)
         {
            // Back at 0 st after a shift: return to transparent.
            mNextDelay = 1.0;
            mFadeLen = fadeLen;
            mFadePos = 0;
         }
      }

      float jitter = 0.0f;
      if (analog)
      {
         mJitterPhase += 17.3f / (float)mSampleRate;
         if (mJitterPhase >= 1.0f)
            mJitterPhase -= 1.0f;
         jitter = sinf(mJitterPhase * 2.0f * (float)M_PI) * 0.35f;
      }

      const float dA = (float)std::clamp(mDelay + jitter, 1.0, maxDelay);
      float outL = mLineL.Read(dA);
      float outR = mLineR.Read(dA);
      if (mFadeLen > 0)
      {
         const float t = (float)(mFadePos + 1) / (float)(mFadeLen + 1);
         const float wNew = 0.5f - 0.5f * cosf((float)M_PI * t);
         const float dB = (float)std::clamp(mNextDelay + jitter, 1.0, maxDelay);
         outL += (mLineL.Read(dB) - outL) * wNew;
         outR += (mLineR.Read(dB) - outR) * wNew;
      }

      // Both taps move at the shifted rate; a finished splice hands over.
      mDelay = std::clamp(mDelay + drift, 1.0, maxDelay);
      if (mFadeLen > 0)
      {
         mNextDelay = std::clamp(mNextDelay + drift, 1.0, maxDelay);
         if (++mFadePos >= mFadeLen)
         {
            mDelay = mNextDelay;
            mFadeLen = 0;
         }
      }

      if (analog)
      {
         // 4th-order 9kHz lowpass reconstruction filter
         outL = mFilterL[0].Process(outL).low;
         outL = mFilterL[1].Process(outL).low;
         outR = mFilterR[0].Process(outR).low;
         outR = mFilterR[1].Process(outR).low;

         // Harmonic grain saturation
         outL = AnalogDsp::AsymTanh(outL, 0.12f);
         outR = AnalogDsp::AsymTanh(outR, 0.12f);
      }

      out.channels[0][i] = outL;
      if (numChannels >= 2)
         out.channels[1][i] = outR;

      for (int ch = 2; ch < out.numChannels; ch++)
         out.channels[ch][i] = 0.0f;
   }
}
