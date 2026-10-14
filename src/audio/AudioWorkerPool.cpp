#include "AudioWorkerPool.h"

#include "../platform/Platform.h"

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#if defined(_M_X64) || defined(_M_IX86)
#include <intrin.h>
#include <xmmintrin.h>
#elif defined(_M_ARM64)
#include <intrin.h>
#ifndef ARM64_FPCR
#define ARM64_FPCR ARM64_SYSREG(3, 3, 4, 4, 0)
#endif
#endif
#elif defined(__x86_64__) || defined(__i386__)
#include <xmmintrin.h>
#endif

AudioWorkerPool::~AudioWorkerPool()
{
   Stop();
}

void AudioWorkerPool::Start(int numWorkers, Job job, void* ctx)
{
   Stop();
   if (numWorkers <= 0)
      return;
   mJob = job;
   mCtx = ctx;
   mStop.store(false, std::memory_order_relaxed);
#if defined(__APPLE__)
   mSem = dispatch_semaphore_create(0);
#elif defined(_WIN32)
   mSem = (AudioWorkerSemaphoreHandle)CreateSemaphoreW(nullptr, 0, 0x7fffffff, nullptr);
#else
   mSemInit = sem_init(&mSem, 0, 0) == 0;
   if (!mSemInit)
      return;
#endif
   mThreads.reserve((size_t)numWorkers);
   for (int i = 0; i < numWorkers; i++)
      mThreads.emplace_back([this, i] { Run(i + 1); });
}

void AudioWorkerPool::Stop()
{
   if (mThreads.empty())
      return;
   mStop.store(true, std::memory_order_release);
   Wake((int)mThreads.size());
   for (std::thread& t : mThreads)
      t.join();
   mThreads.clear();
#if defined(__APPLE__)
   dispatch_release(mSem); // a .cpp file: dispatch objects are not ARC-managed here
   mSem = nullptr;
#elif defined(_WIN32)
   CloseHandle((HANDLE)mSem);
   mSem = nullptr;
#else
   if (mSemInit)
      sem_destroy(&mSem);
   mSemInit = false;
#endif
}

void AudioWorkerPool::Wake(int count)
{
   if (count > (int)mThreads.size())
      count = (int)mThreads.size();
   if (count <= 0)
      return;
#if defined(__APPLE__)
   for (int i = 0; i < count; i++)
      dispatch_semaphore_signal(mSem);
#elif defined(_WIN32)
   ReleaseSemaphore((HANDLE)mSem, count, nullptr);
#else
   for (int i = 0; i < count; i++)
      sem_post(&mSem);
#endif
}

void AudioWorkerPool::Run(int worker)
{
   // Joined lazily and re-joined whenever the device changes: the realtime
   // group belongs to the open output device (macOS workgroup), or is a
   // per-thread registration (Windows MMCSS, Linux SCHED_FIFO).
   uint32_t joinedEpoch = 0;
   void* token = nullptr;
   for (;;)
   {
#if defined(__APPLE__)
      dispatch_semaphore_wait(mSem, DISPATCH_TIME_FOREVER);
#elif defined(_WIN32)
      WaitForSingleObject((HANDLE)mSem, INFINITE);
#else
      while (sem_wait(&mSem) != 0)
      {
      }
#endif
      if (mStop.load(std::memory_order_acquire))
         break;
      const uint32_t epoch = Platform::AudioWorkerEpoch();
      if (epoch != joinedEpoch)
      {
         Platform::AudioWorkerLeave(token);
         token = Platform::AudioWorkerJoin();
         joinedEpoch = epoch;
      }
      mJob(mCtx, worker);
   }
   Platform::AudioWorkerLeave(token);
}

uint64_t AudioWorkerPool::ReadFpControl()
{
#if defined(__aarch64__)
   uint64_t fpcr;
   __asm__ __volatile__("mrs %0, fpcr" : "=r"(fpcr));
   return fpcr;
#elif defined(_M_ARM64)
   return (uint64_t)_ReadStatusReg(ARM64_FPCR);
#elif defined(__x86_64__) || defined(__i386__) || defined(_M_X64) || defined(_M_IX86)
   return (uint64_t)_mm_getcsr();
#else
   return 0;
#endif
}

void AudioWorkerPool::WriteFpControl(uint64_t v)
{
#if defined(__aarch64__)
   __asm__ __volatile__("msr fpcr, %0" : : "r"(v));
#elif defined(_M_ARM64)
   _WriteStatusReg(ARM64_FPCR, (__int64)v);
#elif defined(__x86_64__) || defined(__i386__) || defined(_M_X64) || defined(_M_IX86)
   _mm_setcsr((unsigned int)v);
#else
   (void)v;
#endif
}

void AudioWorkerPool::Relax()
{
#if defined(__aarch64__)
   __asm__ __volatile__("yield");
#elif defined(_M_ARM64)
   __yield();
#elif defined(__x86_64__) || defined(__i386__) || defined(_M_X64) || defined(_M_IX86)
   _mm_pause();
#endif
}
