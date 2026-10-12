#include "ModulatorNodes.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <sstream>

#include "Transport.h"
#include "audio/AudioNode.h"
#include "audio/MusicTime.h"

constexpr int PatternNode::kSteps;

namespace
{
   const std::vector<std::string> kLfoShapes = {
      "Sine", "Triangle", "Saw Up", "Saw Down", "Square", "Sample & Hold"
   };

   float Frac(double v) { return (float)(v - std::floor(v)); }

   // Deterministic hash so a given step always yields the same value; the pattern
   // repeats identically after a rewind instead of drifting.
   float Hash01(long long n)
   {
      unsigned long long x = (unsigned long long)(n * 2654435761u + 1013904223u);
      x ^= x >> 33;
      x *= 0xff51afd7ed558ccdULL;
      x ^= x >> 33;
      return (float)((x >> 11) & 0xFFFFFF) / (float)0xFFFFFF;
   }

   // Seeded hash for the maths-1 Random and S&H. Every bit of the seed
   // reaches the salt, so two different seeds never share a sequence, and
   // the arithmetic is unsigned throughout.
   uint64_t Mix64(uint64_t x)
   {
      x += 0x9E3779B97F4A7C15ULL;
      x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
      x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
      return x ^ (x >> 31);
   }
   uint64_t SeedSalt(float seed, uint64_t stream)
   {
      uint32_t bits = 0;
      if (seed != 0.0f) // -0 and +0 are the same seed
         std::memcpy(&bits, &seed, sizeof bits);
      return Mix64((uint64_t)bits ^ (stream << 32));
   }
   float HashSeeded(long long step, uint64_t salt)
   {
      return (float)(Mix64((uint64_t)step ^ salt) >> 40) / (float)0xFFFFFF;
   }

   // Cycles (or steps) per beat-or-second for the shared rate modes. Hz is
   // per second, the others per beat.
   double PeriodBeatsFor(int rateMode, float rateBeats, SyncedPeriodCache& cache)
   {
      // Synced: a rate on a MusicTime division runs at the division's exact
      // period (a float triplet is ~3e-8 off it). A rate off the menu (a cable
      // on the hidden rate slot, a Field kernel's set(osc, "rateBeats", t))
      // stays continuous, so modulating rate never steps.
      if (rateMode == LFONode::kRateSynced)
      {
         // Only the bar divisions follow the time signature, so only they
         // read it per call.
         const Transport& tr = Transport::Instance();
         if (cache.Hit(rateBeats, tr))
            return cache.period;
         const MusicTime::RateDivision d = MusicTime::NearestRateDivision((double)rateBeats);
         const double div = MusicTime::BeatsFor(d);
         const bool onDivision = std::fabs(div - (double)rateBeats) <= 1.0e-5 * div;
         const bool barBased = d == MusicTime::k4Bars || d == MusicTime::k2Bars || d == MusicTime::k1Bar;
         cache.rate = rateBeats;
         cache.sigNum = onDivision && barBased ? tr.TimeSigNumerator() : -1;
         cache.sigDen = onDivision && barBased ? tr.TimeSigDenominator() : -1;
         cache.period = onDivision ? div : (double)std::max(0.01f, rateBeats);
         return cache.period;
      }
      return std::max(0.01f, rateBeats);
   }
   double RatePosition(int rateMode, float rateBeats, float rateHz, SyncedPeriodCache& cache)
   {
      Transport& tr = Transport::Instance();
      if (rateMode == LFONode::kRateHz)
         return tr.Seconds() * (double)std::max(0.001f, rateHz);
      return tr.Beats() / PeriodBeatsFor(rateMode, rateBeats, cache);
   }

   float Remap(float v01, float low, float high)
   {
      // Value01() is contractually 0..1 regardless of what low/high were
      // typed as, so the mapped result is clamped back into that range too -
      // low > high (an inverted swing) stays legitimate, but low/high outside
      // 0..1 must not leak out of contract.
      float mapped = low + (high - low) * std::min(1.0f, std::max(0.0f, v01));
      return std::min(1.0f, std::max(0.0f, mapped));
   }
}

// ---------------------------------------------------------------- LFO

INode* LFONode::Create()
{
   auto* node = new LFONode();
   node->seed = NextSeed();
   return node;
}

const std::vector<std::string>& LFONode::ShapeNames()
{
   return kLfoShapes;
}

const std::vector<std::string>& LFONode::RateModeNames()
{
   static const std::vector<std::string> kNames = { "beats", "synced", "Hz" };
   return kNames;
}

const std::vector<std::string>& LFONode::PhaseModeNames()
{
   static const std::vector<std::string> kNames = { "transport", "free", "retrigger" };
   return kNames;
}

