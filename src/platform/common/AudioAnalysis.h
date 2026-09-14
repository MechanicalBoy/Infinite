// Shared audio-analysis math for the AudioStart/AudioRead family (the "Audio
// Analyze" node's live-input spectrum/level/onset detector), extracted out of
// AudioDeviceWin.cpp so Windows and Linux run byte-for-byte the same formulas
// instead of two hand-transcribed copies quietly drifting apart - which is
// exactly what happened before this file existed (see the divergence
// post-mortem in the comment this replaces, kept below for context).
//
// Every formula here is deliberately transcribed from Platform.mm's
// ProcessInto() rather than tuned independently: both paths run the same
// 1024-point FFT with the same norm = 2/kFftSize, so identical formulas over
// identical bin magnitudes are identical outputs by construction. Four
// separate divergences used to live in the Windows-only copy, none of which
// crashed or logged, and all of which silently made a Windows user's
// audio-reactive patch respond differently to the same sound:
//
//   1. low/mid/high came from fixed band INDICES, resolving to
//      ~20-106 / ~106-373 / ~1982-4571 Hz. The "mid" band was bass, missing
//      the whole vocal range, and "high" had no cymbals or air. The low
//      weights also summed to 1.5, not 1.0, scaling it up by half again.
//   2. bands[] used a linear clamp(v * 4) where macOS uses the compressive
//      shape() below. They cross at v = 0.75 and diverge badly everywhere
//      real signals live.
//   3. the band ladder stopped at min(16000, nyquist) where macOS runs to
//      nyquist, so band boundaries landed at different frequencies on the
//      two platforms at 48 kHz.
//   4. low/mid/high/rms/peak were left raw - only bands[] was smoothed on
//      read, so they jittered where macOS glides.
//
// Windows and Linux both call RunAnalysisBlock() with their own capture
// engine's ring/FFT/state; this header owns none of that state itself.
#pragma once

#include "../Platform.h"
#include "dsp/PortableFft.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace AudioAnalysisCommon
{
   constexpr int kFftLog2 = 10;
   constexpr int kFftSize = 1 << kFftLog2;
   constexpr int kBins = kFftSize / 2;

   // Runs one full analysis pass over a filled kFftSize ring of mono samples
   // (already gain-applied) and writes the result into `out`. `prevMagnitude`
   // (kBins floats) and `prevFlux` are the caller-owned state carried between
   // calls for the spectral-flux onset detector.
   inline void RunAnalysisBlock(const float ring[kFftSize], double sampleRate,
                                 PortableFft::RealFft& fft, const float window[kFftSize],
                                 float prevMagnitude[kBins], float& prevFlux,
                                 Platform::AudioLevels& out)
   {
      float rms = 0.0f, peak = 0.0f;
      float spectrum[kBins] = {};

      float windowed[kFftSize];
      for (int i = 0; i < kFftSize; i++)
         windowed[i] = ring[i] * window[i];

      float real[kBins], imag[kBins];
      fft.Forward(windowed, kFftLog2, real, imag);
      const float norm = 2.0f / (float)kFftSize;
      for (int k = 0; k < kBins; k++)
         spectrum[k] = std::sqrt(real[k] * real[k] + imag[k] * imag[k]) * norm;

      for (int i = 0; i < kFftSize; i++)
      {
         const float v = ring[i];
         rms += v * v;
         peak = std::max(peak, std::fabs(v));
      }
      rms = std::sqrt(rms / (float)kFftSize);

      // Spectral flux onset, same shape as the file-source analyser.
      float flux = 0.0f;
      for (int k = 0; k < kBins; k++)
         flux += std::max(0.0f, spectrum[k] - prevMagnitude[k]);
      const bool onset = flux > prevFlux * 1.6f && flux > 0.02f;
      prevFlux = prevFlux * 0.7f + flux * 0.3f;
      std::memcpy(prevMagnitude, spectrum, sizeof(float) * kBins);

      const double nyquist = sampleRate * 0.5;

      // Mean bin magnitude across a frequency span. Matches Platform.mm's
      // rangeEnergy lambda exactly, inclusive `hi` and all.
      auto rangeEnergy = [&](double fromHz, double toHz) {
         const int lo = std::max(1, (int)(fromHz / nyquist * kBins));
         const int hi = std::min(kBins - 1, (int)(toHz / nyquist * kBins));
         float sum = 0.0f; int count = 0;
         for (int i = lo; i <= hi; i++) { sum += spectrum[i]; count++; }
         return count > 0 ? sum / (float)count : 0.0f;
      };

      // Magnitudes are tiny; a compressive curve maps them into a usable
      // 0..1. Same curve as Platform.mm.
      auto shape = [](float v) { return std::min(1.0f, std::sqrt(v * 12.0f)); };

      Platform::AudioLevels next;
      next.rms = std::min(1.0f, rms * 3.0f);
      next.peak = std::min(1.0f, peak);
      for (int b = 0; b < Platform::kAudioBands; b++)
      {
         const double loHz = 20.0 * std::pow(nyquist / 20.0, (double)b / Platform::kAudioBands);
         const double hiHz = 20.0 * std::pow(nyquist / 20.0, (double)(b + 1) / Platform::kAudioBands);
         next.bands[b] = shape(rangeEnergy(loHz, hiHz));
      }
      next.low = shape(rangeEnergy(20.0, 250.0));
      next.mid = shape(rangeEnergy(250.0, 2000.0));
      next.high = shape(rangeEnergy(2000.0, 16000.0));
      next.onset = onset;
      out = next;
   }

   // Mixes one block of interleaved frames down to mono*gain, appends to the
   // caller-owned `ring`/`ringFill`, and runs RunAnalysisBlock (writing into
   // `outLevels`) each time the ring fills. Identical ring-accumulation loop
   // on both platforms - only the capture plumbing feeding it differs.
   // Sets outChanged=true (and outLevels to the last block computed) each time
   // the ring fills during this call; callers that publish outLevels under a
   // mutex should do so only when outChanged is true, so a partial block
   // doesn't take the lock for nothing every single audio callback.
   inline void PushFrames(const float* interleaved, int frames, int channels, float gain,
                           double sampleRate, float ring[kFftSize], int& ringFill,
                           PortableFft::RealFft& fft, const float window[kFftSize],
                           float prevMagnitude[kBins], float& prevFlux,
                           Platform::AudioLevels& outLevels, bool& outChanged)
   {
      outChanged = false;
      const int chs = std::max(1, channels);
      for (int i = 0; i < frames; i++)
      {
         float mono = 0.0f;
         for (int c = 0; c < chs; c++)
            mono += interleaved[(size_t)i * chs + c];
         mono *= gain / (float)chs;

         ring[ringFill] = mono;
         ringFill++;

         if (ringFill >= kFftSize)
         {
            ringFill = 0;
            RunAnalysisBlock(ring, sampleRate, fft, window, prevMagnitude, prevFlux, outLevels);
            outChanged = true;
         }
      }
   }
}
