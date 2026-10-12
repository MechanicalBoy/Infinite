#!/usr/bin/env python3
"""re-survey load_bench: how many tracks of synth + effect Infinite renders before it runs out of time.

Block B step 1 of docs/plans/re-survey/coverage.md (performance under load). Builds an N-track patch (one
Keyboard fanned out to N synths, each through one effect, summed by a tree of Mixers into Audio Out), plays
the same held 4-note chords on every track, and renders it offline twice (short and long) so load time
cancels. The slope is the audio-thread cost per second of audio: Infinite renders its graph on one thread,
so 100 % means one core is full and a live device would drop out (in practice earlier, near 70-80 %).

The same stimulus as a standard MIDI file (`midi`) plus PROTOCOL-load.md let the owner build the matching
template in Live, Logic and Bitwig; `app_bench.py` records their CPU while it plays.

Usage:
  python3 tools/re-survey/load_bench.py run [--tracks 8,32,64,128] [--track node:Wavetable+node:Reverb]
                                            [--track "au:aumu:...+Pro-Q 4"] [--out t.md]
  python3 tools/re-survey/load_bench.py midi out.mid [--seconds 30]
  python3 tools/re-survey/load_bench.py --self-test
Exit: 0 ok, 1 a render failed / self-test failed, 2 usage error or no Infinite build.
"""

import argparse
import json
import os
import struct
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402

SR = 48000
BPM = 120.0
CHORDS = [(48, 55, 60, 64), (45, 52, 57, 60), (41, 48, 53, 57), (43, 50, 55, 59)]  # C, Am, F, G
BAR = 4 * 60.0 / BPM
DEFAULT_TRACK = "node:Wavetable+node:Reverb"


def events(seconds):
    """One chord per bar, held 90 % of the bar: (t, pitch, velocity, length)."""
    ev, t, i = [], 0.0, 0
    while t + BAR <= seconds + 1e-9:
        for p in CHORDS[i % len(CHORDS)]:
            ev.append((round(t, 6), p, 0.8, BAR * 0.9))
        t += BAR
        i += 1
    return ev


TRACKS_PER_KEYBOARD = 8  # released builds feed at most 8 nodes from one note output (64 from 2026-10-12)


def keyboard_id(k):
    return "keys" if k == 0 else "keys%d" % k


def write_notes(ev, d, keyboards=1):
    """Every event goes to every Keyboard; event type p<pitch>k<keyboard>."""
    pitches = sorted({p for (_, p, _, _) in ev})
    types = {"p%dk%d" % (p, k): {"node": keyboard_id(k), "pitch": p, "velocity_from": "v", "length_from": "len"}
             for p in pitches for k in range(keyboards)}
    ep, mp = os.path.join(d, "events.json"), os.path.join(d, "map.json")
    with open(ep, "w") as f:
        json.dump([{"t": t, "type": "p%dk%d" % (p, k), "v": v, "len": ln} for (t, p, v, ln) in ev for k in range(keyboards)], f)
    with open(mp, "w") as f:
        json.dump(types, f)
    return ep, mp


def parse_track(spec):
    """'node:Wavetable+node:Reverb' or 'au:aumu:xxxx:yyyy+Pro-Q 4' -> (synth, effect) dicts."""
    parts = spec.split("+")
    if len(parts) != 2:
        raise ValueError("a track is synth+effect: %r" % spec)
    out = []
    aus = None
    for i, p in enumerate(parts):
        p = p.strip()
        if p.startswith("node:"):
            out.append({"kind": "node", "type": p[5:]})
            continue
        if aus is None:
            aus = pp.list_aus()
        if i == 0:
            import synth_probe as sp
            out.append(sp.resolve(p, aus))
        else:
            out.append(pp.resolve(p, aus))
    return out


NODE_CATEGORY = {"Wavetable": "Synths", "Analog": "Synths", "Oscillator": "Synths", "Metallic": "Synths",
                 "Reverb": "AudioEffects", "Delay": "AudioEffects", "EQ": "AudioEffects", "Chorus": "AudioEffects",
                 "Drive": "AudioEffects", "Dynamics": "AudioEffects", "Audio Filter": "AudioEffects"}


def node_lines(idx, nid, t, notes):
    if t["kind"] == "node":
        return ["node %d %s %s" % (idx, NODE_CATEGORY.get(t["type"], "AudioEffects"), t["type"]), "  id " + nid, "end"]
    L = ["node %d AudioEffects Plugin" % idx, "  id " + nid, "  s plugin_format " + t["kind"], "  s plugin_id " + t["id"],
         "  s plugin_name " + t.get("name", t.get("label", t["id"]))]
    if notes:
        L.append("  b plugin_accepts_notes 1")
    return L + ["end"]


