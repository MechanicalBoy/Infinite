#pragma once

#include <atomic>
#include <cmath>
#include <cstdint>
#include <vector>

#include "IEffectKernel.h"
#include "audio/DspMath.h"
#include "audio/dsp/PortableFft.h"

// Key-Snap: streaming STFT phase vocoder (N=2048, hop=512) that finds the
// spectral peaks of every frame, moves each one to the nearest note of a
// scale, and carries the peak's neighbouring bins with it (Laroche & Dolson,
// "New phase-vocoder techniques for pitch-shifting", 1999: peak-locked
// regions, identity phase locking). Polyphonic by construction - each peak
// is corrected on its own.
class AudioEffectNode;

class KeySnapKernel : public IEffectKernel
{
public:
   static constexpr int kFftSize = 2048;
   static constexpr int kLog2Fft = 11;
   static constexpr int kHopSize = 512;
   static constexpr int kNumBins = kFftSize / 2; // 1024
   static constexpr int kMaxChannels = 2;
   static constexpr int kMaxPeaks = 192;
   static constexpr int kOlaSize = 4096; // power of two, >= kFftSize + kHopSize

   struct ChannelState
   {
      std::vector<float> inputFifo;
      std::vector<float> outputOla;
      std::vector<float> phasePrev;
      // Synthesis phase and glide state, valid only at the bins a peak landed
      // on last frame (flag arrays say which).
      std::vector<float> synthPhase, synthPhaseNext;
      std::vector<float> glideSt, glideStNext;
      std::vector<uint8_t> hasSynth, hasSynthNext;
      int fifoSamples = 0;
      int olaRead = 0;

      void Init();
      void Reset();
   };

   void PrepareToPlay(double sampleRate, int maxBlockSize) override;
   void Reset() override;
   void PushParams(const AudioEffectNode& node, double sampleRate) override;
   void ProcessBlock(const AudioBuffer& in, const AudioBuffer* sidechain, AudioBuffer& out) override;

   int LatencySamples() const override { return kFftSize; }

   // Nearest in-scale note to a fractional MIDI pitch. `mask` has bit pc set
   // when pitch class pc (absolute, 0 = C) belongs to the scale. Returns the
   // fractional pitch unchanged when the mask is empty.
   static float NearestScaleNote(float midi, uint32_t mask);

   // Pitch-class mask for `scale`/`root` (MusicTime::ScaleType, 0..11).
   static uint32_t ScaleMask(int scale, int root);

private:
   // Decides the frame on `st`'s spectrum (mRe/mIm): which bins move where,
   // and by what rotation, into mMapTarget/mMapRc/mMapRs.
   void ProcessFrame(ChannelState& st);
   // Applies that mapping to one channel's own spectrum (re/im) -> mOutRe/mOutIm.
   void ApplyMapping(const float* re, const float* im);

   double mSampleRate = 44100.0;

   PortableFft::RealFft mFft;
   std::vector<float> mWindow;
   std::vector<float> mRe, mIm, mOutRe, mOutIm, mTime;
   std::vector<float> mMag, mPhaseA, mInstBin;

   // Main thread -> audio thread, one relaxed atomic per value (each is read
   // independently once per frame; a torn pair across frames is inaudible).
   std::atomic<float> mSnap { 1.0f };
   std::atomic<float> mGlideSec { 0.06f };
   std::atomic<uint32_t> mMask { 0xFFFu };

   ChannelState mChannels[kMaxChannels];

   // Stereo link. Each frame is decided once, on the mid spectrum (the
   // average of the channels' spectra, tracked by mMid's phase state), and
   // the same per-bin move and rotation is applied to every channel's own
   // spectrum - so the channels' phase and level differences (the stereo
   // image) pass through untouched and both sides always snap alike.
   // Deciding per channel let each side's synthesis phases random-walk on
   // their own and let a note exactly between two scale notes snap up on one
   // side and down on the other (DSPTEST: L/R correlation 0.89 -> 0.51).
   ChannelState mMid;
   std::vector<float> mChRe[kMaxChannels], mChIm[kMaxChannels];
   std::vector<int> mMapTarget; // per source bin: target bin, or -1 (dropped)
   std::vector<float> mMapRc, mMapRs;
   bool mMapPassthrough = false;
};
