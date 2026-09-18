#include "ReverbKernel.h"

#include "nodes/AudioEffectNode.h"

void ReverbKernel::PushParams(const AudioEffectNode& node, double sampleRate)
{
   mSampleRate = sampleRate;
   mMailbox.Push(kSize, node.Param("size"));
   mMailbox.Push(kDecaySeconds, node.Param("decay"));
   mMailbox.Push(kDamping, node.Param("damping"));
   mMailbox.Push(kPredelayMs, node.Param("predelay"));
   mMailbox.Push(kWidth, node.Param("width"));
   mAnalog.store(node.Param("analog") != 0.0f ? 1 : 0, std::memory_order_relaxed);
}

void ReverbKernel::ProcessBlock(const AudioBuffer& in, const AudioBuffer* /*sidechain*/, AudioBuffer& out)
{
   using namespace ReverbDsp;

   const int numChannels = std::min(in.numChannels, std::min(out.numChannels, 2));
   const float rateScale = (float)(mSampleRate / 44100.0);
   const float outScale = 1.0f / std::sqrt((float)kNumLines); // keeps the N-way sum near unity
   const bool analog = mAnalog.load(std::memory_order_relaxed) != 0;

   float blockDryPeak = 0.0f, blockWetPeak = 0.0f;

   for (int i = 0; i < out.numFrames; i++)
   {
      const float size = std::clamp(mMailbox.SmoothedValue(kSize), 0.0f, 1.0f);
      const float decaySeconds = std::max(0.05f, mMailbox.SmoothedValue(kDecaySeconds));
      const float damping = std::clamp(mMailbox.SmoothedValue(kDamping), 0.0f, 1.0f);
      const float predelayMs = std::max(0.0f, mMailbox.SmoothedValue(kPredelayMs));
      const float width = std::clamp(mMailbox.SmoothedValue(kWidth), 0.0f, 1.0f);

      const float inL = in.channels[0][i];
      const float inR = numChannels >= 2 ? in.channels[1][i] : inL;
      const float inMono = numChannels >= 2 ? 0.5f * (inL + inR) : inL;

      // Predelay: plain integer-sample read/write per channel behind a
      // shared write pointer, so a stereo source's L/R difference survives
      // into the diffusers instead of being summed away up front.
      const int predelaySamples = std::clamp((int)std::lround(predelayMs * 0.001f * (float)mSampleRate), 0,
                                              mPredelayCapacity - 1);
      mPredelayL[(size_t)mPredelayWrite] = inL;
      mPredelayR[(size_t)mPredelayWrite] = inR;
      int readPos = mPredelayWrite - predelaySamples;
      readPos %= mPredelayCapacity;
      if (readPos < 0)
         readPos += mPredelayCapacity;
      const float predelayedL = mPredelayL[(size_t)readPos];
      const float predelayedR = mPredelayR[(size_t)readPos];
      mPredelayWrite++;
      if (mPredelayWrite >= mPredelayCapacity)
         mPredelayWrite = 0;

      // 4-stage Schroeder diffusion per channel, independently seeded, so
      // the tank sees genuinely decorrelated L/R content rather than a mono
      // sum with a sign flip - most of what makes the tail feel wide
      // instead of merely phase-inverted.
      float diffusedL = predelayedL;
      for (int s = 0; s < kNumDiffusionStages; s++)
         diffusedL = mDiffuserL[s].Process(diffusedL);
      float diffusedR = predelayedR;
      for (int s = 0; s < kNumDiffusionStages; s++)
         diffusedR = mDiffuserR[s].Process(diffusedR);

      diffusedL = mInputLpfL.Process(diffusedL);
      diffusedR = mInputLpfR.Process(diffusedR);

      if (analog)
      {
         diffusedL = AnalogDsp::AsymTanh(diffusedL, 0.12f);
         diffusedR = AnalogDsp::AsymTanh(diffusedR, 0.12f);
         mInputEnv += (std::fabs(inMono) - mInputEnv) * 0.001f;
         mInputEnv = DspMath::FlushDenormal(mInputEnv);
      }

      const float scaleFactor = 0.15f + 0.85f * size;
      const float dynamicAir = analog ? std::clamp(mInputEnv * 4.0f, 0.0f, 1.0f) : 1.0f;
      const float baseCutoff = 18000.0f * std::pow(800.0f / 18000.0f, damping);
      const float cutoffHz = analog ? std::max(600.0f, baseCutoff * (1.0f - 0.20f * (1.0f - dynamicAir))) : baseCutoff;
      const float dampCoeff = 1.0f - std::exp(-2.0f * 3.14159265f * cutoffHz / (float)mSampleRate);
      // Vintage mode wobbles further (~10 samples, tape/spring wow &
      // flutter); digital mode still modulates (~4 samples) - just enough
      // to keep the FDN's resonances from ever sitting still and ringing.
      const float modDepthSamples = analog ? 10.0f : 4.0f;

      float delayedOut[kNumLines];
      int activeLen[kNumLines];

      for (int line = 0; line < kNumLines; line++)
      {
         activeLen[line] = std::clamp((int)std::lround(kBaseLengths44k[line] * rateScale * scaleFactor), 8,
                                       mLines[line].capacity - 32);
         const float lfoVal = mLfo[line].Advance(kLfoRates[line], 0.25f, 0.08f, mSampleRate);
         const float modDelay = std::clamp((float)activeLen[line] + lfoVal * modDepthSamples, 4.0f,
                                            (float)(mLines[line].capacity - 4));
         delayedOut[line] = mLines[line].Read(modDelay);
      }

      float mixed[kNumLines];
      for (int line = 0; line < kNumLines; line++)
         mixed[line] = delayedOut[line];
      HadamardMixN(mixed, kNumLines);

      for (int line = 0; line < kNumLines; line++)
      {
         const float decayGain =
            std::pow(10.0f, -3.0f * (float)activeLen[line] / ((float)mSampleRate * decaySeconds));
         const float fb = mixed[line] * decayGain;

         FdnLine& l = mLines[line];
         l.dampState = FlushDenormal(l.dampState + dampCoeff * (fb - l.dampState));

         const float side = (line % 2 == 0) ? diffusedL : diffusedR;
         const float sign = (line < kNumLines / 2) ? 0.5f : -0.5f;
         l.Write(FlushDenormal(side * sign + l.dampState));
      }

      // Stereo spread: even lines lean left-fed, odd lean right-fed. Their
      // own decorrelated diffusion (plus modulation) keeps the tail from
      // collapsing back toward mono at low width the way one shared tank did.
      float sumEven = 0.0f, sumOdd = 0.0f;
      for (int line = 0; line < kNumLines; line++)
      {
         if (line % 2 == 0)
            sumEven += delayedOut[line];
         else
            sumOdd += delayedOut[line];
      }
      const float crossGain = 1.0f - width * 0.4f;
      const float wetL = (sumEven + crossGain * sumOdd) * outScale;
      const float wetR = (sumOdd + crossGain * sumEven) * outScale;

      out.channels[0][i] = wetL;
      if (numChannels >= 2)
         out.channels[1][i] = wetR;
      for (int ch = 2; ch < numChannels; ch++)
         out.channels[ch][i] = 0.0f;

      for (int ch = 0; ch < numChannels; ch++)
      {
         blockDryPeak = std::max(blockDryPeak, std::fabs(in.channels[ch][i]));
         blockWetPeak = std::max(blockWetPeak, std::fabs(out.channels[ch][i]));
      }
   }

   const float payload[2] = { blockDryPeak, blockWetPeak };
   mLevelMeter.Write(payload, 2);
}