def keyboards_for(n):
    return max(1, (n + TRACKS_PER_KEYBOARD - 1) // TRACKS_PER_KEYBOARD)


def patch_text(n, synth, fx):
    """N tracks -> Mixer tree (8 inputs each) -> Audio Out. One Keyboard per 8 tracks."""
    L = ["infinite-patch 1"]
    idx = 1
    for k in range(keyboards_for(n)):
        L += ["node %d Notes Keyboard" % idx, "  id " + keyboard_id(k), "end"]
        idx += 1
    wires = []
    level = []
    for k in range(n):
        L += node_lines(idx, "s%d" % k, synth, True)
        L += node_lines(idx + 1, "f%d" % k, fx, False)
        wires += ["note s%d %d %s" % (k, 1 if synth["kind"] != "node" else 0, keyboard_id(k // TRACKS_PER_KEYBOARD)), "aud f%d %s s%d" % (k, "in" if fx["kind"] != "node" else "audio", k)]
        level.append("f%d" % k)
        idx += 2
    m = 0
    while len(level) > 1:
        nxt = []
        for g in range(0, len(level), 8):
            mid = "m%d" % m
            m += 1
            L += ["node %d Utility Mixer" % idx, "  id " + mid, "end"]
            idx += 1
            for j, src in enumerate(level[g:g + 8]):
                wires.append("aud %s in_%d %s" % (mid, j + 1, src))
            nxt.append(mid)
        level = nxt
    L += ["node %d Utility Audio Out" % idx, "  id out", "end"]
    wires.append("aud out audio %s" % level[0])
    return "\n".join(L + wires) + "\n"


def render_time(binp, patch, seconds, tmp):
    ev = events(seconds)
    nk = patch.count("Notes Keyboard")
    ep, mp = write_notes(ev, tmp, nk)
    wav = os.path.join(tmp, "out.wav")
    t0 = time.time()
    st = pp.render(binp, patch, wav, SR, seconds, tmp, ["--notes", ep, "--note-map", mp, "--bpm", "%g" % BPM])
    wall = time.time() - t0
    if st.get("notes", {}).get("injected") != len(ev) * nk:
        raise RuntimeError("only %s of %d notes injected" % (st.get("notes", {}).get("injected"), len(ev) * nk))
    bad = [p.get("name") for p in st.get("plugins") or [] if not p.get("ready")]
    if bad:
        raise RuntimeError("plugins did not load: %s" % ", ".join(map(str, bad[:3])))
    a, _, _ = pp.read_wav(wav)
    return wall, float(abs(a).max()) if len(a) else 0.0


def measure(binp, n, synth, fx, short=4.0, long=24.0):
    tmp = tempfile.mkdtemp(prefix="re-load-", dir=ensure_dir(os.path.join(RE_OUTPUT, "tmp")))
    patch = patch_text(n, synth, fx)
    ws, _ = render_time(binp, patch, short, tmp)
    wl, peak = render_time(binp, patch, long, tmp)
    load = max(0.0, (wl - ws) / (long - short))
    return {"tracks": n, "load_pct": load * 100.0, "per_track_ms_per_s": load * 1000.0 / n,
            "setup_s": max(0.0, ws - load * short), "peak": peak}


def to_markdown(label, rows):
    L = ["# Infinite load bench: %s" % label, "",
         "Generated by `tools/re-survey/load_bench.py`. Held 4-note chords on every track at %g BPM, 48 kHz, offline. "
         "Load = audio-thread time per second of audio (slope of a 4 s and a 24 s render). Infinite renders the graph "
         "on one thread: 100 %% is one full core; a live device starts dropping out before that." % BPM, ""]
    L.append(md_table(["Tracks", "Load % of one core", "ms per track per s", "Setup s", "Peak"],
                      [(r["tracks"], "%.1f" % r["load_pct"], "%.2f" % r["per_track_ms_per_s"], "%.2f" % r["setup_s"],
                        "%.3f" % r["peak"] if isinstance(r.get("peak"), (int, float)) else "-") for r in rows]))
    over = [r["tracks"] for r in rows if r["load_pct"] >= 70.0]
    est = rows[-1]["per_track_ms_per_s"] if rows else 0
    L += ["", "- Estimated ceiling at 70 %% of one core: about %d tracks." % (int(700.0 / est) if est > 0 else 0)]
    if over:
        L.append("- At or over 70 %%: %s tracks." % ", ".join(map(str, over)))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- MIDI for the DAW templates

def vlq(n):
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.insert(0, 0x80 | (n & 0x7F))
        n >>= 7
    return bytes(b)


def midi_bytes(seconds):
    """Type-0 SMF, 480 ppq, 120 BPM: the same chords as the Infinite stimulus."""
    ppq = 480
    tick = lambda s: int(round(s * BPM / 60.0 * ppq))
    msgs = []
    for (t, p, v, ln) in events(seconds):
        msgs.append((tick(t), 1, bytes([0x90, p, int(v * 127)])))
        msgs.append((tick(t + ln), 0, bytes([0x80, p, 0])))
    msgs.sort(key=lambda m: (m[0], m[1]))
    trk, last = bytearray(), 0
    trk += vlq(0) + b"\xff\x51\x03" + struct.pack(">I", int(60e6 / BPM))[1:]
    for (tk, _, m) in msgs:
        trk += vlq(tk - last) + m
        last = tk
    trk += vlq(0) + b"\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)


def self_test():
    t = SelfTest("load_bench")
    ev = events(8.0)
    t.check(len(ev) == 16 and ev[4][0] == BAR, "8 s at 120 BPM is 4 bars of 4-note chords")
    p = patch_text(9, {"kind": "node", "type": "Analog"}, {"kind": "node", "type": "Reverb"})
    t.check(p.count("Utility Mixer") == 3 and "aud out audio m2" in p and "aud m1 in_1 f8" in p,
            "9 tracks sum through 2 Mixers into a third")
    p = patch_text(128, {"kind": "node", "type": "Analog"}, {"kind": "node", "type": "Reverb"})
    t.check(p.count("Notes Keyboard") == 16 and "note s127 0 keys15" in p and "note s7 0 keys\n" in p,
            "128 tracks take 16 Keyboards, 8 synths each (a note output once fed at most 8)")
    mb = midi_bytes(8.0)
    t.check(mb[:4] == b"MThd" and mb.count(b"\x90") >= 16 and mb.endswith(b"\xff\x2f\x00"), "the MIDI file is well formed")
    binp = infinite_bin()
    if not binp:
        t.skip("no Infinite build: the render is not run")
        return t.done()
    a = measure(binp, 2, {"kind": "node", "type": "Analog"}, {"kind": "node", "type": "Reverb"}, short=2.0, long=6.0)
    t.check(a["peak"] and a["peak"] > 0.01, "2 tracks of Analog + Reverb make sound (peak %s)" % a["peak"])
    t.check(0.0 <= a["load_pct"] < 100.0, "the load is a sane fraction of a core (%.1f %%)" % a["load_pct"])
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("run")
    rp.add_argument("--tracks", default="8,32,64,128")
    rp.add_argument("--track", action="append")
    rp.add_argument("--out")
    mp = sub.add_parser("midi")
    mp.add_argument("path")
    mp.add_argument("--seconds", type=float, default=32.0)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "midi":
        with open(a.path, "wb") as f:
            f.write(midi_bytes(a.seconds))
        print("wrote %s" % a.path)
        return 0
    if a.cmd != "run":
        ap.print_usage(sys.stderr)
        return 2
    binp = infinite_bin()
    if not binp:
        return 2
    md, failed = [], False
    for spec in a.track or [DEFAULT_TRACK]:
        try:
            synth, fx = parse_track(spec)
        except ValueError as e:
            print("load_bench: %s" % e, file=sys.stderr)
            return 2
        rows = []
        for n in [int(x) for x in a.tracks.split(",")]:
            try:
                r = measure(binp, n, synth, fx)
            except RuntimeError as e:
                print("  %s x%d FAILED %s" % (spec, n, e), file=sys.stderr)
                failed = True
                break
            print("  %s x%-4d load %.1f %% of one core, %.2f ms/track/s" % (spec, n, r["load_pct"], r["per_track_ms_per_s"]),
                  file=sys.stderr)
            rows.append(r)
        md.append(to_markdown(spec, rows))
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "load-bench"))
    with open(os.path.join(out_dir, time.strftime("%Y%m%d-%H%M%S") + ".md"), "w") as f:
        f.write("\n".join(md))
    write_out("\n".join(md), a.out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
