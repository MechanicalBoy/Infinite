#!/usr/bin/env python3
"""re-survey workflow_cost: how many steps, and roughly how long, the ten most common tasks take per app.

Each task is a list of operations from the same starting point (a new, empty project; for tasks 2-10 the
instrument from task 1 is already there). The time is a Keystroke-Level Model estimate (Card, Moran and
Newell 1983, the published operator times below), not a stopwatch: it ranks the flows, and the owner's
timed sitting (docs/plans/re-survey/PROTOCOL-workflow.md) checks it against real hands.

Infinite's steps come from its code: every Infinite task cites `path::token` and `check` fails if a cited
token is no longer in that file, so the table cannot silently go stale. The other apps' steps come from
their public manuals (section named per task) and are confirmed in the sitting.

  table  -> steps, KLM seconds and Infinite's rank per task (markdown)
  check  -> every Infinite citation still resolves

Usage:
  python3 tools/re-survey/workflow_cost.py table [--out workflow.md]
  python3 tools/re-survey/workflow_cost.py check
  python3 tools/re-survey/workflow_cost.py --self-test
Exit: 0 ok, 1 failed, 2 usage error.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REPO, SelfTest, md_table, write_out  # noqa: E402

# KLM operator times in seconds (Card, Moran and Newell 1983).
K = 0.28   # one keystroke, average typist
P = 1.10   # point with the mouse
B = 0.10   # press or release a button
M = 1.35   # mental preparation before a new command
OP_COST = {
    "key": None,             # K per key in the chord ("Shift+N" = 2)
    "type": None,            # K per character
    "click": P + 2 * B,
    "dclick": P + 4 * B,
    "drag": 2 * (P + B),     # point, press, point, release
    "hover": P,
}

LIVE = "Live 12 Reference Manual, https://www.ableton.com/en/live-manual/12/"
LOGIC = "Logic Pro User Guide, https://support.apple.com/guide/logicpro/welcome/mac"
BITWIG = "Bitwig Studio User Guide, https://www.bitwig.com/userguide/latest/"

# task -> app -> (steps, source). A step is (op, what). Infinite's source is a list of `path::token`.
TASKS = [
    ("Add an instrument and hear a note", {
        "Infinite": ([("click", "Start Audio in the top bar (audio is off at launch)"), ("key", "Shift+N"),
                      ("type", "keyboard"), ("key", "Enter"),
                      ("drag", "Keyboard's out pin to empty canvas (opens the picker, wires the pick)"),
                      ("type", "field synth"), ("key", "Enter"), ("drag", "synth's out pin to empty canvas"),
                      ("type", "audio out"), ("key", "Enter"), ("hover", "over the Keyboard node"), ("key", "A")],
                     ["src/app/frame/StageMenuBar.cpp::Start Audio", "src/app/panels/HelpWindows.cpp::Open quick type-to-filter node picker",
                      "src/app/graph/Wiring.cpp::drag-to-empty-canvas auto-wire", "src/nodes/NoteNodes.h::computerKeyboardEnabled = true",
                      "src/app/bodies/NoteBodies.cpp::letter keys belong to this node"]),
        "Live": ([("click", "Instruments in the browser"), ("dclick", "an instrument (loads on the selected MIDI track, which arms)"),
                  ("key", "M (computer MIDI keyboard, if off)"), ("key", "A")],
                 LIVE + " - Working with Instruments and Effects; Computer MIDI Keyboard"),
        "Logic": ([("click", "Software Instrument in the new-track dialog"), ("click", "Create"),
                   ("key", "Cmd+K (Musical Typing)"), ("key", "A")],
                  LOGIC + " - Create tracks; Use Musical Typing"),
        "Bitwig": ([("click", "Instruments in the browser"), ("drag", "an instrument onto the instrument track"),
                    ("key", "A (computer keyboard plays the armed track)")],
                   BITWIG + " - Browser; Playing with the computer keyboard"),
    }),
    ("Load a third-party plugin", {
        "Infinite": ([("click", "Plugins tab of the side panel"), ("type", "valhalla"),
                      ("drag", "the plugin onto the synth-to-Audio-Out cable (splices it in)")],
                     ["src/app/panels/LibraryPanels.cpp::LibraryDragKind::Plugin",
                      "src/app/frame/StageLinks.cpp::drop a node on a cable to splice it in"]),
        "Live": ([("click", "Plugins in the browser"), ("type", "valhalla"), ("dclick", "the plugin (adds to the selected track)")],
                 LIVE + " - Working with Plug-ins"),
        "Logic": ([("click", "an empty Audio FX slot"), ("click", "Audio Units"), ("click", "the vendor"), ("click", "the plugin")],
                  LOGIC + " - Add, remove, move and copy plug-ins"),
        "Bitwig": ([("click", "the browser search"), ("type", "valhalla"), ("drag", "the plugin onto the device chain")],
                   BITWIG + " - Browser; Device chain"),
    }),
    ("Add a built-in effect", {
        "Infinite": ([("click", "Modules tab of the side panel"), ("type", "reverb"),
                      ("drag", "Reverb onto the synth-to-Audio-Out cable (splices it in)")],
                     ["src/app/frame/StageSidePanels.cpp::Add to canvas",
                      "src/app/frame/StageLinks.cpp::drop a node on a cable to splice it in"]),
        "Live": ([("click", "Audio Effects in the browser"), ("dclick", "Reverb")],
                 LIVE + " - Working with Instruments and Effects"),
        "Logic": ([("click", "an empty Audio FX slot"), ("click", "Reverb"), ("click", "ChromaVerb")],
                  LOGIC + " - Add, remove, move and copy plug-ins"),
        "Bitwig": ([("click", "the browser search"), ("type", "reverb"), ("drag", "Reverb onto the device chain")],
                   BITWIG + " - Browser; Device chain"),
    }),
    ("Automate a parameter", {
        "Infinite": ([("key", "Space (play)"), ("drag", "Shift+drag the knob; the move loops when Shift is released")],
                     ["src/core/GestureRecorder.h::Holding Shift while dragging a knob or slider"]),
        "Live": ([("key", "A (show automation)"), ("click", "the parameter chooser"), ("click", "the parameter"),
                  ("key", "B (draw mode)"), ("drag", "draw the envelope")],
                 LIVE + " - Automation and Editing Envelopes"),
        "Logic": ([("key", "A (show automation)"), ("click", "the parameter menu"), ("click", "the parameter"),
                   ("click", "add a point"), ("drag", "move the point")],
                  LOGIC + " - Automation overview; Add automation points"),
        "Bitwig": ([("key", "A (show automation)"), ("click", "the parameter in the inspector"), ("dclick", "add a point"),
                    ("drag", "move the point")],
                   BITWIG + " - Automation"),
    }),
    ("Modulate a parameter with an LFO", {
        "Infinite": ([("key", "Shift+N"), ("type", "lfo"), ("key", "Enter"), ("drag", "LFO's out pin onto the cutoff's param pin")],
                     ["src/app/panels/HelpWindows.cpp::Open quick type-to-filter node picker",
                      "src/app/ui/design/components/PinDot.h::Param"]),
        "Live": ([("click", "Max for Live in the browser"), ("dclick", "LFO"), ("click", "Map"), ("click", "the cutoff knob")],
                 LIVE + " - Max for Live; Modulators"),
        "Logic": ([("click", "an empty MIDI FX slot"), ("click", "Modulator"), ("click", "Learn"), ("drag", "move the cutoff knob")],
                  LOGIC + " - Modulator MIDI plug-in"),
        "Bitwig": ([("click", "the device's modulator +"), ("click", "LFO"), ("click", "the modulator's routing button"),
                    ("drag", "drag on the cutoff knob")],
                   BITWIG + " - Modulators"),
    }),
    ("Enter four MIDI notes", {
        "Infinite": ([("key", "Shift+N"), ("type", "note sequencer"), ("key", "Enter"),
                      ("drag", "sequencer's out pin onto the synth's note input"),
                      ("click", "step 1"), ("click", "step 2"), ("click", "step 3"), ("click", "step 4")],
                     ["src/app/panels/HelpWindows.cpp::A self-playing step sequencer"]),
        "Live": ([("dclick", "an empty clip slot (makes a clip)"), ("key", "B (draw mode)"),
                  ("click", "note 1"), ("click", "note 2"), ("click", "note 3"), ("click", "note 4")],
                 LIVE + " - Editing MIDI"),
        "Logic": ([("key", "Cmd+click the track (makes a region)"), ("key", "P (Piano Roll)"),
                   ("click", "Cmd+click note 1"), ("click", "note 2"), ("click", "note 3"), ("click", "note 4")],
                  LOGIC + " - Piano Roll Editor; Create notes"),
        "Bitwig": ([("dclick", "an empty clip slot"), ("dclick", "note 1"), ("dclick", "note 2"), ("dclick", "note 3"),
                    ("dclick", "note 4")],
                   BITWIG + " - Note editing"),
    }),
    ("Change the tempo", {
        "Infinite": ([("dclick", "the tempo in the top bar"), ("type", "128"), ("key", "Enter")],
                     ["src/app/frame/StageMenuBar.cpp::TopBarField { None, Bpm"]),
        "Live": ([("dclick", "the tempo field"), ("type", "128"), ("key", "Enter")], LIVE + " - Tempo control"),
        "Logic": ([("dclick", "the tempo in the LCD"), ("type", "128"), ("key", "Enter")], LOGIC + " - Tempo"),
        "Bitwig": ([("dclick", "the tempo field"), ("type", "128"), ("key", "Enter")], BITWIG + " - Transport"),
    }),
    ("Import a sample", {
        "Infinite": ([("drag", "the file from Finder onto the canvas"), ("click", "Sampler in the drop picker"),
                      ("drag", "Sampler's out pin onto Audio Out")],
                     ["src/app/frame/StageDropHandling.cpp::pendingAudioDropPaths"]),
        "Live": ([("drag", "the file from Finder onto an audio track")], LIVE + " - Managing Files and Sets"),
        "Logic": ([("drag", "the file from Finder into the Tracks area")], LOGIC + " - Add audio files"),
        "Bitwig": ([("drag", "the file from Finder onto a track")], BITWIG + " - Importing audio"),
    }),
    ("Save the project (first time)", {
        "Infinite": ([("key", "Cmd+S"), ("type", "song"), ("key", "Enter")],
                     ["src/app/panels/HelpWindows.cpp::Save current patch"]),
        "Live": ([("key", "Cmd+S"), ("type", "song"), ("key", "Enter")], LIVE + " - Managing Files and Sets"),
        "Logic": ([("key", "Cmd+S"), ("type", "song"), ("key", "Enter")], LOGIC + " - Save projects"),
        "Bitwig": ([("key", "Cmd+S"), ("type", "song"), ("key", "Enter")], BITWIG + " - Saving projects"),
    }),
    ("Export audio or video", {
        "Infinite": ([("click", "Render on the Output node (writes to the folder in its params, Desktop by default)")],
                     ["src/app/frame/StageNodeBodies.cpp::StartOfflineRenderSession(n)",
                      "src/app/panels/ArrangeRender.cpp::the default (Desktop)"]),
        "Live": ([("key", "Cmd+Shift+R"), ("click", "Export"), ("type", "song"), ("key", "Enter")],
                 LIVE + " - Exporting Audio and Video"),
        "Logic": ([("key", "Cmd+B (Bounce)"), ("click", "OK"), ("type", "song"), ("key", "Enter")],
                  LOGIC + " - Bounce projects"),
        "Bitwig": ([("key", "Cmd+Shift+R (Export Audio)"), ("click", "OK"), ("type", "song"), ("key", "Enter")],
                   BITWIG + " - Exporting audio"),
    }),
]
APPS = ["Infinite", "Live", "Logic", "Bitwig"]


def klm(steps):
    """Seconds for a step list: operator times plus one M before every new command (not before
    typing, nor before the Enter that ends what was typed)."""
    total, prev = 0.0, None
    for op, what in steps:
        if op not in OP_COST:
            raise ValueError("unknown op %r" % op)
        if op == "key":
            chord = what.split(" ")[0]
            cost = K * len(chord.split("+"))
        elif op == "type":
            cost = K * len(what)
        else:
            cost = OP_COST[op]
        if op != "type" and not (op == "key" and what.startswith("Enter") and prev == "type"):
            cost += M
        total += cost
        prev = op
    return total


def check_cites():
    """[(task, cite, ok)] for every Infinite citation."""
    out = []
    for task, apps in TASKS:
        for cite in apps["Infinite"][1]:
            path, token = cite.split("::", 1)
            full = os.path.join(REPO, path)
            ok = os.path.exists(full) and token in open(full, encoding="utf-8", errors="replace").read()
            out.append((task, cite, ok))
    return out


def table():
    rows, ranks = [], []
    for i, (task, apps) in enumerate(TASKS, 1):
        cells = [i, task]
        secs = {}
        for app in APPS:
            steps = apps[app][0]
            secs[app] = klm(steps)
            cells.append("%d / %.1f s" % (len(steps), secs[app]))
        rank = 1 + sum(1 for a in APPS if secs[a] < secs["Infinite"] - 0.05)
        ranks.append(rank)
        cells.append("%d of %d" % (rank, len(APPS)))
        rows.append(cells)
    tot = {a: sum(klm(apps[a][0]) for _, apps in TASKS) for a in APPS}
    rows.append(["", "**All ten**"] + ["%d / %.1f s" % (sum(len(apps[a][0]) for _, apps in TASKS), tot[a]) for a in APPS] + [""])
    out = ["# Workflow cost: ten common tasks", "",
           "Steps / Keystroke-Level Model seconds (K %.2f, P %.2f, B %.2f, M %.2f). Start: a new empty project; tasks 2-10 "
           "build on task 1. Infinite steps cite its code (`workflow_cost.py check`); the others follow their manuals and "
           "are confirmed in the timed sitting (PROTOCOL-workflow.md)." % (K, P, B, M), "",
           md_table(["#", "Task"] + APPS + ["Infinite rank"], rows), "", "## Steps", ""]
    for i, (task, apps) in enumerate(TASKS, 1):
        out.append("### %d. %s" % (i, task))
        out.append("")
        for app in APPS:
            steps, src = apps[app]
            out.append("- **%s**: %s. Source: %s" % (app, "; ".join("%s %s" % s for s in steps),
                                                    ", ".join("`%s`" % c for c in src) if isinstance(src, list) else src))
        out.append("")
    return "\n".join(out)


def self_test():
    t = SelfTest("workflow_cost")
    t.check(abs(klm([("click", "x")]) - (P + 2 * B + M)) < 1e-9, "a click costs point + press/release + M")
    t.check(abs(klm([("key", "Shift+N")]) - (2 * K + M)) < 1e-9, "a chord costs K per key")
    t.check(abs(klm([("type", "abc"), ("key", "Enter")]) - (4 * K)) < 1e-9, "typing and its Enter carry no M")
    t.check(all(set(apps) == set(APPS) for _, apps in TASKS), "every task covers every app")
    t.check(len(TASKS) == 10, "ten tasks")
    t.check(all(isinstance(apps["Infinite"][1], list) and apps["Infinite"][1] for _, apps in TASKS),
            "every Infinite task cites code")
    bad = [c for _, c, ok in check_cites() if not ok]
    t.check(not bad, "every Infinite citation resolves%s" % (" (missing: %s)" % ", ".join(bad) if bad else ""))
    t.check("| 1 | Add an instrument" in table(), "table renders")
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["table", "check"])
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "table":
        write_out(table(), a.out)
        return 0
    if a.cmd == "check":
        res = check_cites()
        for task, cite, ok in res:
            print("%s  %s  (%s)" % ("ok  " if ok else "GONE", cite, task))
        return 0 if all(ok for _, _, ok in res) else 1
    ap.print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
