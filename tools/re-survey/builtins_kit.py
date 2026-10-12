#!/usr/bin/env python3
"""re-survey builtins_kit: each DAW's built-in instruments and effects, measured from the DAW's own bounces.

synth_probe and plugin_probe measure anything Infinite can host. A DAW's built-ins (Live's Wavetable, Logic's
ChromaVerb, Bitwig's Polymer) only run inside their DAW, so here the DAW plays the same stimuli and bounces,
and the same numbers come out of the WAVs:

  synth.mid    synth_probe's note script at 120 BPM (pitch MIDI 24-108, velocity 0.25/0.5/1, a 1 s envelope note)
  fxstim.wav   plugin_probe's stimulus (impulse at 1 s, 1 kHz at -12 and -1 dBFS, a 15 kHz alias probe)

Bounces go into one folder per DAW as synth_<Name>.wav / fx_<Name>.wav (synth_Wavetable.wav, fx_Reverb.wav).
`infinite` renders Infinite's own synth and effect nodes the same way into one folder.

Usage:
  python3 tools/re-survey/builtins_kit.py make [--dir ~/re-output/builtins-kit/kit]
  python3 tools/re-survey/builtins_kit.py infinite [--dir ~/re-output/builtins-kit/Infinite]
  python3 tools/re-survey/builtins_kit.py analyse ~/re-output/builtins-kit/Infinite ~/re-output/builtins-kit/Live ... [--out t.md]
  python3 tools/re-survey/builtins_kit.py --self-test
Limits: each built-in plays its default patch, so the tables compare behaviour (tuning, aliasing, envelope,
latency, tail), not sound design. No CPU column: a bounce does not say what it cost.
Exit: 0 ok, 1 a render failed / a folder has no bounces / self-test failed, 2 usage error.
"""

import argparse
import glob
import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, write_out  # noqa: E402
import bounce_kit as bk  # noqa: E402
import plugin_probe as pp  # noqa: E402
import synth_probe as sp  # noqa: E402

SR = 48000
KIT = os.path.join(RE_OUTPUT, "builtins-kit", "kit")
BPM = 120.0
SYNTHS = ["Analog", "Wavetable", "Oscillator", "Metallic", "Equation Synth", "Field Synth"]
EFFECTS = ["Reverb", "Delay", "Chorus", "Flanger", "Phaser", "EQ", "Drive", "Dynamics", "Limiter", "Audio Filter"]


def synth_len():
    return sp.script()[1]


def midi_events():
    """synth_probe's script as SMF notes: (tick, len_ticks, pitch, vel 1-127) at 120 BPM."""
    tps = BPM / 60.0 * bk.PPQ
    return [(int(round(t * tps)), int(round(ln * tps)), m, max(1, min(127, int(round(v * 127)))))
            for (t, m, v, ln, _) in sp.script()[0]]


PROTOCOL = """# Built-ins kit protocol

One project per DAW: 48 kHz, 120 BPM, 4/4, master with no effects, fader at 0 dB. Every bounce is a 48 kHz
24-bit stereo WAV from bar 1, no normalise, no dither, into one folder per DAW (`Live`, `Logic`, `Bitwig`).

## Instruments: synth_<Name>.wav, {synth:g} s each

1. Drop synth.mid at bar 1 on a MIDI track. Load the instrument with its default / init patch (no preset).
2. Bounce {synth:g} s. Name it synth_<Name>.wav with the instrument's name (spaces removed).

## Effects: fx_<Name>.wav, {fx:g} s each

1. Drop fxstim.wav at bar 1 on an audio track. Load the effect at its default, mix as it opens.
2. Bounce {fx:g} s. Name it fx_<Name>.wav. Also bounce the track with no effect as fx_Dry.wav (the rig floor).

## Which built-ins

| DAW | Instruments | Effects |
|---|---|---|
| Live | Wavetable, Operator, Drift, Analog | Reverb, Hybrid Reverb, Echo, Delay, Chorus-Ensemble, Phaser-Flanger, EQ Eight, Saturator, Roar, Compressor, Glue Compressor, Limiter, Auto Filter |
| Logic | Alchemy, ES2, Retro Synth, Sculpture | ChromaVerb, Space Designer, Tape Delay, Chorus, Phaser, Channel EQ, Overdrive, Compressor, Limiter, AutoFilter |
| Bitwig | Polymer, Phase-4, FM-4, Polysynth | Reverb, Delay-2, Chorus+, Phaser+, EQ+, Distortion, Compressor+, Peak Limiter, Filter+ |

Write down any default that is not neutral (an effect that opens 50 % wet, an instrument that opens a fifth up).
Then: `python3 tools/re-survey/builtins_kit.py analyse <folder> [<folder> ...]`.
"""


