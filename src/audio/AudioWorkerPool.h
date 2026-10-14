#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <thread>
#include <vector>

#if defined(__APPLE__)
#include <dispatch/dispatch.h>
#elif defined(_WIN32)
// HANDLE without dragging <windows.h> into every audio header.
typedef void* AudioWorkerSemaphoreHandle;
#else
#include <semaphore.h>
#endif

// Helper threads for the audio graph (v0.6 2.24). The pool only owns threads
// and a wake signal: AudioEngine decides what each wake does. A worker sleeps
// on a semaphore, wakes, calls the engine's job function with its index
// (1..N; 0 is the audio thread itself), and sleeps again. The job must cope
// with a worker that wakes late or spuriously: the engine's claim counter
// carries the block number, so a stale worker finds nothing to claim.
//
// Started and stopped on the main thread only. Wake() is the one call the
// audio thread makes, and it never blocks or allocates (a semaphore post per
// worker woken).
class AudioWorkerPool
{
public:
   typedef void (*Job)(void* ctx, int worker);

   AudioWorkerPool() = default;
   ~AudioWorkerPool();
   AudioWorkerPool(const AudioWorkerPool&) = delete;
   AudioWorkerPool& operator=(const AudioWorkerPool&) = delete;

   void Start(int numWorkers, Job job, void* ctx);
   void Stop();
   int NumWorkers() const { return (int)mThreads.size(); }

   // Audio thread: wake up to `count` workers. Returns at once.
   void Wake(int count);

   // The FP control word (FTZ/DAZ, rounding) every worker copies before a
   // job, so a node computes the same bits on any thread. Read on the caller.
   static uint64_t ReadFpControl();
   static void WriteFpControl(uint64_t v);
   // A spin-wait hint (yield/pause), not a syscall.
   static void Relax();

private:
   void Run(int worker);

   std::vector<std::thread> mThreads;
   std::atomic<bool> mStop { false };
   Job mJob = nullptr;
   void* mCtx = nullptr;
#if defined(__APPLE__)
   dispatch_semaphore_t mSem = nullptr;
#elif defined(_WIN32)
   AudioWorkerSemaphoreHandle mSem = nullptr;
#else
   sem_t mSem;
   bool mSemInit = false;
#endif
};
