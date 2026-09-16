#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>

#include "platform/Platform.h"

// One channel of a planar Platform::SampleBuffer at a fractional frame
// position, linearly interpolated (the file's rate can differ from the
// engine's, so read positions are generally non-integral). A channel the file
// does not have reads as its last real channel, so a mono file feeds both
// sides of a stereo output. Out-of-range positions read as silence.
inline float ReadBufferInterp(const Platform::SampleBuffer& buf, int channel, double pos)
{
   const int64_t i0 = (int64_t)std::floor(pos);
   if (i0 < 0 || i0 >= buf.numFrames || buf.channels <= 0)
      return 0.0f;
   const int ch = std::min(channel, buf.channels - 1);
   const float* data = buf.channelData.data() + (size_t)ch * (size_t)buf.numFrames;
   const int64_t i1 = i0 + 1;
   const float s0 = data[i0];
   const float s1 = (i1 < buf.numFrames) ? data[i1] : s0;
   const float frac = (float)(pos - (double)i0);
   return s0 + (s1 - s0) * frac;
}

// Channel 0 only - kept for callers that analyse rather than play.
inline float ReadBufferInterp(const Platform::SampleBuffer& buf, double pos)
{
   return ReadBufferInterp(buf, 0, pos);
}

// Real-time-safe, allocation-free WSOLA time-stretcher over a fully decoded,
// randomly addressable buffer (stereo). `ratio` is SOURCE frames consumed per
// OUTPUT (ring) frame: > 1 plays the source faster, < 1 slower, pitch
// unchanged.
//
// Position contract - the property the Arrangement Timeline depends on:
// after Reset(sourceFrame, writeFrame, ratio), ring frame x holds source
// content centred on sourceFrame + (x - writeFrame) * ratio, to within the
// alignment search radius, for as long as the stretcher runs. The nominal
// source position advances by exactly kHop * ratio per hop and is NEVER fed
// back from the similarity search's chosen window start, so the per-hop
// alignment nudges cannot accumulate into drift (the previous version set
// next = nudgedStart + hop*ratio, a random walk away from the timeline).
//
// Reset pre-rolls three hops before writeFrame, so the ring is already at
// full overlap by the first frame the caller reads - a seek does not fade in.
class WsolaStretcher
{
public:
   static constexpr int kWindow = 1024;
   static constexpr int kHalfWindow = kWindow / 2;
   static constexpr int kHop = kWindow / 4;         // 75% overlap, COLA for Hann
   static constexpr int kOverlap = kWindow - kHop;
   static constexpr int kSearch = 128;              // +/- alignment radius, frames
   static constexpr int kCorrLength = 512;          // frames compared per candidate
   static constexpr int kPreRollHops = 3;
   static constexpr int kChannels = 2;
   static constexpr int kRingSize = 8192;
   static constexpr int kRingMask = kRingSize - 1;

   WsolaStretcher()
   {
      constexpr double kTwoPi = 6.283185307179586476925286766559;
      // Periodic Hann (divide by N, not N-1): exactly constant-overlap-add
      // at a hop of N/4, so an unstretched signal reconstructs flat.
      for (int i = 0; i < kWindow; i++)
         mHann[i] = 0.5f - 0.5f * (float)std::cos(kTwoPi * (double)i / (double)kWindow);
      double total = 0.0;
      for (int k = 0; k < kWindow / kHop; k++)
         total += mHann[k * kHop];
      mGainComp = (total > 1e-6) ? (float)(1.0 / total) : 1.0f;
      Reset(0.0, 0, 1.0);
   }

   void Reset(double sourceFrame, int64_t writeFrame, double ratio)
   {
      const int64_t firstWindow = writeFrame - (int64_t)kPreRollHops * kHop;
      mWritten = firstWindow;
      mCenterSource = sourceFrame + (double)(firstWindow + kHalfWindow - writeFrame) * ratio;
      mHavePrev = false;
      for (int ch = 0; ch < kChannels; ch++)
         std::fill(std::begin(mOla[ch]), std::end(mOla[ch]), 0.0f);
   }

   // Generates hops until the ring holds finished output through
   // `throughFrame` (ring/write-domain units).
   void GenerateUpTo(double throughFrame, double ratio, const Platform::SampleBuffer& buf)
   {
      while ((double)mWritten < throughFrame)
         GenerateOneHop(ratio, buf);
   }

