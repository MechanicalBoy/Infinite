// INFINITE_NOTEAUDIT: a measurement audit of the note nodes.
//
// The note-side twin of FXAUDIT / MODAUDIT / SYNTHAUDIT (docs/plans/node-audits/
// README.md, block 2). Each node runs through its real node -> audio node
// ProcessBlock, wired to real NoteEventQueues the way the topology builder
// does it, with the Transport clock advanced the way the audio callback does
// it (AdvanceAudioClock before the graph runs), and gets:
//
//   PAIR    a scripted overlapping stream goes in (input nodes) or the
//           transport plays 4 s (source nodes); every output note-on must have
//           exactly one note-off by voiceId, never before its on, none stuck
//           after the input has released everything / the transport stops
//   GRID    (arp, sequencer, random generator) note-on position in samples
//           against the ideal beat grid at 60/90/120/128/174 bpm and block
//           sizes 64/512/800/333/2048 (24/60/144 fps at 48 kHz); flag > 1 sample
//   SWING   random generator groove 0.5 / 1.0: delay of odd steps against
//           groove * 0.5 * rateBeats, flag > 1 %
//   HUMAN   humanizer timing: spread within the knob, and the same stream
//           after PrepareToPlay gives the same output (seeded determinism)
//   LOOP    a transport loop wrap and a seek during playback: pair integrity
//   CPU     ns per 512-frame block while active
//
// Only hard invariants fail the run (a note-on without its off at the end of
// the stream). Everything else is reported, with FLAG lines past the
// thresholds above.
#include "app/AppShared.h"
#include "audio/AudioBuffer.h"
#include "audio/NoteEventQueue.h"
#include "core/Transport.h"
#include "nodes/NoteNodes.h"

#include <chrono>
#include <map>

namespace app
{
namespace
{
   constexpr double kRate = 48000.0;
   constexpr double kFlagGridSamples = 1.0;
   constexpr double kFlagSwingPct = 1.0;

   struct Flags
   {
      int n = 0;
      void Flag(const char* sec, const char* node, const char* what, double v)
      {
         printf("NOTEAUDIT FLAG %-5s %-18s %s %.2f\n", sec, node, what, v);
         n++;
      }
   };

   struct Evt
   {
      long long sample; // absolute: block start + frameOffset
      NoteEvent e;
   };

   // One node wired to numIn input queues, with one consumer on its outbox.
   struct Rig
   {
      std::unique_ptr<INode> node;
      AudioNode* audio = nullptr;
      NoteEventQueue in[2];
      NoteEventQueue* out = nullptr;
      int outCursor = -1;
      int block = 512;
      long long pos = 0;
      int frame = 1;
      std::vector<float> l, r;
      std::vector<Evt> got;

      bool Init(INode* n, int blockSize = 512)
      {
         node.reset(n);
         block = blockSize;
         l.assign(block, 0.0f);
         r.assign(block, 0.0f);
         INoteSource* src = dynamic_cast<INoteSource*>(n);
         if (src == nullptr)
            return false;
         n->CookIfNeeded(frame++);
         audio = src->GetAudioNode();
         if (audio == nullptr)
            return false;
         audio->PrepareToPlay(kRate, block);
         for (int s = 0; s < 8; s++)
         {
            if (n->NoteInputSlot(s) == nullptr)
               continue;
            const int q = std::min(s, 1);
            audio->SetNoteInbox(s, &in[q], in[q].RegisterConsumer());
         }
         out = audio->NoteOutbox();
         if (out == nullptr)
            return false;
         outCursor = out->RegisterConsumer();
         return true;
      }

      // Transport must be playing; advances the audio clock first, as the
      // engine does, then runs one block and collects the outbox.
      void Step()
      {
         Transport::Instance().AdvanceAudioClock(block);
         node->CookIfNeeded(frame++);
         AudioBuffer buf;
         float* ch[2] = { l.data(), r.data() };
         buf.channels = ch;
         buf.numChannels = 2;
         buf.numFrames = block;
         audio->ProcessBlock(nullptr, 0, buf);
         NoteEvent evts[64];
         int n;
         while ((n = out->Pop(outCursor, evts, 64)) > 0)
            for (int i = 0; i < n; i++)
               got.push_back({ pos + std::clamp(evts[i].frameOffset, 0, block - 1), evts[i] });
         pos += block;
      }
      void Run(double seconds)
      {
         const long long end = pos + (long long)(seconds * kRate);
         while (pos < end)
            Step();
      }
   };

