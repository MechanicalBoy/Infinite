#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>

// One bucket of one arrangement clip's live waveform, measured by the audio
// thread as the clip actually played (WP8).
//
// `bucket` is an index from the clip's own start, not from the timeline's, so
// playing the same stretch twice overwrites rather than appends. The main
// thread owns invalidation (see ArrangeClipWave in main.cpp); the audio thread
// only ever labels and publishes.
struct ClipPeak
{
   uint64_t clipId  = 0;
   // The clip shape this bucket was measured under (see ArrangeClipShape in
   // main.cpp). A bucket can still be in flight when an edit resizes the clip
   // it belongs to; the main thread drops one whose shape no longer matches
   // rather than letting it light a pixel of the new, differently-sized
   // waveform with material from the old one.
   uint64_t shape   = 0;
   int      bucket  = -1;
   float    minValue = 0.0f;
   float    maxValue = 0.0f;
};

// 1/16 beat, i.e. Arrange::kPPQ / 16 ticks - the bucket size WP8 specifies.
// Spelled in beats because the audio thread works in beats and this header
// must not depend on the arrangement model.
constexpr double kClipPeakBucketsPerBeat = 16.0;

// Lock-free single-producer (audio thread) / single-consumer (main thread)
// ring of finished waveform buckets. Same index discipline as MeterRing: the
// producer only ever writes mTail, the consumer only ever writes mHead, and
// neither allocates.
//
// A full ring DROPS rather than blocks or overwrites - the waveform is a
// display, so a main thread that stalled long enough to lose buckets should
// lose the ones it missed, not the ones it is about to draw. At one entry per
// 1/16 beat per sounding clip, 2048 entries is minutes of backlog; anything
// that fills it is a stall the user can already see.
class ClipPeakRing
{
public:
   static constexpr int kCapacity = 2048;

   // Audio thread only.
   void Write(const ClipPeak& peak)
   {
      const size_t tail = mTail.load(std::memory_order_relaxed);
      const size_t next = (tail + 1) % kCapacity;
      if (next == mHead.load(std::memory_order_acquire))
      {
         mDropped.fetch_add(1, std::memory_order_relaxed);
         return;
      }
      mEntries[tail] = peak;
      mTail.store(next, std::memory_order_release);
   }

   // Main thread only. Returns how many entries were actually read.
   int Read(ClipPeak* out, int maxCount)
   {
      size_t head = mHead.load(std::memory_order_relaxed);
      const size_t tail = mTail.load(std::memory_order_acquire);
      int n = 0;
      while (head != tail && n < maxCount)
      {
         out[n++] = mEntries[head];
         head = (head + 1) % kCapacity;
      }
      mHead.store(head, std::memory_order_release);
      return n;
   }

   // Diagnostic only (the WP8 fixture asserts it stays 0 over a short take).
   uint64_t DroppedCount() const { return mDropped.load(std::memory_order_relaxed); }

private:
   ClipPeak mEntries[kCapacity] {};
   std::atomic<size_t>   mHead { 0 };    // consumer reads from here
   std::atomic<size_t>   mTail { 0 };    // producer writes here
   std::atomic<uint64_t> mDropped { 0 };
};