double LFONode::PeriodBeats() const
{
   return PeriodBeatsFor(rateMode, rateBeats, mPeriodCache);
}

// Free and Retrigger: cycles accumulated over FreeSeconds, at the current
// rate, so a tempo or rate change bends the speed without jumping the phase.
// Memoised on the clock like every stateful modulator. A render starts from
// phase 0 so it repeats; a retrigger edge is placed where the trig input
// crosses 0.5 on the straight line between calls.
double LFONode::FreeCycles()
{
   Transport& tr = Transport::Instance();
   const double now = tr.FreeSeconds();
   if (now == mFreeLast)
      return mFreeCycles;
   const bool offline = tr.IsOfflineMode();
   double dt = mFreeLast < 0.0 ? 0.0 : now - mFreeLast;
   if (offline != mFreeOffline)
   {
      mFreeOffline = offline;
      mFreeCycles = 0.0;
      dt = 0.0;
   }
   if (dt < 0.0 || dt > 1.0)
      dt = 0.0; // the clock changed domain (engine restart): hold, don't jump
   mFreeLast = now;

   const double perSecond = rateMode == kRateHz ? (double)std::max(0.001f, rateHz)
                                                : (tr.Tempo() / 60.0) / PeriodBeats();
   const float trig = trigger != nullptr ? trigger->Value01() : 0.0f;
   if (phaseMode == kPhaseRetrigger && trig >= 0.5f && mTrigLast < 0.5f)
   {
      const float f = trig > mTrigLast ? std::clamp((0.5f - mTrigLast) / (trig - mTrigLast), 0.0f, 1.0f) : 1.0f;
      mFreeCycles = (1.0 - f) * dt * perSecond;
   }
   else
      mFreeCycles += dt * perSecond;
   mTrigLast = trig;
   return mFreeCycles;
}

float LFONode::Value01()
{
   double cycles;
   if (phaseMode == kPhaseFree || phaseMode == kPhaseRetrigger)
      cycles = FreeCycles();
   else if (rateMode == kRateBeats)
   {
      // Exactly the expression saved patches were made with.
      const double beats = Transport::Instance().Beats();
      const float rate = std::max(0.01f, rateBeats);
      cycles = beats / rate;
   }
   else
   {
      const Transport& tr = Transport::Instance();
      cycles = rateMode == kRateSynced && mPeriodCache.Hit(rateBeats, tr) ? tr.Beats() / mPeriodCache.period // memo hit
                                                                          : RatePosition(rateMode, rateBeats, rateHz, mPeriodCache);
   }
   const float t = Frac(cycles + phase);

   float raw = 0.0f;
   switch (shape)
   {
      case 0: raw = 0.5f + 0.5f * std::sin(t * 6.28318530718f); break;      // Sine
      case 1: raw = t < 0.5f ? t * 2.0f : 2.0f - t * 2.0f; break;           // Triangle
      case 2: raw = t; break;                                               // Saw Up
      case 3: raw = 1.0f - t; break;                                        // Saw Down
      case 4: raw = t < 0.5f ? 0.0f : 1.0f; break;                          // Square
      default:                                                              // S&H
      {
         const long long step = (long long)std::floor(cycles + phase);
         raw = maths >= 1 ? HashSeeded(step, SeedSalt(seed, 1)) : Hash01(step);
         break;
      }
   }

   return Remap(raw, low, high);
}

// ---------------------------------------------------------------- Random

float RandomNode::ValueForStep(long long step, uint64_t salt) const
{
   if (maths >= 1)
      return HashSeeded(step, salt);
   // The seed is mixed into the hash input rather than added to the result, so
   // two seeds give genuinely different sequences instead of the same sequence
   // offset by a constant.
   const long long legacySalt = (long long)(seed * 1013.0f);
   return Hash01(step * 6364136223LL + legacySalt * 1442695040888963407LL);
}

float RandomNode::Value01()
{
   double pos;
   if (rateMode == LFONode::kRateBeats)
   {
      const double beats = Transport::Instance().Beats();
      const float rate = std::max(0.01f, rateBeats);
      pos = beats / rate;
   }
   else
   {
      const Transport& tr = Transport::Instance();
      pos = rateMode == LFONode::kRateSynced && mPeriodCache.Hit(rateBeats, tr) ? tr.Beats() / mPeriodCache.period // memo hit
                                                                                : RatePosition(rateMode, rateBeats, rateHz, mPeriodCache);
   }
   const long long step = (long long)std::floor(pos);
   const float t = Frac(pos);

   const uint64_t salt = maths >= 1 ? SeedSalt(seed, 2) : 0;
   const float current = ValueForStep(step, salt);

   float raw = current;
   if (smooth > 0.0f)
   {
      const float next = ValueForStep(step + 1, salt);
      // ease only across the tail of the step, scaled by the smooth amount
      float k = std::min(1.0f, t / std::max(0.0001f, smooth));
      float eased = k * k * (3.0f - 2.0f * k);
      raw = current + (next - current) * eased;
   }

   return Remap(raw, low, high);
}

