#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>

#include "platform/Platform.h"

// The file's decoded sample rate can differ from the engine's running rate
// (e.g. a 44.1kHz file with a 48kHz engine), so pos is generally non-integral
// - linearly interpolate between the two nearest frames. Channel 0 only, same
// simplification SamplerNode's ReadSample makes for a multi-channel file.
// Free function (not a member) so WsolaStretcher below can share it with
// every caller (AudioFilePlayerAudioNode, Arrangement Timeline Audio Sample
// voices).
inline float ReadBufferInterp(const Platform::SampleBuffer& buf, double pos)
{
   const int64_t i0 = (int64_t)std::floor(pos);
   if (i0 < 0 || i0 >= buf.numFrames)
      return 0.0f;
   const int64_t i1 = i0 + 1;
   const float s0 = buf.channelData[i0];
   const float s1 = (i1 < buf.numFrames) ? buf.channelData[i1] : s0;
   const float frac = (float)(pos - (double)i0);
   return s0 + (s1 - s0) * frac;
}

// Real-time-safe WSOLA (Waveform-Similarity Overlap-Add) time-stretcher.
// Reads channel 0 of a fully-decoded Platform::SampleBuffer and produces a
// stretched signal at a caller-chosen ratio - ratio > 1 consumes the source
// faster than real time (shorter/compressed), ratio < 1 slower
// (longer/expanded) - WITHOUT changing pitch. Originally lived only inside
// AudioFilePlayerAudioNode (Arrangement Timeline BPM-sync via
// SetClipRateOverride); extracted here so the Arrangement Timeline's
// self-contained Audio Sample voices can share the exact same algorithm
// without either duplicating it or routing Sample playback through a canvas
// node.
//
// Because the source is a fully in-memory, randomly-addressable buffer (not
// a stream), the whole thing can stay allocation-free: every buffer here is a
// fixed-size member, and "seeking" is just repointing the analysis cursor -
// no lookahead ring or background decode thread needed.
//
// Algorithm: fixed-size synthesis windows (kWindow, 75% overlap at kHop) are
// pulled from the source, Hann-windowed, and overlap-added into a small ring
// buffer that the caller drains at its own pace (Read()). The analysis
// position advances by kHop*ratio source-frames per hop - the actual time
// warp - while a short cross-correlation search (kSearch) nudges each new
// window's source offset to whatever position best continues the waveform
// already sitting in the not-yet-finalized overlap region, which is what
// keeps the seam between windows from phasing/combing. At ratio == 1.0 this
// degenerates to plain, unshifted overlap-add reconstruction (the search is
// skipped entirely - center of a silent reference on the very first hop, and
// a needless-but-harmless perfect-alignment search after that would just
// keep finding offset 0 anyway), so audio thread cost when nothing is
// actually being stretched stays a Hann-window multiply-accumulate, not a
// full correlation search.
class WsolaStretcher
{
public:
   static constexpr int kWindow = 1024;                    // ~23ms @44.1kHz
   static constexpr int kHop = kWindow / 4;                 // 75% overlap - COLA-exact for Hann
   static constexpr int kOverlap = kWindow - kHop;
   static constexpr int kSearch = 128;                      // +/- alignment search radius, frames
   static constexpr int kRingSize = 8192;                   // power of two, generous vs. one hop of lookahead
   static constexpr int kRingMask = kRingSize - 1;

   WsolaStretcher()
   {
      // M_PI isn't standard C++ (absent on MSVC without _USE_MATH_DEFINES) -
      // a local constant matches the convention the rest of the audio DSP
      // code already uses (see MolderDsp.cpp's kTwoPi/kPi).
      constexpr double kTwoPi = 6.283185307179586476925286766559;
      for (int i = 0; i < kWindow; i++)
         mHann[i] = 0.5f - 0.5f * (float)std::cos(kTwoPi * (double)i / (double)(kWindow - 1));

      // Hann at 75% overlap is COLA (constant overlap-add) but not
      // COLA-unity - measure the actual constant here instead of hardcoding
      // a textbook value, so a later change to kWindow/kHop can't silently
      // start pumping the output level.
      double total = 0.0;
      for (int k = -8; k <= 8; k++)
      {
         const int idx = 0 - k * kHop;
         if (idx >= 0 && idx < kWindow)
            total += mHann[idx];
      }
      mGainComp = (total > 1e-6) ? (float)(1.0 / total) : 1.0f;

      Reset(0.0, 0);
   }

   // Drops all generated content and starts fresh - `analysisFrame` is where
   // in the SOURCE to resume reading (native file-frame units), `writeFrame`
   // is the ring/write-domain position this resumption corresponds to for the
   // caller (normally the caller's own read cursor at the moment of reset, so
   // Read() right after Reset()+one GenerateUpTo() picks up with no gap).
   // Called on seek, restart, and a fresh buffer swap-in.
   void Reset(double analysisFrame, int64_t writeFrame)
   {
      mAnalysisPos = analysisFrame;
      mStretchWritten = writeFrame;
      mSourceExhausted = false;
      mRingEndPos = -1.0;
      std::fill(std::begin(mOlaAccum), std::end(mOlaAccum), 0.0f);
      mHavePrevWindow = false;
   }

