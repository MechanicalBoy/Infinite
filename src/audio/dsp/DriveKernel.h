#pragma once

#include <algorithm>
#include <cmath>

#include "IEffectKernel.h"
#include "Oversampler.h"
#include "audio/DspMath.h"
#include "audio/ParamMailbox.h"

// Drive's kernel - one saturator (tanh waveshaper with an asymmetry/bias
// control), not the design doc's 6-mode curve dropdown (tanh / hard clip /
// foldback / bitcrush / diode / tube), per
// .claude/skills/new-audio-node/SKILL.md's minimalism rule: a dropdown that
// switches between more than two processing modes is a smell, and tanh alone
// - warm at low drive, hard-saturating at high drive - already covers the
// "overdrive to fuzz" range a single knob is expected to cover. `bias` is
// what makes this more than a one-knob toy: an asymmetric transfer curve
// produces even harmonics, the entire difference between "fuzzy" (symmetric)
// and "warm" (asymmetric) saturation, and it's cheap once tanh exists.
//
// Primary reference: the tanh soft-clipper is the standard closed-form
// saturator in the DSP literature (e.g. Zolzer, "DAFX: Digital Audio
// Effects", ch. 4's nonlinear processing survey); DspMath::FastTanh is this
// codebase's rational approximation of it (see its own comment).
//
// Anti-aliasing is built in, with no control: the curve runs at 8x the
// sample rate through Oversampler.h (half-band cascade, 73 samples of
// latency, reported to PDC), and each oversampled sample is the first-order
// antiderivative form of the curve (ADAA - Parker, Zavalishin & Le Bivic,
// "Reducing the Aliasing of Nonlinear Waveshaping Using Continuous-Time
// Convolution", DAFx-16), which removes most of what oversampling alone
// would still fold back. ALIASTEST gates the result: audible aliasing went
// from -21 dB to about -120 dB at 50% drive. ADAA's half-sample delay at 8x
// (1/16 of a base sample) is not compensated; it is inaudible. The DC blocker
// also runs // always, hardcoded (bias otherwise leaks a constant offset to the output).
class AudioEffectNode;

// Pure function so the visualizer (main-thread, params only) and the audio
// thread compute the identical curve - the same reason DynamicsDsp::
// GainComputerDb exists. Bias is subtracted back out via its own
// zero-signal shaped value, so a bias offset warps the curve's symmetry
// without visibly sliding the whole curve's DC point on the graph the way
// a raw pre-shape offset would.
namespace DriveDsp
{
   // Blends tanh (color=0, warm) toward a harder arctan saturator (color=1,
   // more aggressive/brighter clipping character) - arctan is the standard
   // alternate closed-form saturator alongside tanh in the same DAFX ch. 4
   // survey, with a harder knee at the same input level, which is exactly
   // the "warm vs. aggressive" character axis a drive unit's color/tone
   // knob is expected to cover (distinct from `tone`'s post-shape spectral
   // tilt, which doesn't touch the curve's own shape at all).
   inline float RawShape(float x, float driveDb, float bias, float color)
   {
      const float driveLin = DspMath::DbToLinear(driveDb);
      const float driven = (x + bias) * driveLin;
      const float soft = DspMath::FastTanh(driven);
      const float hard = (2.0f / (float)M_PI) * atanf(driven * 2.0f);
      return soft * (1.0f - color) + hard * color;
   }

   inline float Shape(float x, float driveDb, float bias, float color)
   {
      const float zeroRef = RawShape(0.0f, driveDb, bias, color);
      return RawShape(x, driveDb, bias, color) - zeroRef;
   }

   using DspMath::FastTanhAntiderivative;

   // Antiderivative of atan(2u): u atan(2u) - ln(1 + 4u^2) / 4.
   inline double AtanAntiderivative(double u) { return u * std::atan(2.0 * u) - 0.25 * std::log1p(4.0 * u * u); }

   // Shape()'s parameters resolved once per base-rate sample (they are
   // smoothed at that rate), so the per-oversampled-sample work below is
   // only the curve itself: no pow() for the drive gain, no zero reference.
   struct ShapeParams
   {
      double gain = 1.0, bias = 0.0, color = 0.0, zeroRef = 0.0;