// ---------------------------------------------------------------- Pattern

int PatternNode::EffectiveLength() const
{
   return std::clamp(length, 1, kSteps);
}

float PatternNode::Value01()
{
   const int count = EffectiveLength();
   const double beats = Transport::Instance().Beats();
   const float rate = std::max(0.01f, stepBeats);
   const double pos = beats / rate;
   const long long stepIndex = (long long)std::floor(pos);

   const int i = (int)(((stepIndex % count) + count) % count);
   mCurrentStep = i;

   float raw = steps[i];
   if (smoothSteps)
   {
      const int nextI = (i + 1) % count;
      const float t = Frac(pos);
      const float eased = t * t * (3.0f - 2.0f * t);
      raw = steps[i] + (steps[nextI] - steps[i]) * eased;
   }

   return Remap(raw, low, high);
}

// ---------------------------------------------------------------- Math

namespace
{
   const std::vector<std::string> kMathOps = {
      "A + B", "A - B", "A * B", "A / B", "min(A,B)", "max(A,B)",
      "average", "difference", "A only", "B only"
   };
}

const std::vector<std::string>& MathNode::OpNames()
{
   return kMathOps;
}

float MathNode::Value01()
{
   const float a = inputA ? inputA->Value01() : constantA;
   const float b = inputB ? inputB->Value01() : constantB;

   float r;
   switch (op)
   {
      case 0: r = a + b; break;
      case 1: r = a - b; break;
      case 2: r = a * b; break;
      case 3: r = a / std::max(b, 1e-4f); break;
      case 4: r = std::min(a, b); break;
      case 5: r = std::max(a, b); break;
      case 6: r = (a + b) * 0.5f; break;
      case 7: r = std::fabs(a - b); break;
      case 8: r = a; break;
      default: r = b; break;
   }

   r = r * gain + offset;
   return clampOutput ? std::min(1.0f, std::max(0.0f, r)) : r;
}

// ---------------------------------------------------------------- Compare

namespace
{
   const std::vector<std::string> kCompareOps = {
      "A > B", "A >= B", "A < B", "A <= B", "A == B", "A != B"
   };
}

const std::vector<std::string>& CompareNode::OpNames()
{
   return kCompareOps;
}

float CompareNode::Value01()
{
   const float a = inputA ? inputA->Value01() : constantA;
   const float b = inputB ? inputB->Value01() : constantB;
   const float tol = std::max(0.0f, tolerance);

   bool result;
   switch (op)
   {
      case 0: result = a > b; break;
      case 1: result = a >= b - tol; break;
      case 2: result = a < b; break;
      case 3: result = a <= b + tol; break;
      case 4: result = std::fabs(a - b) <= tol; break;
      default: result = std::fabs(a - b) > tol; break; // A != B
   }

   return result ? 1.0f : 0.0f;
}

// ---------------------------------------------------------------- Range to Range

float RangeToRangeNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;
   const float v = input ? input->Value01() : constantIn;
   const float span = inHigh - inLow;
   const float t = std::fabs(span) > 1e-6f ? (v - inLow) / span : 0.0f;
   const float r = outLow + (outHigh - outLow) * t;
   if (!clampOutput) return r;
   return std::min(std::max(outLow, outHigh), std::max(std::min(outLow, outHigh), r));
}

// ---------------------------------------------------------------- Smooth

double SmoothNode::AmountTau(float amount)
{
   const double k = std::clamp((double)amount, 0.0, 0.99);
   return k <= 0.0 ? 0.0 : (1.0 / 60.0) / -std::log(k);
}

// maths 1: every mode steps by transport seconds and treats the input as a
// straight line from the previous call's value, so the curve is the same
// at any frame rate (Modulation::SmoothStep / SpringStep, both exact).
float SmoothNode::ValueExact(float target)
{
   const double now = Transport::Instance().Seconds();
   if (mInit && now == mLastSeconds)
      return mLast; // fan-out: already advanced for this instant
   const double dt = now - mLastSeconds;
   mLastSeconds = now;
   if (!mInit || dt <= 0.0 || dt > 1.0)
   {
      // First call, a seek or a long gap: snap rather than glide across it.
      mInit = true;
      mLast = mPrevIn = target;
      mVel = 0.0f;
      return mLast;
   }

   if (mode == kSpring)
   {
      double y = mLast, v = mVel;
      Modulation::SpringStep(y, v, mPrevIn, target, dt, 6.283185307179586 * std::max(0.05f, frequency),
                             std::max(0.0f, damping));
      mLast = (float)y;
      mVel = (float)v;
      if (!std::isfinite(mLast) || !std::isfinite(mVel))
      {
         mLast = target;
         mVel = 0.0f;
      }
   }
   else
   {
      if (mode != kTime && amount != mTauAmount)
      {
         mTauAmount = amount; // the log runs when amount moves, not per call
         mTau = AmountTau(amount);
      }
      const double tau = mode == kTime ? (double)std::max(0.001f, timeConstant) : mTau;
      mLast = tau > 0.0 ? (float)Modulation::SmoothStep(mLast, mPrevIn, target, dt, tau) : target;
   }
   mPrevIn = target;
   return mLast;
}

float SmoothNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;
   const float target = input ? input->Value01() : constantIn;
   if (maths >= 1)
      return ValueExact(target);
   if (mode == kPerFrame)
   {
      const double beats = Transport::Instance().Beats();
      if (mInit && beats == mLastBeats)
         return mLast; // already advanced this tick - don't double-apply the filter

      const float k = std::min(1.0f, std::max(0.0f, amount));
      mLast = !mInit ? target : mLast + (target - mLast) * (1.0f - k);
      mInit = true;
      mLastBeats = beats;
      return mLast;
   }

   const double now = Transport::Instance().Seconds();
   if (mInit && now == mLastSeconds)
      return mLast; // fan-out: already advanced for this instant

   const double dt = now - mLastSeconds;
   mLastSeconds = now;
   // First call, a seek backwards or a long gap: snap rather than glide across it.
   if (!mInit || dt < 0.0 || dt > 1.0)
   {
      mInit = true;
      mLast = target;
      mVel = 0.0f;
      return mLast;
   }

   if (mode == kTime)
   {
      const float tc = std::max(0.001f, timeConstant);
      mLast += (target - mLast) * (1.0f - std::exp(-(float)dt / tc));
      return mLast;
   }

   // Spring: x'' = w^2 (target - x) - 2 z w v, semi-implicit Euler in substeps
   // small enough to stay stable at any stiffness the knob allows.
   const float w = 6.2831853f * std::max(0.05f, frequency);
   const float z = std::max(0.0f, damping);
   // dt is capped (a hitch just takes a slower glide) and the step is bounded by
   // both stiffness and damping, so h*w*(1+z) stays well under 1 at every knob value.
   const float sdt = (float)std::min(dt, 0.1);
   const int steps = std::min(256, std::max(1, (int)std::ceil(sdt * w * (1.0f + z) * 4.0f)));
   const float h = sdt / (float)steps;
   for (int i = 0; i < steps; ++i)
   {
      mVel += (w * w * (target - mLast) - 2.0f * z * w * mVel) * h;
      mLast += mVel * h;
   }
   if (!std::isfinite(mLast) || !std::isfinite(mVel))
   {
      mLast = target;
      mVel = 0.0f;
   }
   return mLast;
}

// ---------------------------------------------------------------- CV Recorder

namespace
{
   const char* kHex = "0123456789abcdef";
   int HexVal(char c)
   {
      if (c >= '0' && c <= '9') return c - '0';
      if (c >= 'a' && c <= 'f') return c - 'a' + 10;
      return -1;
   }
   unsigned char Quantize(float v) { return (unsigned char)std::lround(std::clamp(v, 0.0f, 1.0f) * 255.0f); }
}

void CVRecorderNode::VisitParams(ParamVisitor& v)
{
   v.Float("constantIn", constantIn);
   v.Float("speed", speed);
   v.Float("low", low);
   v.Float("high", high);
   v.Bool("playing", playing);

   std::string enc;
   enc.reserve(mData.size() * 2);
   for (unsigned char b : mData)
   {
      enc.push_back(kHex[b >> 4]);
      enc.push_back(kHex[b & 15]);
   }
   const std::string before = enc;
   v.Text("data", enc);
   if (enc != before && !mRecording) // a load / undo restore replaced the take
   {
      mData.clear();
      for (size_t i = 0; i + 1 < enc.size() && (int)mData.size() < kMaxSamples; i += 2)
      {
         const int hi = HexVal(enc[i]), lo = HexVal(enc[i + 1]);
         if (hi < 0 || lo < 0) break;
         mData.push_back((unsigned char)(hi * 16 + lo));
      }
      mAnchorSet = false;
   }
}

void CVRecorderNode::StartRecording()
{
   mRecording = true;
   mData.clear();
   mRecStart = Transport::Instance().Beats();
}

void CVRecorderNode::StopRecording()
{
   if (!mRecording)
      return;
   mRecording = false;
   playing = !mData.empty();
   mAnchorSet = false; // playback restarts from the top of the take
   mLastBeats = -1.0;
   mPhase = 0.0;
}

