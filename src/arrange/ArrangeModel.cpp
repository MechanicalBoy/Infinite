#include "ArrangeModel.h"

#include <algorithm>
#include <cassert>
#include <limits>
#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>

namespace Arrange
{
namespace
{
   void ClampFades(Clip& c)
   {
      if (c.fadeIn < 0) c.fadeIn = 0;
      if (c.fadeOut < 0) c.fadeOut = 0;
      if (c.fadeIn > c.length) c.fadeIn = c.length;
      if (c.fadeOut > c.length) c.fadeOut = c.length;
   }

   void SortLane(Lane& l)
   {
      std::stable_sort(l.clips.begin(), l.clips.end(),
                       [](const Clip& a, const Clip& b) { return a.start < b.start; });
   }

   // Removes [a, b) from every clip on the lane, splitting a clip that strictly
   // contains the range. Returns true if anything changed. `m` is only needed
   // for fresh ids on a split. Assumes the lane is sorted; leaves it sorted.
   bool CarveRange(Model& m, Lane& lane, Tick a, Tick b)
   {
      if (b <= a) return false;
      bool changed = false;
      std::vector<Clip> out;
      out.reserve(lane.clips.size() + 1);
      for (Clip c : lane.clips)
      {
         const Tick s = c.start, e = c.End();
         if (e <= a || s >= b) { out.push_back(c); continue; }   // no overlap
         changed = true;
         if (s >= a && e <= b) continue;                         // fully eaten
         if (s < a && e > b)                                     // strictly contains
         {
            Clip left = c;
            left.length = a - s;
            ClampFades(left);
            out.push_back(left);

            Clip right = c;
            right.id = m.NewId();
            right.start = b;
            right.length = e - b;
            ClampFades(right);
            out.push_back(right);
            continue;
         }
         if (s < a)                                              // overlaps our left edge
         {
            c.length = a - s;
            ClampFades(c);
            out.push_back(c);
            continue;
         }
         // overlaps our right edge
         c.start = b;
         c.length = e - b;
         ClampFades(c);
         out.push_back(c);
      }
      if (changed)
      {
         lane.clips.swap(out);
         SortLane(lane);
      }
      return changed;
   }

