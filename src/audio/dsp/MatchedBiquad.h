#pragma once

#include <algorithm>
#include <cmath>
#include <complex>

#include "audio/DspMath.h"

// Matched-magnitude biquad design: second-order digital filters whose
// magnitude follows the analog prototype all the way to Nyquist instead of
// "cramping" there the way bilinear-transform (RBJ cookbook) filters do.
// After M. Vicanek, "Matched Second Order Digital Filters" (2016): the poles
// come from impulse invariance on the analog denominator, the numerator is
// solved so |H| equals the analog magnitude exactly at DC, at Nyquist and at
// one match frequency in between (the band's own frequency, capped at 0.9 pi).
//
// Cuts (peak/low shelf with negative gain, high shelf with positive gain) are
// designed as the inverse of the matching boost - swap numerator and
// denominator - so the poles always come from the well-damped side and the
// spectral factorisation never has to clamp.
//
// Main thread only (a handful of exp/cos/sqrt per band per PushParams), the
// audio thread still just runs float Biquad::Process.
namespace MatchedBiquad
{
   enum Kind { kLowShelf, kPeak, kHighShelf, kHighpass, kLowpass, kBandpass, kNotch, kAllpass };

   // Analog prototype in normalised s (s = j w / w0):
   // (n2 s^2 + n1 s + n0) / (d2 s^2 + d1 s + d0). Shelves and peak are the
   // cookbook analog prototypes, A = 10^(g/40).
   struct Proto
   {
      double n2, n1, n0, d2, d1, d0;
   };

   inline Proto MakeProto(Kind kind, double q, double gainDb)
   {
      const double A = pow(10.0, gainDb / 40.0);
      const double r = sqrt(A);
      switch (kind)
      {
         case kLowShelf: return { A, A * r / q, A * A, A, r / q, 1.0 };
         case kHighShelf: return { A * A, A * r / q, A, 1.0, r / q, A };
         case kPeak: return { 1.0, A / q, 1.0, 1.0, 1.0 / (A * q), 1.0 };
         case kHighpass: return { 1.0, 0.0, 0.0, 1.0, 1.0 / q, 1.0 };
         case kLowpass: return { 0.0, 0.0, 1.0, 1.0, 1.0 / q, 1.0 };
         case kBandpass: return { 0.0, 1.0 / q, 0.0, 1.0, 1.0 / q, 1.0 };
         case kNotch: return { 1.0, 0.0, 1.0, 1.0, 1.0 / q, 1.0 };
         case kAllpass: default: return { 1.0, -1.0 / q, 1.0, 1.0, 1.0 / q, 1.0 };
      }
   }

   // |H_analog(j W)|^2, W = w / w0.
   inline double AnalogMag2(const Proto& p, double W)
   {
      const std::complex<double> s(0.0, W);
      const std::complex<double> n = p.n2 * s * s + p.n1 * s + p.n0;
      const std::complex<double> d = p.d2 * s * s + p.d1 * s + p.d0;
      return std::norm(n) / std::max(1e-300, std::norm(d));
   }

   struct Coeffs
   {
      double b0 = 1.0, b1 = 0.0, b2 = 0.0, a1 = 0.0, a2 = 0.0;
   };

   // Impulse-invariant poles of d2 s^2 + d1 s + d0 (s normalised by w0).
   inline void Poles(double d2, double d1, double d0, double w0, Coeffs& c)
   {
      const double wp = w0 * sqrt(d0 / d2);
      const double zeta = d1 / (2.0 * sqrt(d0 * d2));
      const double e = exp(-zeta * wp);
      if (zeta < 1.0)
         c.a1 = -2.0 * e * cos(std::min(wp * sqrt(1.0 - zeta * zeta), M_PI));
      else
         c.a1 = -2.0 * e * cosh(wp * sqrt(zeta * zeta - 1.0));
      c.a2 = exp(-2.0 * zeta * wp);
   }

   // phi terms: |H|^2 = (B0 phi0 + B1 phi1 + B2 phi2) / (A0 phi0 + A1 phi1 + A2 phi2).
   inline void Phi(double w, double& p0, double& p1, double& p2)
   {
      const double s = sin(0.5 * w);
      p1 = s * s;
      p0 = 1.0 - p1;
      p2 = 4.0 * p0 * p1;
   }

   inline double DenMag2(const Coeffs& c, double w)
   {
      double p0, p1, p2;
      Phi(w, p0, p1, p2);
      const double A0 = (1.0 + c.a1 + c.a2) * (1.0 + c.a1 + c.a2);
      const double A1 = (1.0 - c.a1 + c.a2) * (1.0 - c.a1 + c.a2);
      const double A2 = -4.0 * c.a2;
      return A0 * p0 + A1 * p1 + A2 * p2;
   }