   // Generates hops until the ring holds valid content through `throughFrame`
   // (ring/write-domain units) or the source has run out (loop == false).
   void GenerateUpTo(double throughFrame, float ratio, bool loop, const Platform::SampleBuffer& buf)
   {
      while (!mSourceExhausted && (double)mStretchWritten < throughFrame)
         GenerateOneHop(ratio, loop, buf);
   }

   // Ring/write-domain read, linear-interpolated. Caller must already have
   // called GenerateUpTo(pos + 1 or more, ...). Returns 0 past Exhausted()'s
   // end position.
   float Read(double pos) const
   {
      if (mRingEndPos >= 0.0 && pos >= mRingEndPos)
         return 0.0f;
      const int64_t i0 = (int64_t)std::floor(pos);
      const float frac = (float)(pos - (double)i0);
      const float s0 = mRing[i0 & kRingMask];
      const float s1 = mRing[(i0 + 1) & kRingMask];
      return s0 + (s1 - s0) * frac;
   }

   // True once the source has run out with loop off. `endPos` (ring/write-
   // domain units, comparable to Read()'s argument) is where playback should
   // stop - the WSOLA equivalent of the old "mPos >= numFrames" check, which
   // can no longer be done by comparing directly against the source's own
   // frame count once ring-domain and source-domain length can differ.
   bool Exhausted(double* endPos) const
   {
      if (mRingEndPos < 0.0)
         return false;
      if (endPos) *endPos = mRingEndPos;
      return true;
   }

   // Main thread (via an atomic snapshot) - how far into the actual source
   // file playback has reached, for AudioFileNode::Position()'s waveform
   // playhead. Audio-thread-only to call directly.
   double AnalysisFrame() const { return mAnalysisPos; }

private:
   void GenerateOneHop(float ratio, bool loop, const Platform::SampleBuffer& buf)
   {
      const bool stretching = std::fabs(ratio - 1.0f) > 0.002f;

      // mOlaAccum[0..kOverlap) already holds every contribution placed by
      // earlier windows for this position (nothing has added THIS window's
      // contribution yet) - exactly the "what's already committed to the
      // output here" reference WSOLA's alignment search wants. Skipped on
      // the very first hop (that reference would be silence) and whenever
      // nothing is actually being stretched (see this function's own
      // no-search fast path in the class comment).
      const double start = (mHavePrevWindow && stretching)
         ? FindBestOffset(buf)
         : mAnalysisPos;

      float windowed[kWindow];
      for (int j = 0; j < kWindow; j++)
         windowed[j] = ReadBufferInterp(buf, start + (double)j) * mHann[j];
      for (int j = 0; j < kWindow; j++)
         mOlaAccum[j] += windowed[j];

      // The front kHop samples can never receive another contribution (the
      // next window starts at least kHop frames later) - they're final.
      for (int j = 0; j < kHop; j++)
      {
         mRing[mStretchWritten & kRingMask] = mOlaAccum[j] * mGainComp;
         mStretchWritten++;
      }
      std::memmove(mOlaAccum, mOlaAccum + kHop, kOverlap * sizeof(float));
      std::fill(mOlaAccum + kOverlap, mOlaAccum + kWindow, 0.0f);
      mHavePrevWindow = true;

      mAnalysisPos = start + (double)kHop * (double)ratio;
      if (mAnalysisPos >= (double)buf.numFrames)
      {
         if (loop && buf.numFrames > 0)
            mAnalysisPos = std::fmod(mAnalysisPos, (double)buf.numFrames);
         else
         {
            mSourceExhausted = true;
            mRingEndPos = (double)mStretchWritten;
         }
      }
   }

   // Normalized cross-correlation search over +/-kSearch frames around
   // mAnalysisPos, against the not-yet-finalized overlap already sitting in
   // mOlaAccum - the standard WSOLA "waveform similarity" step that keeps
   // consecutive windows in phase so the overlap-add doesn't comb-filter.
   double FindBestOffset(const Platform::SampleBuffer& buf) const
   {
      double bestOffset = 0.0;
      float bestScore = -1.0f;
      for (int s = -kSearch; s <= kSearch; s++)
      {
         double num = 0.0, denom = 0.0;
         for (int j = 0; j < kOverlap; j++)
         {
            const float cand = ReadBufferInterp(buf, mAnalysisPos + (double)s + (double)j);
            num += (double)cand * (double)mOlaAccum[j];
            denom += (double)cand * (double)cand;
         }
         const float score = (denom > 1e-9) ? (float)(num / std::sqrt(denom)) : 0.0f;
         if (score > bestScore)
         {
            bestScore = score;
            bestOffset = (double)s;
         }
      }
      return mAnalysisPos + bestOffset;
   }

   float mHann[kWindow] = {};
   float mGainComp = 1.0f;
   float mOlaAccum[kWindow] = {};
   bool mHavePrevWindow = false;

   double mAnalysisPos = 0.0;      // next analysis window start, native source frames
   int64_t mStretchWritten = 0;    // ring/write-domain frames generated so far
   bool mSourceExhausted = false;
   double mRingEndPos = -1.0;      // valid once mSourceExhausted, see Exhausted()

   float mRing[kRingSize] = {};
};