   void StartTransport(double bpm)
   {
      Transport& t = Transport::Instance();
      t.SetOfflineMode(false);
      t.SetLoop(false, 0.0, 4.0);
      t.SetPlaying(false);
      t.SetTempo((float)bpm);
      t.Seek(0.0);
      t.NotifyAudioEngineStarted(kRate);
      t.SetPlaying(true);
   }
   void StopTransport()
   {
      Transport& t = Transport::Instance();
      t.SetPlaying(false);
      t.NotifyAudioEngineStopped();
   }

   void Push(NoteEventQueue& q, int note, float vel, bool on, int voice, int offset = 0)
   {
      NoteEvent e;
      e.note = note;
      e.velocity = vel;
      e.isNoteOn = on;
      e.voiceId = voice;
      e.frameOffset = offset;
      q.Push(e);
   }

   // Pair integrity over an output stream. Returns the number of problems.
   struct PairReport
   {
      int ons = 0, offs = 0, stuck = 0, orphanOff = 0, dupOn = 0, offBeforeOn = 0;
      bool Bad() const { return stuck || orphanOff || dupOn || offBeforeOn; }
   };
   PairReport Pairs(const std::vector<Evt>& got)
   {
      PairReport p;
      std::map<int, long long> open;
      std::map<int, bool> closed;
      for (const Evt& g : got)
      {
         if (g.e.bendUpdate)
            continue;
         if (g.e.isNoteOn)
         {
            p.ons++;
            if (open.count(g.e.voiceId) || closed.count(g.e.voiceId))
               p.dupOn++;
            open[g.e.voiceId] = g.sample;
         }
         else
         {
            p.offs++;
            auto it = open.find(g.e.voiceId);
            if (it == open.end())
               p.orphanOff++;
            else
            {
               if (g.sample < it->second)
                  p.offBeforeOn++;
               open.erase(it);
               closed[g.e.voiceId] = true;
            }
         }
      }
      p.stuck = (int)open.size();
      return p;
   }

   struct Case
   {
      const char* name;
      std::function<INode*()> create;
      std::function<void(INode*)> setup; // param tweaks (optional)
      bool source;                        // no note input: transport drives it
   };

   const std::vector<Case>& Cases()
   {
      static const std::vector<Case> c = {
         { "Note Filter", [] { return NoteFilterNode::Create(); }, nullptr, false },
         { "Note Transpose", [] { return NoteTransposeNode::Create(); }, [](INode* n) { static_cast<NoteTransposeNode*>(n)->semitones = 7; }, false },
         { "Pitch Bend", [] { return PitchBendNode::Create(); }, [](INode* n) { static_cast<PitchBendNode*>(n)->bendSemitones = 1.0f; }, false },
         { "Velocity Curve", [] { return VelocityCurveNode::Create(); }, [](INode* n) { static_cast<VelocityCurveNode*>(n)->curve = 2.0f; }, false },
         { "Gate", [] { return GateNode::Create(); }, [](INode* n) { static_cast<GateNode*>(n)->holdMs = 300.0f; }, false },
         { "Humanizer", [] { return HumanizerNode::Create(); }, [](INode* n) { auto* h = static_cast<HumanizerNode*>(n); h->timingMs = 30.0f; h->velocityPct = 30.0f; }, false },
         { "Quantizer", [] { return QuantizerNode::Create(); }, [](INode* n) { static_cast<QuantizerNode*>(n)->div = 3; }, false },
         { "Glide", [] { return GlideNode::Create(); }, [](INode* n) { static_cast<GlideNode*>(n)->glideMs = 100.0f; }, false },
         { "Note Echo", [] { return NoteEchoNode::Create(); }, nullptr, false },
         { "Note Router", [] { return NoteRouterNode::Create(); }, nullptr, false },
         { "Note Merge", [] { return NoteMergeNode::Create(); }, nullptr, false },
         { "Note Switcher", [] { return NoteSwitcherNode::Create(); }, nullptr, false },
         { "Arpeggiator", [] { return ArpeggiatorNode::Create(); }, nullptr, false },
         { "Chorder", [] { return ChorderNode::Create(); }, nullptr, true },
         { "Note Stack", [] { return NoteStackNode::Create(); }, nullptr, false },
         { "Note Strum", [] { return NoteStrumNode::Create(); }, nullptr, false },
         { "Note Capturer", [] { return NoteCapturerNode::Create(); }, nullptr, false },
         { "Note Sequencer", [] { return NoteSequencerNode::Create(); }, nullptr, true },
         { "Random Note Gen", [] { return RandomNoteGeneratorNode::Create(); }, nullptr, true },
         { "Bouncing Balls", [] { return BouncingBallsNode::Create(); }, nullptr, true },
      };
      return c;
   }