def make(d):
    ensure_dir(d)
    with open(os.path.join(d, "synth.mid"), "wb") as f:
        f.write(bk.smf(midi_events(), [(0, BPM)]))
    pp.write_wav24(os.path.join(d, "fxstim.wav"), pp.make_stimulus(SR), SR)
    with open(os.path.join(d, "PROTOCOL.md"), "w") as f:
        f.write(PROTOCOL.format(synth=synth_len(), fx=pp.TOTAL_S))
    return d


def fname(kind, name):
    return "%s_%s.wav" % (kind, name.replace(" ", ""))


# ---------------------------------------------------------------- Infinite

def render_infinite(out_dir, binp=None, log=print):
    binp = binp or infinite_bin()
    ensure_dir(out_dir)
    tmp = tempfile.mkdtemp(prefix="re-builtins-", dir=ensure_dir(os.path.join(RE_OUTPUT, "tmp")))
    fails = 0
    try:
        events, dur = sp.script()
        for typ in SYNTHS:
            try:
                cat = pp.node_category(binp, typ, tmp)
                sp.render(binp, {"kind": "node", "type": typ, "label": typ}, cat, events, dur,
                          os.path.join(out_dir, fname("synth", typ)), tmp)
                log("  synth %-14s ok" % typ)
            except Exception as e:  # one bad node must not stop the rest
                fails += 1
                log("  synth %-14s FAILED %s" % (typ, e))
        stim = os.path.join(tmp, "fxstim.wav")
        pp.write_wav24(stim, pp.make_stimulus(SR), SR)
        for typ in ["Dry"] + EFFECTS:
            try:
                t = {"kind": "dry"} if typ == "Dry" else {"kind": "node", "type": typ, "label": typ}
                cat = None if typ == "Dry" else pp.node_category(binp, typ, tmp)
                pp.render(binp, pp.patch_text(t, stim, False, cat), os.path.join(out_dir, fname("fx", typ)), SR, pp.TOTAL_S, tmp)
                log("  fx    %-14s ok" % typ)
            except Exception as e:
                fails += 1
                log("  fx    %-14s FAILED %s" % (typ, e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


# ---------------------------------------------------------------- analysis

def name_of(path, kind):
    return os.path.basename(path)[len(kind) + 1:-4]


def analyse_dir(d):
    app = os.path.basename(os.path.normpath(d))
    events, _ = sp.script()
    stim = pp.make_stimulus(SR)
    synths, fx = [], []
    for p in sorted(glob.glob(os.path.join(d, "synth_*.wav"))):
        out, sr, bits = pp.read_wav(p)
        row = {"app": app, "name": name_of(p, "synth"), "bits": bits, "sr": sr}
        row.update(sp.analyse(out if out.shape[1] > 1 else np.repeat(out, 2, 1), sr, events) if sr == SR else {"error": "%d Hz" % sr})
        synths.append(row)
    for p in sorted(glob.glob(os.path.join(d, "fx_*.wav"))):
        out, sr, bits = pp.read_wav(p)
        row = {"app": app, "name": name_of(p, "fx"), "bits": bits, "sr": sr}
        row.update(pp.analyse(out if out.shape[1] > 1 else np.repeat(out, 2, 1), sr, stim) if sr == SR else {"error": "%d Hz" % sr})
        fx.append(row)
    return {"app": app, "synths": synths, "fx": fx}


def fv(v, s="%.1f"):
    return "-" if v is None else s % v


def report(rows):
    L = ["# Built-ins kit results", "",
         "Generated by `tools/re-survey/builtins_kit.py`. Each DAW's built-ins at their default patch, measured "
         "from the DAW's own 48 kHz bounces; Infinite's nodes rendered headless with the same stimuli.", ""]
    T = []
    for row in rows:
        for r in row["synths"]:
            if r.get("error"):
                T.append([row["app"], r["name"], "wrong rate: " + r["error"]] + [""] * 8)
                continue
            oc = r.get("octave")
            T.append([row["app"], r["name"], "-" if oc is None else "%+d" % oc,
                      fv(r.get("cents_worst")) + ("" if not r.get("octave_jumps") else " (%d off)" % r["octave_jumps"]),
                      fv(r.get("nonharm_60")), fv(r.get("nonharm_96")), fv(r.get("nonharm_108")),
                      fv(r.get("attack_ms"), "%.0f"), fv(r.get("release_s"), "%.2f"), fv(r.get("vel_span_db")),
                      fv(r.get("peak_dbfs"))])
    L += ["## Instruments", "", md_table(["App", "Instrument", "Octave", "Pitch err ¢", "Non-harm 60", "Non-harm 96",
                                          "Non-harm 108", "Attack ms", "Release -60 s", "Vel span dB", "Peak dBFS"], T), "",
          "- Octave: the default patch's transposition; pitch error is measured within it.",
          "- Non-harm: energy off the harmonic series in dB against the note (aliasing + noise + drift); MIDI 60 is "
          "the clean reference, 96 and 108 show aliasing.",
          "- Onset is not shown: a bounce's start is the DAW's choice, not the instrument's.", ""]
    T = []
    for row in rows:
        for r in row["fx"]:
            if r.get("error"):
                T.append([row["app"], r["name"], "wrong rate: " + r["error"]] + [""] * 7)
                continue
            resp = r.get("response_db") or {}
            ref = resp.get(1000, 0.0)
            flat = max([abs(v - ref) for c, v in resp.items() if 63 <= c <= 16000] or [0.0])
            star = "*" if (r["tail_s"] or 0) > 0.5 else ""
            lat = r["latency_onset"]
            T.append([row["app"], r["name"], fv(None if lat is None else lat * 1000.0 / SR, "%.2f"),
                      fv(r["lo"]["gain_db"], "%+.2f"), fv(r["lo"]["thd_db"]) + star, fv(r["hi"]["thd_db"]) + star,
                      fv(r["hf"]["nonharm_db"]) + star, fv(flat, "%.2f"), fv(r["tail_s"], "%.2f"), fv(r["rt60_s"], "%.2f")])
    L += ["## Effects", "", md_table(["App", "Effect", "Latency ms", "Gain 1k dB", "THD -12", "THD -1", "Alias HF dB",
                                      "Flatness ±dB", "Tail -60 s", "RT60 s"], T), "",
          "- Latency after the DAW's own compensation: a DAW bounce should read 0 ms whatever the effect reports.",
          "- `*` = tail longer than 0.5 s: THD/alias then measure the tail, compare tails instead. Dry = the rig floor.", ""]
    for row in rows:
        if not row["synths"] and not row["fx"]:
            L.append("- %s: no synth_*.wav or fx_*.wav bounces" % row["app"])
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("builtins_kit")
    d = tempfile.mkdtemp(prefix="bk")
    try:
        kit = make(os.path.join(d, "kit"))
        t.check(sorted(os.listdir(kit)) == ["PROTOCOL.md", "fxstim.wav", "synth.mid"], "kit files")
        mid = open(os.path.join(kit, "synth.mid"), "rb").read()
        events = sp.script()[0]
        t.check(mid.startswith(b"MThd") and mid.count(b"\x90") >= len(events), "synth.mid holds every note")
        t.check(midi_events()[0][0] == int(round(0.5 * 2 * bk.PPQ)), "first note at 0.5 s = beat 1 at 120 BPM")
        t.check("%g s" % synth_len() in open(os.path.join(kit, "PROTOCOL.md")).read(), "protocol names the bounce length")
        t.check(fname("synth", "Equation Synth") == "synth_EquationSynth.wav", "file names drop spaces")
        # an ideal instrument: a sine per note, linear 5 ms attack, 50 ms release; and a dry effect
        ideal = ensure_dir(os.path.join(d, "Ideal"))
        n = int(synth_len() * SR)
        y = np.zeros(n)
        for (t0, m, v, ln, _) in events:
            k = np.arange(int((ln + 0.5) * SR))
            env = np.minimum(1.0, k / (0.005 * SR)) * np.where(k < ln * SR, 1.0, np.exp(-(k - ln * SR) / (0.05 * SR / 6.9)))
            a = int(t0 * SR)
            seg = 0.5 * v * np.sin(2 * np.pi * sp.midi_hz(m) * k / SR) * env
            y[a:a + len(seg)] += seg[:n - a]
        bk.write_wav24(os.path.join(ideal, "synth_Sine.wav"), np.stack([y, y], 1))
        stim = pp.make_stimulus(SR)
        pp.write_wav24(os.path.join(ideal, "fx_Dry.wav"), stim, SR)
        a = analyse_dir(ideal)
        s = a["synths"][0]
        t.check(s["name"] == "Sine" and s.get("octave") == 0 and s["cents_worst"] < 1, "ideal sine: octave 0, %.2f cents" % s["cents_worst"])
        t.check(abs(s["vel_span_db"] - 20 * np.log10(4)) < 0.5, "velocity 0.25 -> 1 spans 12 dB (%.2f)" % s["vel_span_db"])
        fx = a["fx"][0]
        t.check(fx["latency_onset"] == 0 and abs(fx["lo"]["gain_db"]) < 0.01, "dry bounce: 0 latency, unity gain")
        rep = report([a, analyse_dir(ensure_dir(os.path.join(d, "Empty")))])
        t.check("## Instruments" in rep and "| Ideal | Sine |" in rep and "Empty: no synth_" in rep, "report renders")
        if not infinite_bin():
            t.skip("no Infinite binary: render part (set INFINITE_BIN or build)")
            return t.done()
        global SYNTHS, EFFECTS
        keep = SYNTHS, EFFECTS
        SYNTHS, EFFECTS = ["Oscillator"], ["Delay"]
        try:
            inf = os.path.join(d, "Infinite")
            t.check(render_infinite(inf, log=lambda *_: None) == 0, "Infinite renders Oscillator, Dry and Delay")
            b = analyse_dir(inf)
            osc = b["synths"][0]
            t.check(osc.get("octave") is not None and osc.get("cents_worst", 99) < 5, "Oscillator in tune (%s cents)" % osc.get("cents_worst"))
            dry = [r for r in b["fx"] if r["name"] == "Dry"][0]
            t.check(dry["latency_onset"] == 0 and abs(dry["lo"]["gain_db"]) < 0.1, "Infinite dry rig: 0 latency, unity")
        finally:
            SYNTHS, EFFECTS = keep
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    mp = sub.add_parser("make")
    mp.add_argument("--dir", default=KIT)
    ip = sub.add_parser("infinite")
    ip.add_argument("--dir", default=os.path.join(RE_OUTPUT, "builtins-kit", "Infinite"))
    an = sub.add_parser("analyse")
    an.add_argument("dirs", nargs="+")
    an.add_argument("--out")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "make":
        print(make(os.path.expanduser(a.dir)))
        return 0
    if a.cmd == "infinite":
        if not infinite_bin():
            print("usage: no Infinite binary (set INFINITE_BIN or build)", file=sys.stderr)
            return 2
        return 1 if render_infinite(os.path.expanduser(a.dir)) else 0
    if a.cmd == "analyse":
        bad = [x for x in a.dirs if not os.path.isdir(os.path.expanduser(x))]
        if bad:
            print("usage: not a folder: %s" % ", ".join(bad), file=sys.stderr)
            return 2
        rows = [analyse_dir(os.path.expanduser(x)) for x in a.dirs]
        write_out(report(rows), a.out)
        return 1 if any(not r["synths"] and not r["fx"] for r in rows) else 0
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
