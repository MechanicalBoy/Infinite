#include "Transport.h"

Transport& Transport::Instance()
{
   static Transport instance;
   return instance;
}

double Transport::Seconds() const
{
   const double pending = mPendingSeekSeconds.load(std::memory_order_relaxed);
   if (pending >= 0.0)
      return pending;

   if (mOfflineActive.load(std::memory_order_relaxed))
   {
      if (mOfflineInAudioBlock.load(std::memory_order_relaxed))
      {
         const double sr = mAudioSampleRate.load(std::memory_order_relaxed);
         if (sr > 0.0)
         {
            return mAudioSecondsOffset.load(std::memory_order_relaxed) +
                   (double)mAudioSampleCounter.load(std::memory_order_relaxed) / sr;
         }
      }
      return mOfflineVideoSeconds.load(std::memory_order_relaxed);
   }

   const double sr = mAudioSampleRate.load(std::memory_order_relaxed);
   if (sr > 0.0)
   {
      return mAudioSecondsOffset.load(std::memory_order_relaxed) +
             (double)mAudioSampleCounter.load(std::memory_order_relaxed) / sr;
   }
   return mSeconds;
}

double Transport::Beats() const
{
   const double pending = mPendingSeekSeconds.load(std::memory_order_relaxed);
   if (pending >= 0.0)
      return pending * (mBpm.load(std::memory_order_relaxed) / 60.0);

   const double sr = mAudioSampleRate.load(std::memory_order_relaxed);
   if (sr <= 0.0 && !mOfflineActive.load(std::memory_order_relaxed))
      return mBeats;
   const double secOffset = mAudioSecondsOffset.load(std::memory_order_relaxed);
   return mAudioBeatsOffset.load(std::memory_order_relaxed) +
          (Seconds() - secOffset) * (mBpm.load(std::memory_order_relaxed) / 60.0);
}

void Transport::Tick(float deltaSeconds)
{
   // clamp so a stalled frame (window drag, file dialog) doesn't jump the clock
   if (deltaSeconds > 0.25f)
      deltaSeconds = 0.25f;

   if (mOfflineActive.load(std::memory_order_relaxed))
      return; // offline mode: video frame time is driven explicitly by SetOfflineVideoTime

   if (mAudioSampleRate.load(std::memory_order_relaxed) > 0.0)
      return; // audio-driven: Beats()/Seconds() compute live, nothing to accumulate here

   if (!mPlaying.load(std::memory_order_relaxed))
      return;

   mSeconds += deltaSeconds;
   mBeats += deltaSeconds * (mBpm.load(std::memory_order_relaxed) / 60.0);
}

void Transport::NotifyAudioEngineStarted(double sampleRate)
{
   mAudioSecondsOffset.store(mSeconds, std::memory_order_relaxed);
   mAudioBeatsOffset.store(mBeats, std::memory_order_relaxed);
   mAudioSampleCounter.store(0, std::memory_order_relaxed);
   mAudioSampleRate.store(sampleRate, std::memory_order_relaxed); // publish last
}

void Transport::NotifyAudioEngineStopped()
{
   mSeconds = Seconds(); // read the still-live audio-driven value...
   mBeats = Beats();
   mAudioSampleRate.store(0.0, std::memory_order_relaxed); // ...then switch back to fallback
   mPendingSeekSeconds.store(-1.0, std::memory_order_relaxed);
}

void Transport::AdvanceAudioClock(int numFrames)
{
   const double pending = mPendingSeekSeconds.exchange(-1.0, std::memory_order_relaxed);
   if (pending >= 0.0)
   {
      mAudioSecondsOffset.store(pending, std::memory_order_relaxed);
      mAudioBeatsOffset.store(pending * (mBpm.load(std::memory_order_relaxed) / 60.0), std::memory_order_relaxed);
      mAudioSampleCounter.store(0, std::memory_order_relaxed);
   }
   if (mPlaying.load(std::memory_order_relaxed))
      mAudioSampleCounter.fetch_add((uint64_t)numFrames, std::memory_order_relaxed);
}

void Transport::Rewind()
{
   Seek(0.0);
}

void Transport::Seek(double seconds)
{
   if (seconds < 0.0)
      seconds = 0.0;
   mResetEpoch.fetch_add(1, std::memory_order_relaxed);
   mSeconds = seconds;
   mBeats = seconds * (mBpm.load(std::memory_order_relaxed) / 60.0);
   mOfflineVideoSeconds.store(seconds, std::memory_order_relaxed);
   if (mOfflineActive.load(std::memory_order_relaxed))
   {
      mPendingSeekSeconds.store(-1.0, std::memory_order_relaxed);
      mAudioSampleCounter.store(0, std::memory_order_relaxed);
      mAudioSecondsOffset.store(seconds, std::memory_order_relaxed);
      mAudioBeatsOffset.store(mBeats, std::memory_order_relaxed);
   }
   else if (mAudioSampleRate.load(std::memory_order_relaxed) > 0.0)
   {
      mPendingSeekSeconds.store(seconds, std::memory_order_relaxed);
   }
   else
   {
      mPendingSeekSeconds.store(-1.0, std::memory_order_relaxed);
      mAudioSampleCounter.store(0, std::memory_order_relaxed);
      mAudioSecondsOffset.store(seconds, std::memory_order_relaxed);
      mAudioBeatsOffset.store(mBeats, std::memory_order_relaxed);
   }
}

void Transport::SetOfflineMode(bool active, double sampleRate)
{
   if (active)
   {
      mPendingSeekSeconds.store(-1.0, std::memory_order_relaxed);
      mAudioSecondsOffset.store(mSeconds, std::memory_order_relaxed);
      mAudioBeatsOffset.store(mBeats, std::memory_order_relaxed);
      mAudioSampleCounter.store(0, std::memory_order_relaxed);
      mAudioSampleRate.store(sampleRate, std::memory_order_relaxed);
      mOfflineVideoSeconds.store(mSeconds, std::memory_order_relaxed);
      mOfflineInAudioBlock.store(false, std::memory_order_relaxed);
      mOfflineActive.store(true, std::memory_order_relaxed);
   }
   else
   {
      mPendingSeekSeconds.store(-1.0, std::memory_order_relaxed);
      mOfflineActive.store(false, std::memory_order_relaxed);
      mOfflineInAudioBlock.store(false, std::memory_order_relaxed);
   }
}

void Transport::SetOfflineVideoTime(double seconds)
{
   mOfflineVideoSeconds.store(seconds, std::memory_order_relaxed);
}

void Transport::BeginOfflineAudioBlock(int numFrames)
{
   const double pending = mPendingSeekSeconds.exchange(-1.0, std::memory_order_relaxed);
   if (pending >= 0.0)
   {
      mAudioSecondsOffset.store(pending, std::memory_order_relaxed);
      mAudioBeatsOffset.store(pending * (mBpm.load(std::memory_order_relaxed) / 60.0), std::memory_order_relaxed);
      mAudioSampleCounter.store(0, std::memory_order_relaxed);
   }
   if (mPlaying.load(std::memory_order_relaxed))
      mAudioSampleCounter.fetch_add((uint64_t)numFrames, std::memory_order_relaxed);
   mOfflineInAudioBlock.store(true, std::memory_order_relaxed);
}

void Transport::EndOfflineAudioBlock()
{
   mOfflineInAudioBlock.store(false, std::memory_order_relaxed);
}