   // Four overlapping notes across the first second, all released by 1.5 s.
   void ScriptedStream(Rig& rig, double tSec)
   {
      struct Ev { double t; int note; bool on; int voice; };
      static const Ev kScript[] = {
         { 0.00, 60, true, 9001 }, { 0.10, 64, true, 9002 }, { 0.20, 67, true, 9003 }, { 0.30, 60, true, 9004 },
         { 0.50, 64, false, 9002 }, { 0.70, 60, false, 9001 }, { 1.00, 67, false, 9003 }, { 1.30, 60, false, 9004 },
      };
      static const double kStep = 0.0; (void)kStep;
      for (const Ev& e : kScript)
      {
         const double t0 = tSec, t1 = tSec + (double)rig.block / kRate;
         if (e.t >= t0 && e.t < t1)
            Push(rig.in[0], e.note, 0.8f, e.on, e.voice, (int)((e.t - t0) * kRate));
      }
   }

   void AuditPair(const Case& c, Flags& flags, bool& ok)
   {
      Rig rig;
      if (!rig.Init(c.create()))
      {
         printf("NOTEAUDIT SKIP %-18s no note outbox\n", c.name);
         return;
      }
      if (c.setup)
         c.setup(rig.node.get());
      rig.node->CookIfNeeded(rig.frame++);
      StartTransport(120.0);
      const double total = c.source ? 4.0 : 4.0;
      while (rig.pos < (long long)(total * kRate))
      {
         if (!c.source)
            ScriptedStream(rig, (double)rig.pos / kRate);
         rig.Step();
      }
      if (c.source)
      {
         StopTransport();
         // A stopped transport must close what it opened: run another second
         // with the transport frozen.
         rig.Run(1.0);
      }
      else
      {
         rig.Run(3.0); // tails: echo repeats, gate hold, strum, glide
         StopTransport();
      }
      const PairReport p = Pairs(rig.got);
      printf("NOTEAUDIT PAIR  %-18s on %3d off %3d | stuck %d orphan-off %d dup-on %d off-before-on %d\n", c.name, p.ons,
             p.offs, p.stuck, p.orphanOff, p.dupOn, p.offBeforeOn);
      if (p.ons == 0)
         printf("NOTEAUDIT NOTE  %-18s produced no notes in this scenario\n", c.name);
      if (p.Bad())
      {
         flags.Flag("PAIR", c.name, "unpaired events", p.stuck + p.orphanOff + p.dupOn + p.offBeforeOn);
         if (p.stuck)
            ok = false;
      }
   }

   // ---- GRID / SWING -----------------------------------------------------
   struct GridSrc
   {
      const char* name;
      std::function<INode*(double rateBeats, float groove)> create;
      bool needsInput; // arp: hold note 60
   };

   const std::vector<GridSrc>& GridSrcs()
   {
      static const std::vector<GridSrc> g = {
         { "Arpeggiator", [](double rb, float) {
              auto* a = static_cast<ArpeggiatorNode*>(ArpeggiatorNode::Create());
              a->rateBeats = (float)rb;
              a->octaves = 1;
              return (INode*)a;
           }, true },
         { "Note Sequencer", [](double rb, float) {
              auto* s = static_cast<NoteSequencerNode*>(NoteSequencerNode::Create());
              s->rateBeats = (float)rb;
              return (INode*)s;
           }, false },
         { "Random Note Gen", [](double rb, float groove) {
              auto* g2 = static_cast<RandomNoteGeneratorNode*>(RandomNoteGeneratorNode::Create());
              g2->rateBeats = (float)rb;
              g2->groove = groove;
              g2->useGlobalScale = false;
              return (INode*)g2;
           }, false },
      };
      return g;
   }

   // Runs a source and returns its note-on sample positions.
   std::vector<long long> OnPositions(const GridSrc& g, double bpm, int block, double rateBeats, float groove, double seconds)
   {
      Rig rig;
      std::vector<long long> pos;
      if (!rig.Init(g.create(rateBeats, groove), block))
         return pos;
      rig.node->CookIfNeeded(rig.frame++);
      StartTransport(bpm);
      if (g.needsInput)
         Push(rig.in[0], 60, 0.8f, true, 777);
      rig.Run(seconds);
      StopTransport();
      for (const Evt& e : rig.got)
         if (e.e.isNoteOn && !e.e.bendUpdate)
            pos.push_back(e.sample);
      return pos;
   }