void CVRecorderNode::StartPlayback()
{
   playing = true;
   mAnchorSet = false;
   mLastBeats = -1.0;
   mPhase = 0.0;
}

void CVRecorderNode::StopPlayback()
{
   playing = false;
}

void CVRecorderNode::Clear()
{
   mRecording = false;
   playing = false;
   mData.clear();
}

float CVRecorderNode::Sample(double pos) const
{
   const int n = (int)mData.size();
   if (n == 0)
      return 0.0f;
   if (pos < 0.0)
      pos = 0.0;
   int i0 = (int)pos;
   const float f = (float)(pos - i0);
   i0 %= n;
   const int i1 = (i0 + 1) % n;
   return (mData[i0] + (mData[i1] - mData[i0]) * f) * (1.0f / 255.0f);
}

float CVRecorderNode::Value01()
{
   const float in = std::clamp(input ? input->Value01() : constantIn, 0.0f, 1.0f);
   if (bypassed)
      return in;
   const double beats = Transport::Instance().Beats();

   if (mRecording)
   {
      double rel = beats - mRecStart;
      if (rel < 0.0) // transport rewound: start the take over from here
      {
         mRecStart = beats;
         mData.clear();
         rel = 0.0;
      }
      const int idx = (int)(rel * kSamplesPerBeat);
      if (idx >= kMaxSamples)
      {
         StopRecording(); // take is full; fall through to playback
      }
      else
      {
         // Fill any skipped slots with the previous value so a stalled frame
         // leaves a hold, not a gap; the current slot tracks the latest input.
         const unsigned char q = Quantize(in);
         while ((int)mData.size() <= idx)
            mData.push_back(mData.empty() ? q : mData.back());
         mData[idx] = q;
         mLastOut = in;
         return in;
      }
   }

   if (!mPlaying())
      return mData.empty() ? in : mLastOut;
   if (beats == mLastBeats)
      return mLastOut; // already resolved this tick

   // Integrate the playhead instead of deriving it from (beats - anchor) *
   // speed: that form jumps the loop position every time `speed` is dragged.
   // A rewind or first tick only re-seeds mLastBeats, keeping the phase.
   if (!mAnchorSet || mLastBeats < 0.0 || beats < mLastBeats)
   {
      mAnchorSet = true;
      if (mLastBeats < 0.0)
         mPhase = 0.0; // fresh pass starts from the top of the take
   }
   else
      mPhase += (beats - mLastBeats) * std::max(0.0f, speed) * kSamplesPerBeat;
   mLastBeats = beats;

   const double n = (double)mData.size();
   mPhase = std::fmod(mPhase, n);
   const double pos = mPhase;
   mPlayNorm = (float)(pos / n);
   mLastOut = std::clamp(low + (high - low) * Sample(pos), 0.0f, 1.0f);
   return mLastOut;
}

// ---------------------------------------------------------------- Mod Depth

float ModDepthNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;
   const float v = input ? input->Value01() : constantIn;
   return std::clamp(0.5f + (v - 0.5f) * depth, 0.0f, 1.0f);
}

// ---------------------------------------------------------------- Envelope

// The level at `seconds`, walking stage edges at their exact times (an
// attack that ends between calls hands over to decay at attackMs, not at
// the call that noticed). A time before the stage start reads as the start.
float EnvelopeNode::LevelAt(double seconds)
{
   for (int edges = 0; edges < 4; edges++)
   {
      const double elapsedMs = std::max(0.0, (seconds - mStageStartSeconds) * 1000.0);
      const float sustain = std::clamp(sustainLevel, 0.0f, 1.0f);
      switch (mStage)
      {
         case Stage::Idle:
            return 0.0f;
         case Stage::Attack:
         {
            const double a = std::max(0.001f, attackMs);
            if (elapsedMs < a)
               return mStageStartLevel + (1.0f - mStageStartLevel) * (float)(elapsedMs / a);
            mStage = Stage::Decay;
            mStageStartLevel = 1.0f;
            mStageStartSeconds += a * 0.001;
            break;
         }
         case Stage::Decay:
         {
            const double d = std::max(0.001f, decayMs);
            if (elapsedMs < d)
               return 1.0f + (sustain - 1.0f) * (float)(elapsedMs / d);
            mStage = Stage::Sustain;
            mStageStartSeconds += d * 0.001;
            break;
         }
         case Stage::Sustain:
            return sustain;
         case Stage::Release:
         {
            const double r = std::max(0.001f, releaseMs);
            if (elapsedMs < r)
               return mStageStartLevel * (1.0f - (float)(elapsedMs / r));
            mStage = Stage::Idle;
            return 0.0f;
         }
      }
   }
   return mLevel;
}

