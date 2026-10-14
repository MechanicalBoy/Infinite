#pragma once

#include "Platform.h"
#include <atomic>
#include <mutex>
#include <string>
#include <vector>

#import <Cocoa/Cocoa.h>
#import <AudioToolbox/AudioToolbox.h>
#import <AVFoundation/AVFoundation.h>

@interface InfinitePluginEditorDelegate : NSObject <NSWindowDelegate>
@property (nonatomic, assign) void* handle;
@end

namespace Platform
{
   struct PluginVST3State;

   struct PluginHandle
   {
      PluginDesc desc;

      // --- instantiation, main thread except where noted -------------------
      AUAudioUnit* unit = nil;
      AUAudioUnit* arrivedUnit = nil; // written by the completion handler's queue
      NSError* arrivedError = nil;    // ditto
      std::mutex arrivalMutex;        // guards the two above; main thread only takes it in PluginPoll
      std::atomic<bool> arrived { false };
      PluginLoadState state = PluginLoadState::Pending;
      std::string loadError;

      // --- render path -----------------------------------------------------
      AURenderBlock renderBlockStrong = nil;
      void* renderBlockRaw = nullptr;
      AUScheduleMIDIEventBlock scheduleMIDIEventBlockStrong = nil;
      void* scheduleMIDIEventBlockRaw = nullptr;

      double sampleRate = 0.0;
      int maxBlockFrames = 0;
      bool resourcesAllocated = false;
      int pluginInChannels = 0;
      int pluginOutChannels = 0;

      // Sidechain: the AU's second input bus. Enabled only while the host has
      // something patched into it (PluginSetSidechainEnabled, applied at the
      // next configure); the pull block answers bus 1 from the sidechain
      // pointers PluginRender was handed.
      bool sidechainWanted = false;
      bool sidechainActive = false;
      int sidechainChannels = 0; // 0 when the AU has no second input bus

      // Plugin-reported processing latency in samples at `sampleRate`,
      // refreshed each time render resources are (re)allocated - AU's
      // PluginConfigure reads it from `au.latency` right after
      // allocateRenderResourcesAndReturnError succeeds; VST3's
      // PluginVST3Configure reads it from IAudioProcessor::getLatencySamples()
      // right after setupProcessing/setActive succeed. Main thread only
      // (same discipline as sampleRate/maxBlockFrames above); read by
      // Platform::PluginLatencySamples(), which AudioPluginNode::
      // LatencySamples() forwards to the topology builder's PDC pass.
      int latencySamples = 0;

      AudioBufferList* outAbl = nullptr;   // allocated once at prepare, sized kPluginMaxChannels
      std::vector<float> inScratch;        // kPluginMaxChannels * maxBlockFrames
      std::vector<float> outScratch;       // ditto, used only when channel counts differ
      std::vector<float> sidechainScratch; // ditto, for a sidechain pull that hands us empty buffers
      double renderSampleTime = 0.0;
      std::atomic<bool> inRender { false };
      // Consecutive render calls the AU answered with an error. An AU hosted
      // out of process answers every call that way once its host process has
      // died; PluginPoll turns a run of them into Failed.
      std::atomic<int> renderFailures { 0 };

      // Host clock for the block being rendered, copied in by PluginRender
      // just before the render block runs; the AU reads it back through the
      // musicalContextBlock/transportStateBlock installed in PluginConfigure,
      // normally from inside that same render call. A plugin that polls the
      // blocks from another thread (some draw tempo in their UI) reads plain
      // aligned doubles, which tear at worst into a one-block-stale value.
      PluginTransport transport;
      bool transportWasPlaying = false;
      bool transportStateChanged = false;

      // --- learn -----------------------------------------------------------
      AUParameterObserverToken learnToken = nullptr;
      std::atomic<bool> learning { false };
      std::atomic<unsigned long long> learnedAddress { 0 };
      std::atomic<bool> learnedValid { false };

      // --- editor window ---------------------------------------------------
      NSWindow* editorWindow = nil;
      NSViewController* editorController = nil;
      InfinitePluginEditorDelegate* editorDelegate = nil;
      bool editorRequestInFlight = false;
      std::atomic<bool> editorOpen { false };
      id editorSizeObserver = nil;
      bool editorUserResized = false;
      bool programmaticResize = false;

      // --- VST3 backend state ---
      PluginVST3State* vst3 = nullptr;
   };

   extern std::atomic<int> gOpenPluginEditorCount;
   void SetPluginEditorOpen(PluginHandle* h, bool open);
}