   void AuditGrid(Flags& flags)
   {
      const double tempos[5] = { 60.0, 90.0, 120.0, 128.0, 174.0 };
      const int blocks[5] = { 64, 512, 800, 333, 2048 };
      const double rateBeats = 0.25;
      for (const GridSrc& g : GridSrcs())
      {
         double worst = 0.0;
         double worstBpm = 0, worstBlock = 0;
         int perBlock[5] = {};
         for (double bpm : tempos)
            for (int bi = 0; bi < 5; bi++)
            {
               const std::vector<long long> p = OnPositions(g, bpm, blocks[bi], rateBeats, 0.0f, 6.0);
               const double stepSamples = rateBeats * 60.0 / bpm * kRate;
               double maxErr = 0.0;
               for (size_t i = 0; i < p.size(); i++)
               {
                  const double k = std::round((double)p[i] / stepSamples);
                  maxErr = std::max(maxErr, std::fabs((double)p[i] - k * stepSamples));
               }
               if (p.empty())
                  maxErr = -1.0;
               perBlock[bi] = (int)std::lround(std::max(maxErr, 0.0));
               if (maxErr > worst)
               {
                  worst = maxErr;
                  worstBpm = bpm;
                  worstBlock = blocks[bi];
               }
            }
         printf("NOTEAUDIT GRID  %-18s worst %7.1f samples (%.0f bpm, block %.0f) | by block 64/512/800/333/2048: %d %d %d %d %d\n",
                g.name, worst, worstBpm, worstBlock, perBlock[0], perBlock[1], perBlock[2], perBlock[3], perBlock[4]);
         if (worst > kFlagGridSamples)
            flags.Flag("GRID", g.name, "worst note-on error samples", worst);
      }
   }

   void AuditSwing(Flags& flags)
   {
      const GridSrc& g = GridSrcs()[2];
      const double bpm = 120.0, rateBeats = 0.25;
      const double stepSamples = rateBeats * 60.0 / bpm * kRate;
      for (float groove : { 0.5f, 1.0f })
      {
         const std::vector<long long> p = OnPositions(g, bpm, 512, rateBeats, groove, 6.0);
         double oddSum = 0.0, evenSum = 0.0;
         int oddN = 0, evenN = 0;
         for (long long s : p)
         {
            const long long k = (long long)std::round((double)s / stepSamples);
            const double d = (double)s - (double)k * stepSamples;
            if (k & 1) { oddSum += d; oddN++; }
            else { evenSum += d; evenN++; }
         }
         if (oddN == 0)
         {
            printf("NOTEAUDIT SWING %-18s groove %.1f no odd steps\n", g.name, groove);
            continue;
         }
         const double expected = (double)groove * 0.5 * stepSamples;
         const double got = oddSum / oddN - (evenN ? evenSum / evenN : 0.0);
         const double errPct = std::fabs(got - expected) / stepSamples * 100.0;
         printf("NOTEAUDIT SWING %-18s groove %.1f odd-step delay %8.1f samples, expected %8.1f (%.2f %% of a step off)\n", g.name,
                groove, got, expected, errPct);
         if (errPct > kFlagSwingPct)
            flags.Flag("SWING", g.name, "swing error % of step", errPct);
      }
   }

   // ---- HUMAN ------------------------------------------------------------
   std::vector<long long> HumanRun(float timingMs, bool* withinKnob, double* maxDevMs)
   {
      auto* h = static_cast<HumanizerNode*>(HumanizerNode::Create());
      h->timingMs = timingMs;
      Rig rig;
      std::vector<long long> res;
      if (!rig.Init(h))
         return res;
      rig.node->CookIfNeeded(rig.frame++);
      StartTransport(120.0);
      std::vector<long long> inPos;
      for (int i = 0; i < 20; i++)
      {
         const long long at = (long long)(0.1 * kRate) + (long long)i * (long long)(0.2 * kRate);
         inPos.push_back(at);
      }
      int next = 0;
      while (rig.pos < (long long)(6.0 * kRate))
      {
         while (next < (int)inPos.size() && inPos[next] < rig.pos + rig.block)
         {
            Push(rig.in[0], 60 + next, 0.8f, true, 5000 + next, (int)(inPos[next] - rig.pos));
            Push(rig.in[0], 60 + next, 0.0f, false, 5000 + next, (int)(inPos[next] - rig.pos));
            next++;
         }
         rig.Step();
      }
      StopTransport();
      double maxDev = 0.0;
      for (const Evt& e : rig.got)
      {
         if (!e.e.isNoteOn)
            continue;
         res.push_back(e.sample);
         const int idx = e.e.voiceId - 5000;
         if (idx >= 0 && idx < (int)inPos.size())
            maxDev = std::max(maxDev, std::fabs((double)(e.sample - inPos[idx])) / kRate * 1000.0);
      }
      if (maxDevMs)
         *maxDevMs = maxDev;
      if (withinKnob)
         *withinKnob = maxDev <= (double)timingMs * 1.01 + 1.0;
      return res;
   }

