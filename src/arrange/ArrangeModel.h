#pragma once

// Arrangement timeline data model (docs/plans/arrangement/overhaul-prompt.md,
// WP1). Pure data plus edit operations: no ImGui, no OpenGL, no audio, no
// dependency on main.cpp. Everything here is headless-testable, which is the
// whole point - the arrangement's invariants used to live inside 74k lines of
// UI code where nothing could check them.
//
// Two invariants hold everywhere outside the body of an edit op:
//   1. A lane's clips are sorted by `start` and never overlap.
//   2. Every clip id is unique within the model, and so is every lane and
//      marker id. Ids come from Model::nextId, which is persisted, so a
//      deleted clip's id is never handed out again even across a reload.
// `Validate()` checks both (plus more); debug builds call it after every op.
//
// Time is ticks, never seconds. kPPQ = 960 divides by 2, 3, 4, 5, 6, 8 and 16,
// so triplets and quintuplets land exactly on integers and abutting clip edges
// compare equal. A tempo change therefore keeps every clip on its bar/beat and
// only changes what those ticks mean in seconds.

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace Arrange
{
   using Tick = int64_t;
   constexpr Tick kPPQ = 960;            // ticks per quarter note
   constexpr Tick kTicksPerBar = kPPQ * 4;
   // Upper bound for any tick position or clip end. 100,000 bars - about 55
   // hours at 120 bpm, and still ~24 bits of headroom inside int64 so tick
   // arithmetic (sums, differences, llround of a beat multiply) cannot wrap.
   // Every unbounded edge - a trim with no neighbour to the right, a drag
   // past the end of the timeline - clamps here rather than at int64 max, so
   // ArrangementEnd stays a number the ruler can draw.
   constexpr Tick kMaxTick = kTicksPerBar * 100000; // 4/4 only - no meter map yet

   inline double TicksToBeats(Tick t) { return (double)t / (double)kPPQ; }
   inline Tick   BeatsToTicks(double beats) { return (Tick)llround(beats * (double)kPPQ); }
   inline double TicksToSeconds(Tick t, double bpm)
   {
      if (!(bpm > 0.0)) bpm = 120.0;
      return TicksToBeats(t) * 60.0 / bpm;
   }
   inline Tick SecondsToTicks(double sec, double bpm)
   {
      if (!(bpm > 0.0)) bpm = 120.0;
      return BeatsToTicks(sec * bpm / 60.0);
   }

   enum LaneType { kLaneVideo = 0, kLaneAudio = 1 };
   enum Edge { kEdgeStart = 0, kEdgeEnd = 1 };
   // SetEnabled's third argument.
   enum EnableMode { kDisable = 0, kEnable = 1, kToggle = 2 };

   struct Clip
   {
      uint64_t id       = 0;   // unique in the model, never reused
      Tick     start    = 0;   // >= 0
      Tick     length   = 0;   // > 0
      uint64_t srcUid   = 0;   // GraphNode::uid, 0 = unassigned ("offline")
      int      srcOutput = 0;  // which output of srcUid, as CableRecord::srcOutput
      Tick     fadeIn   = 0;   // 0..length
      Tick     fadeOut  = 0;   // 0..length
      float    gainDb   = 0.0f;
      bool     enabled  = true; // the `0` key (WP5)
      uint64_t groupId  = 0;   // 0 = not grouped; a live group has >= 2 members
      std::string name;        // empty = auto (the source node's own title)
      float    colorR = 0.0f, colorG = 0.0f, colorB = 0.0f; // 0,0,0 = no tint

      Tick End() const { return start + length; }
   };

   struct Lane
   {
      uint64_t id        = 0;
      int      type      = kLaneVideo;
      int      blendMode = 0;     // video only, index into BlendModes::Names()
      float    opacity   = 1.0f;  // video only, 0..1
      float    gainDb    = 0.0f;  // audio only
      float    pan       = 0.0f;  // audio only, -1..1
      std::string name;           // empty = auto ("V1", "A2", ...)
      std::vector<Clip> clips;    // always sorted by start, never overlapping
   };

   struct Marker
   {
      uint64_t id  = 0;
      Tick     pos = 0;
      std::string name;
      uint32_t color = 0xFFFFFFFFu; // RGBA8
   };

   struct LoopRange
   {
      bool enabled = false;
      Tick start   = 0;
      Tick end     = 0;
   };

   // Per-patch view and render state. Audio mode is deliberately NOT here: the
   // app always starts in Canvas mode (WP3 owner decision), so it must not be
   // saved.
   struct Settings
   {
      int   timeDisplay  = 0;     // 0 = Bars, 1 = Time
      int   snapDivision = 4;     // grid denominator: 1 = bar, 4 = 1/4, ...
      bool  snapTriplet  = false;
      float zoom         = 1.0f;  // pixels per beat multiplier
      float scroll       = 0.0f;  // leftmost visible beat
      LoopRange loop;
      int   dockSide     = 0;     // 0 = bottom, 1 = top (WP5)
      // Render defaults (WP7).
      int   renderWidth  = 1920;
      int   renderHeight = 1080;
      int   renderFps    = 60;
      int   renderSampleRate = 48000;
      int   renderFormat = 0;     // 0 = mp4, 1 = mov, 2 = wav
      int   renderRangeKind = 0;  // 0 = whole, 1 = loop, 2 = markers, 3 = custom
      Tick  renderRangeStart = 0;
      Tick  renderRangeEnd   = 0;
      int   renderAudioSource = -1; // -1 = follow the monitoring mode
      int   renderVideoSource = -1; // -1 = auto
      std::string renderFolder;
   };

   struct Model
   {
      std::vector<Lane>   lanes;
      std::vector<Marker> markers;   // sorted by pos
      Settings            settings;
      uint64_t            nextId  = 1; // persisted; never recomputed as max+1
      uint64_t            revision = 0; // bumped by every op that changed data

      uint64_t NewId() { return nextId++; }
   };

   // Where a clip lives right now. Indices are only valid until the next edit.
   struct Loc
   {
      int lane = -1;
      int index = -1;
      bool Valid() const { return lane >= 0 && index >= 0; }
   };

   Loc Find(const Model& m, uint64_t clipId);
   const Clip* FindClip(const Model& m, uint64_t clipId);
   Clip*       FindClip(Model& m, uint64_t clipId);
   const Lane* FindLane(const Model& m, uint64_t laneId);
   Lane*       FindLane(Model& m, uint64_t laneId);
   int         LaneIndex(const Model& m, uint64_t laneId);

   // Every invariant this model promises, in one place. `why` (optional) gets
   // a human-readable first failure.
   bool Validate(const Model& m, std::string* why = nullptr);

   // End of the last clip on any lane, 0 when empty.
   Tick ArrangementEnd(const Model& m);

   // --- clip edit ops --------------------------------------------------
   // Each returns true if the model actually changed, and bumps `revision`
   // exactly once when it does. A false return leaves the model untouched.

   // Overwrite-style insert: trims or splits whatever `clip` lands on, then
   // inserts it in sorted position. `clip.id` is assigned if it is 0.
   bool PlaceOverwrite(Model& m, uint64_t laneId, Clip clip, uint64_t* outId = nullptr);

   // Moves every id by the same tick delta and the same lane delta. Moved
   // clips never trim each other - if they would overlap after the move, or
   // any lands on a lane of the wrong type, nothing moves and this returns
   // false. Stationary clips in the target lanes are overwritten.
   bool MoveClips(Model& m, const std::vector<uint64_t>& ids, Tick deltaTick, int laneDelta);

   // Drags one edge to `tick`. Clamped so length stays > 0 and the clip never
   // crosses its neighbours (the neighbour wins; use PlaceOverwrite to eat it).
   bool TrimEdge(Model& m, uint64_t id, int edge, Tick tick);

   // Cuts at an absolute tick strictly inside the clip. The right half gets a
   // fresh id (returned through outRightId) and keeps the group membership.
   bool Split(Model& m, uint64_t id, Tick tick, uint64_t* outRightId = nullptr);

   // Copies the selection as one block landing immediately after its own max
   // end, preserving relative lane and tick offsets. Groups are re-created
   // with fresh group ids so the copy is its own group.
   bool DuplicateBlock(Model& m, const std::vector<uint64_t>& ids, std::vector<uint64_t>* outNew = nullptr);

   bool Delete(Model& m, const std::vector<uint64_t>& ids);
   bool SetEnabled(Model& m, const std::vector<uint64_t>& ids, int mode);

   // --- groups ---------------------------------------------------------
   // A group needs >= 2 members; grouping fewer does nothing. Dropping to one
   // member (delete, ungroup-one) dissolves the group rather than leaving a
   // singleton, which Validate would reject.
   bool Group(Model& m, const std::vector<uint64_t>& ids, uint64_t* outGroupId = nullptr);
   bool Ungroup(Model& m, const std::vector<uint64_t>& groupIds);
   bool RemoveFromGroup(Model& m, const std::vector<uint64_t>& ids);
   std::vector<uint64_t> ClipsInGroup(const Model& m, uint64_t groupId);
   // Expands a selection so that every grouped member's whole group is in it.
   std::vector<uint64_t> ExpandSelectionToGroups(const Model& m, const std::vector<uint64_t>& ids);

   // WP5 fills these in; declared now so the UI can be written against the
   // final shape. TrimGroupEdge trims only the members touching `edge`;
   // ScaleGroup scales every member proportionally about the opposite edge.
   bool TrimGroupEdge(Model& m, uint64_t groupId, int edge, Tick tick);
   bool ScaleGroup(Model& m, uint64_t groupId, int edge, Tick tick);

   // --- lanes ----------------------------------------------------------
   uint64_t AddLane(Model& m, int type, int atIndex = -1);
   bool RemoveLane(Model& m, uint64_t laneId);
   bool ReorderLane(Model& m, uint64_t laneId, int newIndex);
   // Clears srcUid on every clip pointing at `uid` instead of deleting the
   // clip: deleting a node leaves its clips offline, not gone (WP5).
   bool ClearSource(Model& m, uint64_t uid);

   // --- markers --------------------------------------------------------
   uint64_t AddMarker(Model& m, Tick pos, const std::string& name = std::string(), uint32_t color = 0xFFFFFFFFu);
   bool MoveMarker(Model& m, uint64_t id, Tick pos);
   bool RenameMarker(Model& m, uint64_t id, const std::string& name);
   bool RecolorMarker(Model& m, uint64_t id, uint32_t color);
   bool DeleteMarker(Model& m, uint64_t id);

   // Re-sorts, clamps and dissolves singleton groups. Called at the end of
   // every op and after deserialization; safe to call on anything.
   void Normalize(Model& m);
}
