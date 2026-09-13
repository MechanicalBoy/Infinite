#include "ArrangeLegacy.h"

#include "ArrangeModel.h"

#include <algorithm>

namespace LegacyArrange
{
void FromLegacyStreams(const std::vector<StreamRecord>& streams, double bpm,
                       IndexToUid toUid, void* ctx, Arrange::Model& model)
{
   model.lanes.clear();
   model.lanes.reserve(streams.size());
   for (const StreamRecord& s : streams)
   {
      Arrange::Lane lane;
      lane.id = s.id ? s.id : model.NewId();
      lane.type = (s.type == Arrange::kLaneAudio) ? Arrange::kLaneAudio : Arrange::kLaneVideo;
      lane.blendMode = s.blendMode;
      lane.opacity = s.opacity;
      lane.gainDb = s.gainDb;
      lane.pan = s.pan;
      lane.name = s.name;
      for (const ClipRecord& c : s.clips)
      {
         Arrange::Clip clip;
         clip.id = c.id ? c.id : model.NewId();
         clip.start = std::max<Arrange::Tick>(0, Arrange::SecondsToTicks(c.startSeconds, bpm));
         clip.length = std::max<Arrange::Tick>(1, Arrange::SecondsToTicks(c.lengthSeconds, bpm));
         // The live node index wins over the carried uid: the UI is what just
         // edited this clip, so a reassignment there must not be overwritten
         // by a stale uid riding along from the last load.
         clip.srcUid = (c.srcIndex >= 0 && toUid) ? toUid(c.srcIndex, ctx) : c.srcUid;
         clip.srcOutput = c.srcOutput;
         clip.fadeIn = Arrange::SecondsToTicks(c.fadeInSec, bpm);
         clip.fadeOut = Arrange::SecondsToTicks(c.fadeOutSec, bpm);
         clip.gainDb = c.gainDb;
         clip.enabled = c.enabled;
         clip.groupId = c.groupId;
         clip.name = c.name;
         clip.colorR = c.colorR;
         clip.colorG = c.colorG;
         clip.colorB = c.colorB;
         lane.clips.push_back(clip);
      }
      model.lanes.push_back(std::move(lane));
   }
   // The UI's overlap handling is not the model's: PlaceClipTrimmingOverlap
   // appends without sorting. Normalize sorts, clamps and re-seats nextId so
   // whatever the UI produced satisfies the model's invariants from here on.
   Arrange::Normalize(model);
}

void ToLegacyStreams(const Arrange::Model& model, double bpm,
                     UidToIndex toIndex, void* ctx, std::vector<StreamRecord>& out)
{
   out.clear();
   out.reserve(model.lanes.size());
   for (const Arrange::Lane& lane : model.lanes)
   {
      StreamRecord s;
      s.id = lane.id;
      s.type = lane.type;
      s.blendMode = lane.blendMode;
      s.opacity = lane.opacity;
      s.gainDb = lane.gainDb;
      s.pan = lane.pan;
      s.name = lane.name;
      for (const Arrange::Clip& c : lane.clips)
      {
         ClipRecord r;
         r.id = c.id;
         r.startSeconds = Arrange::TicksToSeconds(c.start, bpm);
         r.lengthSeconds = Arrange::TicksToSeconds(c.length, bpm);
         r.srcUid = c.srcUid;
         r.srcIndex = (c.srcUid != 0 && toIndex) ? toIndex(c.srcUid, ctx) : -1;
         r.srcOutput = c.srcOutput;
         r.fadeInSec = (float)Arrange::TicksToSeconds(c.fadeIn, bpm);
         r.fadeOutSec = (float)Arrange::TicksToSeconds(c.fadeOut, bpm);
         r.gainDb = c.gainDb;
         r.enabled = c.enabled;
         r.groupId = c.groupId;
         r.name = c.name;
         r.colorR = c.colorR;
         r.colorG = c.colorG;
         r.colorB = c.colorB;
         s.clips.push_back(r);
      }
      out.push_back(std::move(s));
   }
}
}