// maths 1: the gate edge sits where the input, as a straight line from the
// previous call, crosses the threshold, and the stage edges after it at
// their exact times, so stage lengths match the knobs at any frame rate.
float EnvelopeNode::LevelExact(double seconds, float in01)
{
   const bool above = in01 >= threshold;
   if (above != mGateOpen)
   {
      double edge = seconds;
      if (mPrevSeconds >= 0.0 && seconds > mPrevSeconds && in01 != mPrevIn)
      {
         const double f = std::clamp((double)(threshold - mPrevIn) / (double)(in01 - mPrevIn), 0.0, 1.0);
         edge = mPrevSeconds + f * (seconds - mPrevSeconds);
      }
      const float levelAtEdge = mStageStartSeconds < 0.0 ? 0.0f : LevelAt(edge);
      mGateOpen = above;
      mStage = above ? Stage::Attack : Stage::Release;
      mStageStartLevel = levelAtEdge;
      mStageStartSeconds = edge;
   }
   mPrevIn = in01;
   mPrevSeconds = seconds;
   mLevel = mStageStartSeconds < 0.0 ? 0.0f : LevelAt(seconds);
   return mLevel;
}

float EnvelopeNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;
   const float in01 = input ? input->Value01() : constantIn;
   const double seconds = Transport::Instance().Seconds();

   if (maths >= 1)
   {
      if (seconds != mPrevSeconds)
         LevelExact(seconds, in01);
      return output == kOutAdsr ? std::clamp(mLevel, 0.0f, 1.0f)
                                : std::clamp(0.5f + (in01 - 0.5f) * mLevel, 0.0f, 1.0f);
   }

   const bool above = in01 >= threshold;
   if (above != mGateOpen)
   {
      mGateOpen = above;
      mStage = above ? Stage::Attack : Stage::Release;
      mStageStartLevel = mLevel;
      mStageStartSeconds = seconds;
   }

   const double elapsedMs = mStageStartSeconds < 0.0 ? 0.0 : (seconds - mStageStartSeconds) * 1000.0;

   switch (mStage)
   {
      case Stage::Idle:
         mLevel = 0.0f;
         break;

      case Stage::Attack:
      {
         const float t = (float)(elapsedMs / std::max(0.001f, attackMs));
         if (t >= 1.0f)
         {
            mLevel = 1.0f;
            mStage = Stage::Decay;
            mStageStartLevel = 1.0f;
            mStageStartSeconds = seconds;
         }
         else
         {
            mLevel = mStageStartLevel + (1.0f - mStageStartLevel) * t;
         }
         break;
      }

      case Stage::Decay:
      {
         const float sustain = std::clamp(sustainLevel, 0.0f, 1.0f);
         const float t = (float)(elapsedMs / std::max(0.001f, decayMs));
         if (t >= 1.0f)
         {
            mLevel = sustain;
            mStage = Stage::Sustain;
         }
         else
         {
            mLevel = 1.0f + (sustain - 1.0f) * t;
         }
         break;
      }

      case Stage::Sustain:
         mLevel = std::clamp(sustainLevel, 0.0f, 1.0f);
         break;

      case Stage::Release:
      {
         const float t = (float)(elapsedMs / std::max(0.001f, releaseMs));
         if (t >= 1.0f)
         {
            mLevel = 0.0f;
            mStage = Stage::Idle;
         }
         else
         {
            mLevel = mStageStartLevel * (1.0f - t);
         }
         break;
      }
   }

   if (output == kOutAdsr)
      return std::clamp(mLevel, 0.0f, 1.0f);
   return std::clamp(0.5f + (in01 - 0.5f) * mLevel, 0.0f, 1.0f);
}

// ---------------------------------------------------------------- CV to Pitch

float CVToPitchNode::TargetFor(float v01, int* semitoneOut) const
{
   const int low = std::min(rangeLow, rangeHigh);
   const int high = std::max(rangeLow, rangeHigh);
   const int semitoneCount = std::max(1, high - low + 1);
   const int idx = std::clamp((int)std::lround(v01 * (float)(semitoneCount - 1)), 0, semitoneCount - 1);
   int semitone = low + idx;
   if (scale != MusicTime::kChromatic)
      semitone = MusicTime::SnapToScaleInRange(semitone, root, scale, low, high);
   if (semitoneOut != nullptr)
      *semitoneOut = semitone;
   return (float)(semitone - low) / (float)std::max(1, semitoneCount - 1);
}

float CVToPitchNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;

   const float v01 = std::clamp(input ? input->Value01() : constantIn, 0.0f, 1.0f);

   if (maths >= 1)
   {
      int semitone = 0;
      const float target01 = TargetFor(v01, &semitone);
      mLastSemitone = semitone;
      const double seconds = Transport::Instance().Seconds();
      if (mGlided >= 0.0f && seconds == mLastSeconds)
         return mGlided; // already advanced this tick - don't double-apply the filter
      const double dt = (mGlided < 0.0f || mLastSeconds < 0.0) ? 0.0 : seconds - mLastSeconds;
      mLastSeconds = seconds;
      if (glideMs <= 0.0f || mGlided < 0.0f || dt <= 0.0 || dt > 1.0)
         mGlided = target01;
      else
      {
         // The input runs in a straight line from the last call's value; the
         // glide chases each semitone from the moment the line enters it.
         // Boundaries between input steps sit at (k + 0.5) / (count - 1).
         const double tau = glideMs * 0.001;
         const int count = std::max(1, std::abs(rangeHigh - rangeLow) + 1);
         const double x0 = mPrevIn < 0.0f ? v01 : mPrevIn, x1 = v01;
         double y = mGlided, from = 0.0;
         if (count > 1 && x1 != x0)
         {
            const double n = count - 1;
            const double dir = x1 > x0 ? 1.0 : -1.0;
            // First boundary past x0 in the direction of travel.
            double k = dir > 0 ? std::floor(x0 * n - 0.5) + 1.0 : std::ceil(x0 * n - 0.5) - 1.0;
            for (int guard = 0; guard < 256; guard++, k += dir)
            {
               const double b = (k + 0.5) / n;
               const double f = (b - x0) / (x1 - x0);
               if (!(f < 1.0))
                  break; // past this call's end of the line (or not finite)
               if (f <= from)
                  continue; // x0 sits on this boundary: already in the next step
               const float seg = TargetFor((float)(x0 + (x1 - x0) * (from + f) * 0.5), nullptr);
               y = seg + (y - seg) * std::exp(-(f - from) * dt / tau);
               from = f;
            }
         }
         // The last stretch chases the step the line runs through, which is
         // target01 unless the line ends exactly on a boundary.
         const float last = x1 != x0 ? TargetFor((float)(x0 + (x1 - x0) * (from + 1.0) * 0.5), nullptr) : target01;
         y = last + (y - last) * std::exp(-(1.0 - from) * dt / tau);
         mGlided = (float)y;
      }
      mPrevIn = v01;
      return std::clamp(mGlided, 0.0f, 1.0f);
   }

   const int low = std::min(rangeLow, rangeHigh);
   const int high = std::max(rangeLow, rangeHigh);
   const int semitoneCount = std::max(1, high - low + 1);
   const int idx = std::clamp((int)std::lround(v01 * (float)(semitoneCount - 1)), 0, semitoneCount - 1);
   int semitone = low + idx;

   if (scale != MusicTime::kChromatic)
      semitone = MusicTime::SnapToScaleInRange(semitone, root, scale, low, high);
   mLastSemitone = semitone;

   const int snappedIdx = semitone - low;
   const float target01 = (float)snappedIdx / (float)std::max(1, semitoneCount - 1);

   // Glide smooths the quantized output itself (portamento) - see the class
   // comment. Transport::Seconds() is real playing time, frozen while
   // paused, so glide simply holds rather than jumping while stopped.
   const double seconds = Transport::Instance().Seconds();
   if (mGlided >= 0.0f && seconds == mLastSeconds)
      return mGlided; // already advanced this tick - don't double-apply the filter

   const double dt = (mGlided < 0.0f || mLastSeconds < 0.0) ? 0.0 : std::max(0.0, seconds - mLastSeconds);
   mLastSeconds = seconds;

   if (glideMs <= 0.0f || mGlided < 0.0f)
      mGlided = target01;
   else
   {
      const float coef = std::exp(-(float)dt / (glideMs * 0.001f));
      mGlided = target01 + (mGlided - target01) * coef;
   }
   return std::clamp(mGlided, 0.0f, 1.0f);
}

// ---------------------------------------------------------------- Invert

float InvertNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;
   const float v = input ? input->Value01() : constantIn;
   return low + high - v;
}

// ---------------------------------------------------------------- Mod Curve

float ModCurveNode::Value01()
{
   if (bypassed)
      return input ? input->Value01() : constantIn;
   const float in = input ? input->Value01() : constantIn;
   const float x = std::clamp(in, 0.0f, 1.0f); // clamp for lookup only; the curve is only defined on 0..1
   const float y = curve.Evaluate(x);
   return in + (y - in) * mix;
}

// ---------------------------------------------------------------- Audio to CV
class AudioAudioToCVNode : public AudioNode
{
public:
   void PrepareToPlay(double sampleRate, int /*maxBlockSize*/) override
   {
      mSampleRate = sampleRate > 0.0 ? sampleRate : 44100.0;
   }

