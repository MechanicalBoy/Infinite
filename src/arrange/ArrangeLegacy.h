#pragma once

// TRANSITIONAL (overhaul WP1 -> deleted in WP5).
//
// The arrangement panel's ~190 UI call sites still address clips by
// (streamIndex, clipIndex) in seconds, and still point at nodes by node index.
// Converting all of them is WP5's job, and doing it in the same commit as the
// model would make both unreviewable. So the UI keeps working on this struct -
// bit-for-bit the shape Patch::ClipRecord used to have - and Arrange::Model is
// the real source of truth for save/load, undo and the fixtures.
//
// The sync is a one-way funnel at each boundary, never a background mirror:
//
//   UI edit ─► gArrangeStreams (seconds, node indices)
//   BuildPatchData ─► FromLegacyStreams ─► gArrange ─► Patch::Data
//   Patch::Data ─► gArrange ─► ToLegacyStreams ─► gArrangeStreams
//
// so the two can never drift for longer than one save or one load. Fields the
// UI does not understand (clip id, group, enabled, srcUid) ride through the
// legacy struct untouched so a round trip does not destroy them.
//
// Round-tripping through seconds quantizes clip edges to Arrange::kPPQ
// (1/960 beat, 0.52 ms at 120 bpm). That is intentional - ticks are the
// storage format from WP1 on, and the grid is what abutting clips must agree
// on - but it does mean a dragged edge settles onto the tick grid the first
// time the patch is serialized.

#include <cstdint>
#include <string>
#include <vector>

namespace Arrange { struct Model; }
namespace Patch { struct StreamRecord; struct MarkerRecord; struct ArrangeSettingsRecord; }

namespace LegacyArrange
{
   struct ClipRecord
   {
      double startSeconds  = 0.0;
      double lengthSeconds = 1.0;
      int    srcIndex      = -1;   // live node index, remapped by ApplyPatchData
      int    srcOutput     = 0;
      float  fadeInSec     = 0.0f;
      float  fadeOutSec    = 0.0f;
      float  gainDb        = 0.0f;
      std::string name;
      float  colorR = 0.0f, colorG = 0.0f, colorB = 0.0f;

      // Carried through untouched by the UI - the model owns their meaning.
      uint64_t id      = 0;
      uint64_t srcUid  = 0;
      bool     enabled = true;
      uint64_t groupId = 0;
   };

   struct StreamRecord
   {
      uint64_t id     = 0;
      int   type      = 0;      // Patch::kStreamVideo / kStreamAudio
      int   blendMode = 0;
      float opacity   = 1.0f;
      float gainDb    = 0.0f;
      float pan       = 0.0f;
      std::string name;
      std::vector<ClipRecord> clips;
   };

   // Both directions need a bpm (the seconds <-> ticks conversion) and a
   // node-index <-> node-uid mapping, which only main.cpp can supply.
   using IndexToUid = uint64_t (*)(int index, void* ctx);
   using UidToIndex = int (*)(uint64_t uid, void* ctx);

   // Folds the UI's streams into `model`, preserving the model's markers,
   // settings and nextId. Clips without an id get one.
   void FromLegacyStreams(const std::vector<StreamRecord>& streams, double bpm,
                          IndexToUid toUid, void* ctx, Arrange::Model& model);

   // Rebuilds the UI's streams from the model. A clip whose srcUid no longer
   // resolves keeps srcIndex = -1 ("offline"), it is never dropped.
   void ToLegacyStreams(const Arrange::Model& model, double bpm,
                        UidToIndex toIndex, void* ctx, std::vector<StreamRecord>& out);
}
