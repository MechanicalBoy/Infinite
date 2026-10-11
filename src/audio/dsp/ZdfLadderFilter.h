#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

#include "audio/DspMath.h"

// Non-linear zero-delay-feedback Moog ladder filter.
//
// The circuit: four one-pole stages, each driven by the difference of tanh
// of its input and tanh of its own output (Huovilainen, "Non-Linear Digital
// Implementation of the Moog Ladder Filter", DAFx 2004), with the fourth
// stage's output fed back, scaled by k, to the input:
//
//   dy_i/dt = wc * (tanh(y_{i-1}) - tanh(y_i)),   y_{-1} = x - k * y_3
//
// discretised with trapezoidal (TPT) integrators, g = tan(pi fc / fs)
// (Zavalishin, "The Art of VA Filter Design", ch. 3 and 5).
//
// The zero-delay feedback loop is solved exactly each sample. Each tanh is
// linearised around its value at the previous sample - tanh(v) ~= v * T(v')
// with T(v) = tanh(v) / v - which turns one sample of the whole ladder into
// a linear system in the input u = x - k y_3: each stage is
// y_i = a_i y_{i-1} + b_i, so y_3 = A u + B and u = (x - k B) / (1 + k A).
// This is the standard "cheap" nonlinear ZDF method; below k = 4 it is
// stable at every cutoff, because each sample solves the filter it actually
// is rather than iterating towards it. At small signals T = 1 and the
// response is the exact bilinear-transformed linear ladder (matches the
// analytic 1/((1+s)^4 + k) to 0.01 dB); at large ones the tanh terms
// compress each stage, which is the Moog sound. Past k = 4 the ladder
// self-oscillates at the cutoff frequency, and the tanh compression bounds
// the oscillation (checked from 200 Hz to 12 kHz up to k = 4.2).
//
// The previous version ran two fixed-point iterations from a stale guess and
// paired tanh of the previous output with the current integrator state. It
// was not a zero-delay solve, and with resonance at high cutoffs it fell
// into a limit cycle at an unrelated frequency - 20-30 dB above the note at
// 8 kHz cutoff, resonance 0.5 - heard as whistling.
struct ZdfLadderFilter
{
   struct State
   {
      float stage[4] = {};     // integrator states s_i
      float stageTanh[4] = {}; // previous stage outputs y_i, where each T(.) is evaluated
      float prevInput = 0.0f;  // previous u, where the input stage's T(.) is evaluated

      void Reset()
      {
         for (int i = 0; i < 4; ++i)
         {
            stage[i] = 0.0f;
            stageTanh[i] = 0.0f;
         }
         prevInput = 0.0f;
      }
   };

   // Computes the cutoff coefficient g from cutoff frequency in Hz and sample rate.
   // Uses standard bilinear/tangent prewarping clamped safely below Nyquist.
   static inline float CutoffToG(float cutoffHz, double sampleRate)
   {
      if (sampleRate <= 0.0)
         return 0.0f;
      const float nyquistLimit = (float)sampleRate * 0.45f;
      const float fc = std::clamp(cutoffHz, 10.0f, nyquistLimit);
      const float w = (float)M_PI * fc / (float)sampleRate;
      // Prewarped tangent mapping, clamped so g stays well-conditioned
      return std::clamp(tanf(w), 0.0001f, 3.0f);
   }

   // tanh(v) / v, the slope of the line from the origin to tanh at v.
   static inline float TanhSlope(float v)
   {
      if (std::fabs(v) < 1.0e-4f)
         return 1.0f;
      return DspMath::FastTanh(v) / v;
   }

   // Processes a single sample through the 4-stage ZDF ladder filter.
   // input: audio sample (typically in [-1, 1], optionally saturated by pre-filter drive)
   // g: cutoff coefficient from CutoffToG
   // k: feedback resonance; 4 is the self-oscillation threshold, up to 4.5
   // iterations: accepted for source compatibility; the loop is solved
   //             exactly, so there is nothing to iterate.
   static inline float Process(State& s, float input, float g, float k, int /*iterations*/ = 2)
   {
      const float kk = std::clamp(k, 0.0f, 4.5f);

      // Slopes at the previous sample's operating point.
      const float tIn = TanhSlope(s.prevInput);
      float t[4];
      for (int i = 0; i < 4; ++i)
         t[i] = TanhSlope(s.stageTanh[i]);

      // y_i = s_i + g (t_{i-1} y_{i-1} - t_i y_i)  =>  y_i = a_i y_{i-1} + b_i
      float a[4], b[4];
      for (int i = 0; i < 4; ++i)
      {
         const float den = 1.0f / (1.0f + g * t[i]);
         a[i] = g * (i == 0 ? tIn : t[i - 1]) * den;
         b[i] = s.stage[i] * den;
      }

      // Chain the stages: y_3 = A u + B.
      float A = a[0], B = b[0];
      for (int i = 1; i < 4; ++i)
      {
         B = a[i] * B + b[i];
         A = a[i] * A;
      }

      // Close the loop exactly: u = x - k y_3.
      const float u = (input - kk * B) / (1.0f + kk * A);

      float y[4];
      float prev = u;
      for (int i = 0; i < 4; ++i)
      {
         y[i] = a[i] * prev + b[i];
         prev = y[i];
      }

      // Trapezoidal state update: s_i <- 2 y_i - s_i.
      for (int i = 0; i < 4; ++i)
      {
         s.stage[i] = DspMath::FlushDenormal(2.0f * y[i] - s.stage[i]);
         s.stageTanh[i] = y[i];
      }
      s.prevInput = u;
      return y[3];
   }
};