   void ProcessBlock(const AudioBuffer* const* inputs, int numInputs, AudioBuffer& output) override
   {
      const int numFrames = output.numFrames;
      const AudioBuffer* inBuf = (numInputs > 0) ? inputs[0] : nullptr;

      const float gain = mGain.load(std::memory_order_relaxed);
      const float attackMs = std::max(0.1f, mAttackMs.load(std::memory_order_relaxed));
      const float releaseMs = std::max(1.0f, mReleaseMs.load(std::memory_order_relaxed));
      const int mode = mMode.load(std::memory_order_relaxed);
      const float minVal = mMinVal.load(std::memory_order_relaxed);
      const float maxVal = mMaxVal.load(std::memory_order_relaxed);

      const float attCoef = std::exp(-1.0f / (float)(mSampleRate * 0.001 * attackMs));
      const float relCoef = std::exp(-1.0f / (float)(mSampleRate * 0.001 * releaseMs));

      float env = mEnv.load(std::memory_order_relaxed);

      if (inBuf != nullptr && inBuf->numChannels > 0 && inBuf->channels != nullptr)
      {
         const int channels = inBuf->numChannels;
         for (int i = 0; i < numFrames; i++)
         {
            float instant = 0.0f;
            if (mode == 0) // Peak
            {
               for (int c = 0; c < channels; c++)
                  if (inBuf->channels[c] != nullptr)
                     instant = std::max(instant, std::fabs(inBuf->channels[c][i]));
            }
            else // RMS
            {
               float sumSq = 0.0f;
               int validCh = 0;
               for (int c = 0; c < channels; c++)
               {
                  if (inBuf->channels[c] != nullptr)
                  {
                     float s = inBuf->channels[c][i];
                     sumSq += s * s;
                     validCh++;
                  }
               }
               instant = validCh > 0 ? std::sqrt(sumSq / (float)validCh) : 0.0f;
            }
            instant *= gain;

            const float coef = (instant > env) ? attCoef : relCoef;
            env = instant + coef * (env - instant);
         }
      }
      else
      {
         for (int i = 0; i < numFrames; i++)
            env *= relCoef;
      }

      mEnv.store(env, std::memory_order_relaxed);

      float mapped = minVal + (maxVal - minVal) * std::clamp(env, 0.0f, 1.0f);
      mLevel.store(std::clamp(mapped, 0.0f, 1.0f), std::memory_order_relaxed);
   }

   void PushParams(const AudioToCVNode& n)
   {
      mGain.store(n.gain, std::memory_order_relaxed);
      mAttackMs.store(n.attackMs, std::memory_order_relaxed);
      mReleaseMs.store(n.releaseMs, std::memory_order_relaxed);
      mMode.store(n.mode, std::memory_order_relaxed);
      mMinVal.store(n.minVal, std::memory_order_relaxed);
      mMaxVal.store(n.maxVal, std::memory_order_relaxed);
   }

   float Level() const { return mLevel.load(std::memory_order_relaxed); }
   float RawEnvelope() const { return mEnv.load(std::memory_order_relaxed); }

private:
   double mSampleRate = 44100.0;
   std::atomic<float> mEnv { 0.0f };
   std::atomic<float> mLevel { 0.0f };
   std::atomic<float> mGain { 1.0f };
   std::atomic<float> mAttackMs { 10.0f };
   std::atomic<float> mReleaseMs { 100.0f };
   std::atomic<int> mMode { 0 };
   std::atomic<float> mMinVal { 0.0f };
   std::atomic<float> mMaxVal { 1.0f };
};

AudioToCVNode::AudioToCVNode() = default;
AudioToCVNode::~AudioToCVNode() = default;

void AudioToCVNode::CookIfNeeded(int frameId)
{
   if (frameId == mLastCookFrame)
      return;
   mLastCookFrame = frameId;
   if (!mAudioNode)
      mAudioNode = std::make_unique<AudioAudioToCVNode>();
   mAudioNode->PushParams(*this);
}

void AudioToCVNode::VisitParams(ParamVisitor& v)
{
   v.Float("gain", gain);
   v.Float("attackMs", attackMs);
   v.Float("releaseMs", releaseMs);
   v.Int("mode", mode);
   v.Float("minVal", minVal);
   v.Float("maxVal", maxVal);
}

AudioNode* AudioToCVNode::AudioNodeForNotePorts()
{
   if (!mAudioNode)
      mAudioNode = std::make_unique<AudioAudioToCVNode>();
   return mAudioNode.get();
}

float AudioToCVNode::Value01()
{
   if (!mAudioNode)
      mAudioNode = std::make_unique<AudioAudioToCVNode>();
   return mAudioNode->Level();
}

float AudioToCVNode::CurrentLevel() const
{
   return mAudioNode ? mAudioNode->Level() : 0.0f;
}

float AudioToCVNode::RawEnvelope() const
{
   return mAudioNode ? mAudioNode->RawEnvelope() : 0.0f;
}