   // A group with fewer than two live members is not a group. Dissolving here
   // rather than at every delete site is what keeps Validate's group rule true
   // no matter which op removed the member.
   bool DissolveSingletonGroups(Model& m)
   {
      std::unordered_map<uint64_t, int> counts;
      for (const Lane& l : m.lanes)
         for (const Clip& c : l.clips)
            if (c.groupId != 0) counts[c.groupId]++;
      bool changed = false;
      for (Lane& l : m.lanes)
         for (Clip& c : l.clips)
            if (c.groupId != 0 && counts[c.groupId] < 2) { c.groupId = 0; changed = true; }
      return changed;
   }
}

namespace
{
   // The one invariant Normalize cannot get by sorting alone. Anything that
   // reaches the model without going through an edit op - the legacy UI bridge
   // (PlaceClipTrimmingOverlap appends without sorting), a hand-edited patch,
   // a file from a build with a bug - can carry overlaps, and Validate would
   // then fail on data no op produced. Later clip wins, the earlier one is
   // trimmed off its tail: the same overwrite convention PlaceOverwrite uses,
   // so a clip never silently disappears under one that starts after it.
   bool ResolveOverlaps(Lane& l)
   {
      bool changed = false;
      for (size_t i = 0; i + 1 < l.clips.size(); i++)
      {
         Clip& a = l.clips[i];
         const Clip& b = l.clips[i + 1];
         if (a.End() <= b.start)
            continue;
         if (b.start <= a.start)
         {
            // Same start: nothing can be trimmed, one of the two has to go.
            // Keep the longer one - dropping "the earlier one" is arbitrary
            // when both start at the same tick, and this is the only place in
            // the model that destroys user data, so it should at least keep
            // the bigger piece.
            const size_t drop = (b.length > a.length) ? i : (i + 1);
            l.clips.erase(l.clips.begin() + (long)drop);
            i--;
            changed = true;
            continue;
         }
         a.length = b.start - a.start;
         ClampFades(a);
         changed = true;
      }
      return changed;
   }
}

void Normalize(Model& m)
{
   for (Lane& l : m.lanes)
   {
      for (Clip& clip : l.clips)
      {
         if (clip.start < 0) clip.start = 0;
         if (clip.length < 1) clip.length = 1;
         if (clip.srcOutput < 0) clip.srcOutput = 0;
         if (!std::isfinite(clip.gainDb)) clip.gainDb = 0.0f;
         ClampFades(clip);
         if (clip.id == 0) clip.id = m.NewId();
      }
      SortLane(l);
      ResolveOverlaps(l);
      if (l.id == 0) l.id = m.NewId();
   }
   std::stable_sort(m.markers.begin(), m.markers.end(),
                    [](const Marker& a, const Marker& b) { return a.pos < b.pos; });
   for (Marker& mk : m.markers)
      if (mk.id == 0) mk.id = m.NewId();

   // Re-mint collisions. Ids arriving from outside an edit op are not
   // trustworthy: the legacy UI's copy/paste/duplicate/split paths clone a
   // whole clip record, id included, and a hand-edited patch can do the same.
   // A duplicate id is worse than a lost one - Find() resolves to the first
   // match, so Delete/Group/MoveClips would silently hit the wrong clip and
   // every id-keyed cache (selection, waveform, thumbnail) would attach to
   // it. The clip that already sat at that id keeps it; later ones move.
   {
      std::unordered_set<uint64_t> seen;
      auto claim = [&](uint64_t& id) {
         if (id != 0 && seen.insert(id).second)
            return;
         do { id = m.NewId(); } while (!seen.insert(id).second);
      };
      for (Lane& l : m.lanes)
      {
         claim(l.id);
         for (Clip& c : l.clips) claim(c.id);
      }
      for (Marker& mk : m.markers) claim(mk.id);
   }

   DissolveSingletonGroups(m);

   // nextId must sit above everything already handed out. A patch whose saved
   // nextId was stale (hand-edited, or written by a build with the bug) would
   // otherwise hand out a duplicate on the next edit.
   uint64_t maxId = 0;
   for (const Lane& l : m.lanes)
   {
      maxId = std::max(maxId, l.id);
      for (const Clip& c : l.clips) { maxId = std::max(maxId, c.id); maxId = std::max(maxId, c.groupId); }
   }
   for (const Marker& mk : m.markers) maxId = std::max(maxId, mk.id);
   if (m.nextId <= maxId) m.nextId = maxId + 1;

   // Normalize is the funnel every un-vetted model passes through, so this is
   // the one place worth paying for the check: if it can't produce a valid
   // model, the repair above has a hole and the fixtures should say so loudly
   // rather than letting the bad model reach disk.
#ifndef NDEBUG
   {
      std::string why;
      assert(Validate(m, &why) && "Arrange::Normalize left the model invalid");
      (void)why;
   }
#endif
}

Loc Find(const Model& m, uint64_t clipId)
{
   if (clipId == 0) return Loc{};
   for (size_t li = 0; li < m.lanes.size(); li++)
      for (size_t ci = 0; ci < m.lanes[li].clips.size(); ci++)
         if (m.lanes[li].clips[ci].id == clipId) return Loc{(int)li, (int)ci};
   return Loc{};
}

const Clip* FindClip(const Model& m, uint64_t clipId)
{
   const Loc loc = Find(m, clipId);
   return loc.Valid() ? &m.lanes[loc.lane].clips[loc.index] : nullptr;
}

Clip* FindClip(Model& m, uint64_t clipId)
{
   const Loc loc = Find(m, clipId);
   return loc.Valid() ? &m.lanes[loc.lane].clips[loc.index] : nullptr;
}

int LaneIndex(const Model& m, uint64_t laneId)
{
   for (size_t i = 0; i < m.lanes.size(); i++)
      if (m.lanes[i].id == laneId) return (int)i;
   return -1;
}

const Lane* FindLane(const Model& m, uint64_t laneId)
{
   const int i = LaneIndex(m, laneId);
   return i >= 0 ? &m.lanes[i] : nullptr;
}

Lane* FindLane(Model& m, uint64_t laneId)
{
   const int i = LaneIndex(m, laneId);
   return i >= 0 ? &m.lanes[i] : nullptr;
}

bool Validate(const Model& m, std::string* why)
{
   auto fail = [&](const std::string& msg) { if (why) *why = msg; return false; };

   std::unordered_set<uint64_t> ids;
   std::unordered_map<uint64_t, int> groupCounts;
   for (const Lane& l : m.lanes)
   {
      if (l.id == 0) return fail("lane with id 0");
      if (!ids.insert(l.id).second) return fail("duplicate lane id " + std::to_string(l.id));
      if (l.id >= m.nextId) return fail("lane id " + std::to_string(l.id) + " >= nextId");
      if (l.type != kLaneVideo && l.type != kLaneAudio) return fail("bad lane type");

      Tick prevEnd = 0;
      bool first = true;
      for (const Clip& c : l.clips)
      {
         if (c.id == 0) return fail("clip with id 0");
         if (!ids.insert(c.id).second) return fail("duplicate clip id " + std::to_string(c.id));
         if (c.id >= m.nextId) return fail("clip id " + std::to_string(c.id) + " >= nextId");
         if (c.start < 0) return fail("negative clip start");
         if (c.length <= 0) return fail("clip length <= 0");
         if (c.fadeIn < 0 || c.fadeOut < 0 || c.fadeIn > c.length || c.fadeOut > c.length)
            return fail("fade outside clip");
         if (!first && c.start < prevEnd)
            return fail("clips overlap or unsorted on lane " + std::to_string(l.id));
         prevEnd = c.End();
         first = false;
         if (c.groupId != 0)
         {
            if (c.groupId >= m.nextId) return fail("group id >= nextId");
            groupCounts[c.groupId]++;
         }
      }
   }
   for (const auto& g : groupCounts)
      if (g.second < 2) return fail("group " + std::to_string(g.first) + " has one member");

   Tick prev = 0;
   bool firstMarker = true;
   for (const Marker& mk : m.markers)
   {
      if (mk.id == 0) return fail("marker with id 0");
      if (!ids.insert(mk.id).second) return fail("duplicate marker id " + std::to_string(mk.id));
      if (mk.id >= m.nextId) return fail("marker id >= nextId");
      if (mk.pos < 0) return fail("negative marker position");
      if (!firstMarker && mk.pos < prev) return fail("markers unsorted");
      prev = mk.pos;
      firstMarker = false;
   }
   if (why) why->clear();
   return true;
}

Tick ArrangementEnd(const Model& m)
{
   Tick end = 0;
   for (const Lane& l : m.lanes)
      if (!l.clips.empty()) end = std::max(end, l.clips.back().End());
   return end;
}

bool PlaceOverwrite(Model& m, uint64_t laneId, Clip clip, uint64_t* outId)
{
   Lane* lane = FindLane(m, laneId);
   if (!lane) return false;
   if (clip.length <= 0) return false;
   if (clip.start < 0) clip.start = 0;
   ClampFades(clip);
   if (clip.id == 0) clip.id = m.NewId();

   CarveRange(m, *lane, clip.start, clip.End());
   lane->clips.push_back(clip);
   SortLane(*lane);
   DissolveSingletonGroups(m);
   m.revision++;
   if (outId) *outId = clip.id;
   return true;
}

bool MoveClips(Model& m, const std::vector<uint64_t>& ids, Tick deltaTick, int laneDelta)
{
   if (ids.empty()) return false;
   if (deltaTick == 0 && laneDelta == 0) return false;

   // Gather, checking every id resolves and every destination lane exists and
   // matches the clip's current lane type. Bail before touching anything.
   struct Moving { Clip clip; int dstLane; };
   std::vector<Moving> moving;
   std::unordered_set<uint64_t> movingIds;
   Tick minStart = 0;
   bool haveMin = false;
   for (uint64_t id : ids)
   {
      const Loc loc = Find(m, id);
      if (!loc.Valid()) return false;
      if (!movingIds.insert(id).second) continue;
      const Clip& c = m.lanes[loc.lane].clips[loc.index];
      const int dst = loc.lane + laneDelta;
      if (dst < 0 || dst >= (int)m.lanes.size()) return false;
      if (m.lanes[dst].type != m.lanes[loc.lane].type) return false;
      if (!haveMin || c.start < minStart) { minStart = c.start; haveMin = true; }
      moving.push_back(Moving{c, dst});
   }
   if (moving.empty()) return false;
   // The whole block stops at 0 rather than each clip clamping individually,
   // which would silently squash the block's internal spacing.
   if (minStart + deltaTick < 0) deltaTick = -minStart;
   if (deltaTick == 0 && laneDelta == 0) return false;

   for (Moving& mv : moving) mv.clip.start += deltaTick;

   // Moved clips must not collide with each other (two clips from different
   // lanes can land on the same one).
   std::map<int, std::vector<const Clip*>> byDst;
   for (const Moving& mv : moving) byDst[mv.dstLane].push_back(&mv.clip);
   for (auto& kv : byDst)
   {
      std::vector<const Clip*>& v = kv.second;
      std::sort(v.begin(), v.end(), [](const Clip* a, const Clip* b) { return a->start < b->start; });
      for (size_t i = 1; i < v.size(); i++)
         if (v[i]->start < v[i - 1]->End()) return false;
   }

   // Lift the movers out, carve their destinations, drop them back in.
   for (Lane& l : m.lanes)
      l.clips.erase(std::remove_if(l.clips.begin(), l.clips.end(),
                                   [&](const Clip& c) { return movingIds.count(c.id) != 0; }),
                    l.clips.end());
   for (const Moving& mv : moving)
      CarveRange(m, m.lanes[mv.dstLane], mv.clip.start, mv.clip.End());
   for (const Moving& mv : moving)
      m.lanes[mv.dstLane].clips.push_back(mv.clip);
   for (Lane& l : m.lanes) SortLane(l);
   DissolveSingletonGroups(m);
   m.revision++;
   return true;
}

bool TrimEdge(Model& m, uint64_t id, int edge, Tick tick)
{
   const Loc loc = Find(m, id);
   if (!loc.Valid()) return false;
   Lane& lane = m.lanes[loc.lane];
   Clip& c = lane.clips[loc.index];

   if (edge == kEdgeStart)
   {
      const Tick lo = (loc.index > 0) ? lane.clips[loc.index - 1].End() : 0;
      const Tick hi = c.End() - 1;
      tick = std::clamp(tick, lo, hi);
      if (tick == c.start) return false;
      const Tick end = c.End();
      c.start = tick;
      c.length = end - tick;
   }
   else
   {
      const Tick lo = c.start + 1;
      // No neighbour to the right: cap at kMaxTick rather than a raw int64
      // sentinel, so a runaway drag can't produce a clip whose end converts to
      // ~10^11 seconds and takes ArrangementEnd (and the ruler) with it.
      const Tick hi = (loc.index + 1 < (int)lane.clips.size())
                          ? lane.clips[loc.index + 1].start
                          : kMaxTick;
      tick = std::clamp(tick, lo, hi);
      if (tick == c.End()) return false;
      c.length = tick - c.start;
   }
   ClampFades(c);
   SortLane(lane);
   m.revision++;
   return true;
}

bool Split(Model& m, uint64_t id, Tick tick, uint64_t* outRightId)
{
   const Loc loc = Find(m, id);
   if (!loc.Valid()) return false;
   Lane& lane = m.lanes[loc.lane];
   Clip& c = lane.clips[loc.index];
   if (tick <= c.start || tick >= c.End()) return false;

   Clip right = c;
   right.id = m.NewId();
   right.start = tick;
   right.length = c.End() - tick;
   right.fadeIn = 0;                    // the cut is not a fade
   ClampFades(right);

   c.length = tick - c.start;
   c.fadeOut = 0;
   ClampFades(c);

   lane.clips.insert(lane.clips.begin() + loc.index + 1, right);
   SortLane(lane);
   m.revision++;
   if (outRightId) *outRightId = right.id;
   return true;
}

bool DuplicateBlock(Model& m, const std::vector<uint64_t>& ids, std::vector<uint64_t>* outNew)
{
   if (ids.empty()) return false;
   struct Src { Clip clip; int lane; };
   std::vector<Src> src;
   std::unordered_set<uint64_t> seen;
   Tick minStart = 0, maxEnd = 0;
   bool have = false;
   for (uint64_t id : ids)
   {
      const Loc loc = Find(m, id);
      if (!loc.Valid()) continue;
      if (!seen.insert(id).second) continue;
      const Clip& c = m.lanes[loc.lane].clips[loc.index];
      if (!have) { minStart = c.start; maxEnd = c.End(); have = true; }
      else { minStart = std::min(minStart, c.start); maxEnd = std::max(maxEnd, c.End()); }
      src.push_back(Src{c, loc.lane});
   }
   if (src.empty()) return false;

   // One block delta for every copy - copying each clip to just after itself
   // is what made the first copy overwrite the second original (WP5).
   const Tick delta = maxEnd - minStart;
   std::unordered_map<uint64_t, uint64_t> groupRemap;
   std::vector<uint64_t> made;
   for (const Src& s : src)
   {
      Clip c = s.clip;
      c.id = m.NewId();
      c.start += delta;
      if (c.groupId != 0)
      {
         auto it = groupRemap.find(c.groupId);
         if (it == groupRemap.end()) it = groupRemap.emplace(c.groupId, m.NewId()).first;
         c.groupId = it->second;
      }
      CarveRange(m, m.lanes[s.lane], c.start, c.End());
      m.lanes[s.lane].clips.push_back(c);
      made.push_back(c.id);
   }
   for (Lane& l : m.lanes) SortLane(l);
   DissolveSingletonGroups(m);
   m.revision++;
   if (outNew) *outNew = made;
   return true;
}

bool Delete(Model& m, const std::vector<uint64_t>& ids)
{
   if (ids.empty()) return false;
   std::unordered_set<uint64_t> kill(ids.begin(), ids.end());
   bool changed = false;
   for (Lane& l : m.lanes)
   {
      const size_t before = l.clips.size();
      l.clips.erase(std::remove_if(l.clips.begin(), l.clips.end(),
                                   [&](const Clip& c) { return kill.count(c.id) != 0; }),
                    l.clips.end());
      changed = changed || l.clips.size() != before;
   }
   if (!changed) return false;
   DissolveSingletonGroups(m);
   m.revision++;
   return true;
}

bool SetEnabled(Model& m, const std::vector<uint64_t>& ids, int mode)
{
   if (ids.empty()) return false;
   std::unordered_set<uint64_t> want(ids.begin(), ids.end());
   bool changed = false;
   for (Lane& l : m.lanes)
      for (Clip& c : l.clips)
      {
         if (!want.count(c.id)) continue;
         const bool next = (mode == kToggle) ? !c.enabled : (mode == kEnable);
         if (next != c.enabled) { c.enabled = next; changed = true; }
      }
   if (changed) m.revision++;
   return changed;
}

std::vector<uint64_t> ClipsInGroup(const Model& m, uint64_t groupId)
{
   std::vector<uint64_t> out;
   if (groupId == 0) return out;
   for (const Lane& l : m.lanes)
      for (const Clip& c : l.clips)
         if (c.groupId == groupId) out.push_back(c.id);
   return out;
}

std::vector<uint64_t> ExpandSelectionToGroups(const Model& m, const std::vector<uint64_t>& ids)
{
   std::unordered_set<uint64_t> groups;
   for (uint64_t id : ids)
      if (const Clip* c = FindClip(m, id))
         if (c->groupId != 0) groups.insert(c->groupId);
   std::unordered_set<uint64_t> out(ids.begin(), ids.end());
   for (const Lane& l : m.lanes)
      for (const Clip& c : l.clips)
         if (c.groupId != 0 && groups.count(c.groupId)) out.insert(c.id);
   std::vector<uint64_t> v(out.begin(), out.end());
   std::sort(v.begin(), v.end());
   return v;
}

bool Group(Model& m, const std::vector<uint64_t>& ids, uint64_t* outGroupId)
{
   std::unordered_set<uint64_t> uniq;
   for (uint64_t id : ids)
      if (Find(m, id).Valid()) uniq.insert(id);
   if (uniq.size() < 2) return false;
   const uint64_t gid = m.NewId();
   for (Lane& l : m.lanes)
      for (Clip& c : l.clips)
         if (uniq.count(c.id)) c.groupId = gid;
   DissolveSingletonGroups(m);
   m.revision++;
   if (outGroupId) *outGroupId = gid;
   return true;
}

bool Ungroup(Model& m, const std::vector<uint64_t>& groupIds)
{
   std::unordered_set<uint64_t> g(groupIds.begin(), groupIds.end());
   g.erase(0);
   if (g.empty()) return false;
   bool changed = false;
   for (Lane& l : m.lanes)
      for (Clip& c : l.clips)
         if (g.count(c.groupId)) { c.groupId = 0; changed = true; }
   if (changed) m.revision++;
   return changed;
}

bool RemoveFromGroup(Model& m, const std::vector<uint64_t>& ids)
{
   std::unordered_set<uint64_t> want(ids.begin(), ids.end());
   bool changed = false;
   for (Lane& l : m.lanes)
      for (Clip& c : l.clips)
         if (want.count(c.id) && c.groupId != 0) { c.groupId = 0; changed = true; }
   if (!changed) return false;
   DissolveSingletonGroups(m);
   m.revision++;
   return true;
}

bool TrimGroupEdge(Model& m, uint64_t groupId, int edge, Tick tick)
{
   // Only the members flush with the dragged edge move; interior clips keep
   // their own bounds (Ableton's group-edge behaviour, WP5).
   //
   // Runs under a live drag, once per frame, so it is one pass over the lanes
   // with no per-member Find (the old version was O(members x clips)). The
   // in-place trim is exact: a start-edge trim never moves any clip's end,
   // and an end-edge trim never moves any clip's start, so the neighbour each
   // member clamps against is the same whether or not it is itself a member.
   if (groupId == 0) return false;
   Tick bound = 0;
   bool have = false;
   for (const Lane& l : m.lanes)
      for (const Clip& c : l.clips)
      {
         if (c.groupId != groupId) continue;
         const Tick v = (edge == kEdgeStart) ? c.start : c.End();
         if (!have) { bound = v; have = true; }
         else bound = (edge == kEdgeStart) ? std::min(bound, v) : std::max(bound, v);
      }
   if (!have) return false;

   bool changed = false;
   for (Lane& lane : m.lanes)
   {
      for (size_t i = 0; i < lane.clips.size(); i++)
      {
         Clip& c = lane.clips[i];
         if (c.groupId != groupId) continue;
         if (edge == kEdgeStart)
         {
            if (c.start != bound) continue;
            const Tick lo = (i > 0) ? lane.clips[i - 1].End() : 0;
            const Tick hi = c.End() - 1;
            const Tick t = std::clamp(tick, lo, hi);
            if (t == c.start) continue;
            const Tick end = c.End();
            c.start = t;
            c.length = end - t;
         }
         else
         {
            if (c.End() != bound) continue;
            const Tick lo = c.start + 1;
            const Tick hi = (i + 1 < lane.clips.size()) ? lane.clips[i + 1].start : kMaxTick;
            const Tick t = std::clamp(tick, lo, hi);
            if (t == c.End()) continue;
            c.length = t - c.start;
         }
         ClampFades(c);
         changed = true;
      }
   }
   // One bump per op, like every other op (it used to bump once per member).
   if (changed) m.revision++;
   return changed;
}

bool ScaleGroup(Model& m, uint64_t groupId, int edge, Tick tick)
{
   if (groupId == 0) return false;
   Tick lo = 0, hi = 0;
   int count = 0;
   for (const Lane& l : m.lanes)
      for (const Clip& c : l.clips)
      {
         if (c.groupId != groupId) continue;
         if (count == 0) { lo = c.start; hi = c.End(); }
         else { lo = std::min(lo, c.start); hi = std::max(hi, c.End()); }
         count++;
      }
   if (count < 2 || hi <= lo) return false;

   // Scale about the opposite edge; a factor <= 0 would invert the block.
   const Tick pivot = (edge == kEdgeStart) ? hi : lo;
   const double oldSpan = (double)(hi - lo);
   const double newSpan = (edge == kEdgeStart) ? (double)(pivot - tick) : (double)(tick - pivot);
   if (!(newSpan > 0.0)) return false;
   const double f = newSpan / oldSpan;

   auto scaledSpan = [&](const Clip& c, Tick& outStart, Tick& outLen)
   {
      const Tick s = pivot + (Tick)llround((double)(c.start - pivot) * f);
      const Tick e = pivot + (Tick)llround((double)(c.End() - pivot) * f);
      outStart = std::max<Tick>(0, std::min(s, e));
      outLen = std::max<Tick>(1, std::llabs(e - s));
   };

   // Check first, lane by lane, touching only lanes that hold a member: each
   // lane's clips as (start, end) with members at their scaled span, sorted,
   // must not overlap. Scaling can push a member into a non-member neighbour;
   // rather than silently eating an untouched clip, refuse the gesture. (This
   // used to copy the whole Model and Validate it - per frame, under a drag.)
   bool any = false;
   std::vector<std::pair<Tick, Tick>> spans;
   for (const Lane& l : m.lanes)
   {
      bool laneHasMember = false;
      for (const Clip& c : l.clips)
         if (c.groupId == groupId) { laneHasMember = true; break; }
      if (!laneHasMember) continue;
      spans.clear();
      for (const Clip& c : l.clips)
      {
         if (c.groupId == groupId)
         {
            Tick s = 0, len = 0;
            scaledSpan(c, s, len);
            if (s != c.start || len != c.length) any = true;
            spans.emplace_back(s, s + len);
         }
         else
            spans.emplace_back(c.start, c.End());
      }
      std::sort(spans.begin(), spans.end());
      for (size_t i = 1; i < spans.size(); i++)
         if (spans[i].first < spans[i - 1].second) return false;
   }
   if (!any) return false;

   for (Lane& l : m.lanes)
   {
      bool touched = false;
      for (Clip& c : l.clips)
      {
         if (c.groupId != groupId) continue;
         Tick s = 0, len = 0;
         scaledSpan(c, s, len);
         c.start = s;
         c.length = len;
         ClampFades(c);
         touched = true;
      }
      if (touched) SortLane(l);
   }
   m.revision++;
   return true;
}

uint64_t AddLane(Model& m, int type, int atIndex)
{
   Lane l;
   l.id = m.NewId();
   l.type = (type == kLaneAudio) ? kLaneAudio : kLaneVideo;
   const int at = (atIndex < 0 || atIndex > (int)m.lanes.size()) ? (int)m.lanes.size() : atIndex;
   m.lanes.insert(m.lanes.begin() + at, l);
   m.revision++;
   return l.id;
}

bool RemoveLane(Model& m, uint64_t laneId)
{
   const int i = LaneIndex(m, laneId);
   if (i < 0) return false;
   m.lanes.erase(m.lanes.begin() + i);
   DissolveSingletonGroups(m);
   m.revision++;
   return true;
}

bool ReorderLane(Model& m, uint64_t laneId, int newIndex)
{
   const int i = LaneIndex(m, laneId);
   if (i < 0) return false;
   newIndex = std::clamp(newIndex, 0, (int)m.lanes.size() - 1);
   if (newIndex == i) return false;
   Lane l = m.lanes[i];
   m.lanes.erase(m.lanes.begin() + i);
   m.lanes.insert(m.lanes.begin() + newIndex, l);
   m.revision++;
   return true;
}

bool ClearSource(Model& m, uint64_t uid)
{
   if (uid == 0) return false;
   bool changed = false;
   for (Lane& l : m.lanes)
      for (Clip& c : l.clips)
         if (c.srcUid == uid) { c.srcUid = 0; changed = true; }
   if (changed) m.revision++;
   return changed;
}

uint64_t AddMarker(Model& m, Tick pos, const std::string& name, uint32_t color)
{
   Marker mk;
   mk.id = m.NewId();
   mk.pos = std::max<Tick>(0, pos);
   mk.name = name;
   mk.color = color;
   m.markers.push_back(mk);
   std::stable_sort(m.markers.begin(), m.markers.end(),
                    [](const Marker& a, const Marker& b) { return a.pos < b.pos; });
   m.revision++;
   return mk.id;
}

bool MoveMarker(Model& m, uint64_t id, Tick pos)
{
   pos = std::max<Tick>(0, pos);
   for (Marker& mk : m.markers)
      if (mk.id == id)
      {
         if (mk.pos == pos) return false;
         mk.pos = pos;
         std::stable_sort(m.markers.begin(), m.markers.end(),
                          [](const Marker& a, const Marker& b) { return a.pos < b.pos; });
         m.revision++;
         return true;
      }
   return false;
}

bool RenameMarker(Model& m, uint64_t id, const std::string& name)
{
   for (Marker& mk : m.markers)
      if (mk.id == id)
      {
         if (mk.name == name) return false;
         mk.name = name;
         m.revision++;
         return true;
      }
   return false;
}

bool RecolorMarker(Model& m, uint64_t id, uint32_t color)
{
   for (Marker& mk : m.markers)
      if (mk.id == id)
      {
         if (mk.color == color) return false;
         mk.color = color;
         m.revision++;
         return true;
      }
   return false;
}

bool DeleteMarker(Model& m, uint64_t id)
{
   const size_t before = m.markers.size();
   m.markers.erase(std::remove_if(m.markers.begin(), m.markers.end(),
                                  [&](const Marker& mk) { return mk.id == id; }),
                   m.markers.end());
   if (m.markers.size() == before) return false;
   m.revision++;
   return true;
}
}