   float Read(int channel, double pos) const
   {
      const int ch = std::clamp(channel, 0, kChannels - 1);
      const int64_t i0 = (int64_t)std::floor(pos);
      const float frac = (float)(pos - (double)i0);
      const float s0 = mRing[ch][i0 & kRingMask];
      const float s1 = mRing[ch][(i0 + 1) & kRingMask];
      return s0 + (s1 - s0) * frac;
   }

   int64_t Written() const { return mWritten; }

private:
   static float Frame(const Platform::SampleBuffer& buf, int ch, int64_t i)
   {
      if (i < 0 || i >= buf.numFrames || buf.channels <= 0)
         return 0.0f;
      const int c = std::min(ch, buf.channels - 1);
      return buf.channelData[(size_t)c * (size_t)buf.numFrames + (size_t)i];
   }

   static float Mid(const Platform::SampleBuffer& buf, int64_t i)
   {
      if (buf.channels < 2)
         return Frame(buf, 0, i);
      return 0.5f * (Frame(buf, 0, i) + Frame(buf, 1, i));
   }

   // Normalised cross-correlation of the candidate window start against the
   // natural continuation of the previous window, on the mid signal.
   static double Score(const Platform::SampleBuffer& buf, int64_t cand, int64_t ref, int stride, bool* silent)
   {
      double num = 0.0, candEnergy = 0.0, refEnergy = 0.0;
      for (int j = 0; j < kCorrLength; j += stride)
      {
         const double c = Mid(buf, cand + j);
         const double r = Mid(buf, ref + j);
         num += c * r;
         candEnergy += c * c;
         refEnergy += r * r;
      }
      if (silent) *silent = refEnergy < 1e-10;
      return candEnergy > 1e-12 ? num / std::sqrt(candEnergy) : -1e30;
   }

   int64_t FindBestStart(const Platform::SampleBuffer& buf, int64_t nominal) const
   {
      const int64_t ref = mPrevStart + kHop;
      bool silent = false;
      Score(buf, ref, ref, 4, &silent);
      if (silent)
         return nominal;
      // Coarse pass every 2 frames with a 2-frame stride, then refine +/-2.
      int64_t best = nominal;
      double bestScore = -1e30;
      for (int64_t off = -kSearch; off <= kSearch; off += 2)
      {
         const double s = Score(buf, nominal + off, ref, 2, nullptr);
         if (s > bestScore) { bestScore = s; best = nominal + off; }
      }
      const int64_t coarse = best;
      bestScore = -1e30;
      for (int64_t off = -2; off <= 2; off++)
      {
         const int64_t cand = coarse + off;
         if (cand < nominal - kSearch || cand > nominal + kSearch)
            continue;
         const double s = Score(buf, cand, ref, 1, nullptr);
         if (s > bestScore) { bestScore = s; best = cand; }
      }
      return best;
   }

   void GenerateOneHop(double ratio, const Platform::SampleBuffer& buf)
   {
      const int64_t nominal = (int64_t)std::llround(mCenterSource - (double)kHalfWindow);
      const int64_t start = mHavePrev ? FindBestStart(buf, nominal) : nominal;

      for (int ch = 0; ch < kChannels; ch++)
      {
         float* ola = mOla[ch];
         for (int j = 0; j < kWindow; j++)
            ola[j] += Frame(buf, ch, start + j) * mHann[j];
         for (int j = 0; j < kHop; j++)
            mRing[ch][(mWritten + j) & kRingMask] = ola[j] * mGainComp;
         std::memmove(ola, ola + kHop, kOverlap * sizeof(float));
         std::fill(ola + kOverlap, ola + kWindow, 0.0f);
      }
      mWritten += kHop;
      mPrevStart = start;
      mHavePrev = true;
      mCenterSource += (double)kHop * ratio;
   }

   float mHann[kWindow] = {};
   float mGainComp = 1.0f;
   float mOla[kChannels][kWindow] = {};
   float mRing[kChannels][kRingSize] = {};

   double mCenterSource = 0.0; // nominal source frame at the centre of the next window
   int64_t mPrevStart = 0;
   int64_t mWritten = 0;       // ring frames finalised so far
   bool mHavePrev = false;
};