   void AuditHuman(Flags& flags)
   {
      bool within = false;
      double dev = 0.0;
      const std::vector<long long> a = HumanRun(30.0f, &within, &dev);
      const std::vector<long long> b = HumanRun(30.0f, nullptr, nullptr);
      printf("NOTEAUDIT HUMAN Humanizer          timing 30 ms: max deviation %.2f ms (%s), %zu notes\n", dev,
             within ? "within knob" : "OUTSIDE knob", a.size());
      if (!within)
         flags.Flag("HUMAN", "Humanizer", "deviation ms beyond knob", dev);
      const bool same = a == b;
      printf("NOTEAUDIT HUMAN Humanizer          two fresh nodes, same stream: %s\n", same ? "identical" : "different");
      if (!same)
         flags.Flag("HUMAN", "Humanizer", "run-to-run difference (unseeded)", 1.0);
   }

   // ---- LOOP -------------------------------------------------------------
   void AuditLoop(Flags& flags, bool& ok)
   {
      for (const GridSrc& g : GridSrcs())
      {
         Rig rig;
         if (!rig.Init(g.create(0.25, 0.0f), 512))
            continue;
         rig.node->CookIfNeeded(rig.frame++);
         StartTransport(120.0);
         if (g.needsInput)
            Push(rig.in[0], 60, 0.8f, true, 777);
         Transport::Instance().SetLoop(true, 0.0, 3.0); // 1.5 s lap
         rig.Run(5.0);
         Transport::Instance().Seek(0.7);
         rig.Run(1.0);
         Transport::Instance().SetLoop(false, 0.0, 3.0);
         StopTransport();
         rig.Run(1.0);
         const PairReport p = Pairs(rig.got);
         printf("NOTEAUDIT LOOP  %-18s on %3d off %3d | stuck %d orphan-off %d dup-on %d off-before-on %d\n", g.name, p.ons,
                p.offs, p.stuck, p.orphanOff, p.dupOn, p.offBeforeOn);
         if (p.Bad())
         {
            flags.Flag("LOOP", g.name, "unpaired events across loop/seek/stop", p.stuck + p.orphanOff + p.dupOn + p.offBeforeOn);
            if (p.stuck)
               ok = false;
         }
      }
   }

   // ---- CPU --------------------------------------------------------------
   void AuditCpu()
   {
      for (const Case& c : Cases())
      {
         Rig rig;
         if (!rig.Init(c.create()))
            continue;
         if (c.setup)
            c.setup(rig.node.get());
         rig.node->CookIfNeeded(rig.frame++);
         StartTransport(120.0);
         for (int i = 0; i < 4; i++)
            Push(rig.in[0], 60 + i * 4, 0.8f, true, 9100 + i);
         rig.Run(0.5);
         const auto t0 = std::chrono::steady_clock::now();
         const int blocks = 400;
         for (int i = 0; i < blocks; i++)
            rig.Step();
         const auto t1 = std::chrono::steady_clock::now();
         StopTransport();
         const double ns = std::chrono::duration<double, std::nano>(t1 - t0).count() / blocks;
         printf("NOTEAUDIT CPU   %-18s %8.0f ns per 512-frame block\n", c.name, ns);
      }
   }
} // namespace

bool RunNoteAudit()
{
   setvbuf(stdout, nullptr, _IONBF, 0);
   const char* only = getenv("INFINITE_NOTEAUDIT_ONLY");
   auto want = [&](const char* sec) { return only == nullptr || *only == 0 || strstr(only, sec) != nullptr; };
   Flags flags;
   bool ok = true;

   if (want("PAIR"))
      for (const Case& c : Cases())
         AuditPair(c, flags, ok);
   if (want("GRID"))
      AuditGrid(flags);
   if (want("SWING"))
      AuditSwing(flags);
   if (want("HUMAN"))
      AuditHuman(flags);
   if (want("LOOP"))
      AuditLoop(flags, ok);
   if (want("CPU"))
      AuditCpu();

   printf("NOTEAUDIT %s (%d flags)\n", ok ? "PASS" : "FAIL", flags.n);
   return ok;
}

} // namespace app