      ShapeParams() = default;
      ShapeParams(float driveDb, float bias_, float color_)
         : gain((double)DspMath::DbToLinear(driveDb)), bias(bias_), color(color_),
           zeroRef((double)RawShape(0.0f, driveDb, bias_, color_))
      {
      }

      double Value(double x) const
      {
         const double u = (x + bias) * gain;
         double y = 0.0;
         if (color < 1.0)
            y += (1.0 - color) * (double)DspMath::FastTanh((float)u);
         if (color > 0.0)
            y += color * (2.0 / M_PI) * std::atan(2.0 * u);
         return y - zeroRef;
      }

      // Antiderivative of Value() with respect to x. Double precision: ADAA
      // divides the difference of two of these by a small step, and in
      // float that difference is mostly rounding.
      double Antiderivative(double x) const
      {
         const double u = (x + bias) * gain;
         double f = 0.0;
         if (color < 1.0)
            f += (1.0 - color) * FastTanhAntiderivative(u);
         if (color > 0.0)
            f += color * (2.0 / M_PI) * AtanAntiderivative(u);
         return f / gain - zeroRef * x;
      }
   };

   // First-order ADAA of Shape() between the previous input and this one:
   // the average of the curve over the straight line joining them, instead
   // of its value at one point. Falls back to the midpoint value when the
   // step is too small for the difference quotient to be meaningful.
   struct Adaa
   {
      double prevX = 0.0;
      double prevF = 0.0;
      bool primed = false;

      void Reset() { primed = false; }

      float Process(float x, const ShapeParams& p)
      {
         const double F = p.Antiderivative(x);
         double y;
         const double dx = (double)x - prevX;
         if (!primed)
            y = p.Value(x);
         else if (std::fabs(dx) < 1.0e-5)
            y = p.Value(0.5 * ((double)x + prevX));
         else
            y = (F - prevF) / dx;
         prevX = x;
         prevF = F;
         primed = true;
         return (float)y;
      }
   };
}

// The always-on DC blocker after the shaper (8 Hz) - DspMath::DcBlocker.
using DcBlocker = DspMath::DcBlocker;

// Bipolar tilt around a fixed 1 kHz pivot, the same construction
// DelayKernel.h's DelayToneFilter uses for its feedback-path tone control -
// negative darkens, positive brightens, y=x exactly at tone=0.
struct DriveToneFilter
{
   DspMath::TptSvf svf;

   void Reset() { svf.Reset(); }

   float Process(float x, float tone, float sampleRate)
   {
      if (tone != 0.0f)
      {
         svf.SetSampleRate(sampleRate);
         svf.SetCutoff(1000.0f, 0.707f);
         const DspMath::TptSvf::Outputs o = svf.Process(x);
         x = x + tone * (o.high - o.low) * 0.5f;
      }
      return x;
   }
};

class DriveKernel : public IEffectKernel
{
public:
   static constexpr int kMaxChannels = 8;

   enum ParamSlot
   {
      kDriveDb = 0,
      kBias,
      kTone,
      kColor,
      kOutputDb,
      kNumSlots
   };

   static constexpr int kOversample = 8;

   void PrepareToPlay(double sampleRate, int /*maxBlockSize*/) override
   {
      mSampleRate = sampleRate;
      mMailbox.PrepareToPlay(sampleRate);
      mOversampler.Prepare(kOversample);
      for (int ch = 0; ch < kMaxChannels; ch++)
         mDcBlockers[ch].SetSampleRate(sampleRate);
      Reset();
   }

   void Reset() override
   {
      mOversampler.Reset();
      for (int ch = 0; ch < kMaxChannels; ch++)
      {
         mAdaa[ch].Reset();
         mDcBlockers[ch].Reset();
         mToneFilters[ch].Reset();
      }
   }

   void PushParams(const AudioEffectNode& node, double sampleRate) override;

   void ProcessBlock(const AudioBuffer& in, const AudioBuffer* sidechain, AudioBuffer& out) override;

   int LatencySamples() const override { return mOversampler.Latency(); }

private:
   ParamMailbox mMailbox;
   double mSampleRate = 44100.0; // written by PrepareToPlay only (audio-thread owned)

   Oversampler mOversampler;
   DriveDsp::Adaa mAdaa[kMaxChannels];
   DcBlocker mDcBlockers[kMaxChannels];
   DriveToneFilter mToneFilters[kMaxChannels];
};