   // Full three-point match (DC, Nyquist, wm) for prototypes with no zero at DC.
   inline void MatchThreePoint(const Proto& p, double w0, double wm, Coeffs& c)
   {
      Poles(p.d2, p.d1, p.d0, w0, c);
      const double A0 = (1.0 + c.a1 + c.a2) * (1.0 + c.a1 + c.a2);
      const double A1 = (1.0 - c.a1 + c.a2) * (1.0 - c.a1 + c.a2);
      const double B0 = AnalogMag2(p, 0.0) * A0;
      const double B1 = AnalogMag2(p, M_PI / w0) * A1;
      double p0, p1, p2;
      Phi(wm, p0, p1, p2);
      const double B2 = (AnalogMag2(p, wm / w0) * DenMag2(c, wm) - B0 * p0 - B1 * p1) / p2;
      const double s0 = sqrt(B0), s1 = sqrt(B1), W = 0.5 * (s0 + s1);
      const double disc = std::max(W * W + B2, 0.0);
      c.b0 = 0.5 * (W + sqrt(disc));
      c.b1 = 0.5 * (s0 - s1);
      c.b2 = c.b0 > 0.0 ? -B2 / (4.0 * c.b0) : 0.0;
   }

   inline Coeffs Invert(const Coeffs& c)
   {
      return { 1.0 / c.b0, c.a1 / c.b0, c.a2 / c.b0, c.b1 / c.b0, c.b2 / c.b0 };
   }

   inline Coeffs Design(Kind kind, double freq, double q, double gainDb, double sampleRate)
   {
      Coeffs c;
      if (sampleRate <= 0.0)
         return c;
      q = std::max(q, 1e-3);
      const double w0 = 2.0 * M_PI * std::clamp(freq, 1.0, 0.4999 * sampleRate) / sampleRate;
      const double wm = std::min(w0, 0.9 * M_PI);

      if (kind == kLowShelf || kind == kPeak || kind == kHighShelf)
      {
         // The cut side of each shelf/peak puts its zeros where the boost's
         // poles were; design the boost and swap.
         const bool invert = (kind == kHighShelf) ? gainDb > 0.0 : gainDb < 0.0;
         MatchThreePoint(MakeProto(kind, q, invert ? -gainDb : gainDb), w0, wm, c);
         return invert ? Invert(c) : c;
      }

      Poles(1.0, 1.0 / q, 1.0, w0, c);
      const Proto p = MakeProto(kind, q, gainDb);
      double p0, p1, p2;
      Phi(wm, p0, p1, p2);
      switch (kind)
      {
         case kLowpass:
         {
            // b2 = 0; match DC and wm.
            const double A0 = (1.0 + c.a1 + c.a2) * (1.0 + c.a1 + c.a2);
            const double B0 = A0;
            const double B1 = std::max((DenMag2(c, wm) * AnalogMag2(p, wm / w0) - B0 * p0) / p1, 0.0);
            c.b0 = 0.5 * (sqrt(B0) + sqrt(B1));
            c.b1 = sqrt(B0) - c.b0;
            c.b2 = 0.0;
            return c;
         }
         case kHighpass:
         {
            // Double zero at DC, scaled to match at wm.
            c.b0 = sqrt(DenMag2(c, wm) * AnalogMag2(p, wm / w0)) / (4.0 * p1);
            c.b1 = -2.0 * c.b0;
            c.b2 = c.b0;
            return c;
         }
         case kBandpass:
         {
            // Zero at DC; match wm and Nyquist.
            const double B1 = AnalogMag2(p, M_PI / w0) * DenMag2(c, M_PI);
            const double B2 = (DenMag2(c, wm) * AnalogMag2(p, wm / w0) - B1 * p1) / p2;
            const double W = 0.5 * sqrt(B1);
            const double disc = std::max(W * W + B2, 0.0);
            c.b0 = 0.5 * (W + sqrt(disc));
            c.b2 = c.b0 > 0.0 ? -B2 / (4.0 * c.b0) : 0.0;
            c.b1 = -(c.b0 + c.b2);
            return c;
         }
         case kNotch:
         {
            // Zeros on the unit circle at w0, unity at DC.
            const double k = (1.0 + c.a1 + c.a2) / (2.0 - 2.0 * cos(w0));
            c.b0 = k;
            c.b1 = -2.0 * cos(w0) * k;
            c.b2 = k;
            return c;
         }
         case kAllpass:
         default:
            // Numerator is the reversed denominator: |H| = 1 exactly.
            c.b0 = c.a2;
            c.b1 = c.a1;
            c.b2 = 1.0;
            return c;
      }
   }

   inline void Apply(const Coeffs& c, DspMath::Biquad& bq)
   {
      bq.b0 = (float)c.b0;
      bq.b1 = (float)c.b1;
      bq.b2 = (float)c.b2;
      bq.a1 = (float)c.a1;
      bq.a2 = (float)c.a2;
   }
}
