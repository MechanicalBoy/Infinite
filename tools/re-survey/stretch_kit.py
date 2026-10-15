#!/usr/bin/env python3
"""re-survey stretch_kit: time-stretch quality, measured from each app's own stretched renders.

`make` writes four synthetic stimuli (48 kHz, 24-bit mono, nothing sampled from anyone) and PROTOCOL.md:

  drums.wav  -> kick/snare/hat every 0.25 s: onset timing error, transient smear (10-90 % rise), crest loss
  vocal.wav  -> three sung-vowel notes (A3, C#4, E4, formants of "a"): pitch error, non-harmonic artefacts
  tone.wav   -> 1 kHz sine: pitch error, amplitude flutter (phasiness), non-harmonic artefacts
  sweep.wav  -> log sweep 50 Hz - 10 kHz: frequency tracking error, level ripple

Each app stretches every stimulus to 0.5x, 0.8x, 1.25x and 2x its length with pitch kept, the way a user
would: the file is tagged 120 BPM, synced to tempo, and the project tempo is set to 120 / ratio. Bounces go
into one folder per app as stretch_<item>_<ratio>.wav (stretch_drums_2.wav). `infinite` renders the same
through Infinite's headless host: an arrangement Sample clip at 120 BPM, project tempo 120 / ratio.

Usage:
  python3 tools/re-survey/stretch_kit.py make [--dir ~/re-output/stretch-kit/kit]
  python3 tools/re-survey/stretch_kit.py infinite [--dir ~/re-output/stretch-kit/Infinite]
  python3 tools/re-survey/stretch_kit.py analyse ~/re-output/stretch-kit/Infinite ~/re-output/stretch-kit/Live ... [--out t.md]
  python3 tools/re-survey/stretch_kit.py --self-test
Exit: 0 ok, 1 a bounce is missing / render failed / self-test failed, 2 usage error.
"""

import argparse
import math
import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, quality_line, run, write_out  # noqa: E402
import bounce_kit as bk  # noqa: E402
import plugin_probe as pp  # noqa: E402
import synth_probe as sp  # noqa: E402

SR = 48000
KIT = os.path.join(RE_OUTPUT, "stretch-kit", "kit")
ITEMS = ["drums", "vocal", "tone", "sweep"]
RATIOS = [0.5, 0.8, 1.25, 2.0]
LEAD = 0.5          # silence before every stimulus, seconds (scaled with the stretch)
HIT_GAP = 0.25
N_HITS = 24
VOWEL = [(800, 80), (1150, 90), (2900, 120)]  # "a": formant centre, bandwidth (Hz)
NOTES = [220.0, 277.18, 329.63]
NOTE_S = 2.0
SWEEP = (50.0, 10000.0, 6.0)


def rname(r):
    return ("%g" % r).replace(".", "p")


# ---------------------------------------------------------------- stimuli

def hit_times(r=1.0):
    return [r * (LEAD + HIT_GAP * i) for i in range(N_HITS)]


def drums(r=1.0):
    """r = 1 is the stimulus; any other r is the ideal stretch (same hits, spaced r times wider)."""
    rng = np.random.default_rng(1)
    n = int(round(r * (LEAD + HIT_GAP * N_HITS + 0.5) * SR))
    x = np.zeros(n)
    t = np.arange(int(0.3 * SR)) / SR
    kick = np.sin(2 * np.pi * (55 * t + 95 * 0.03 * (1 - np.exp(-t / 0.03)))) * np.exp(-t / 0.12)
    noise = rng.standard_normal(len(t))
    snare = (0.5 * np.sin(2 * np.pi * 190 * t) + 0.5 * noise) * np.exp(-t / 0.06)
    hat = np.diff(np.concatenate([[0.0], noise])) * 0.5 * np.exp(-t / 0.015)
    shapes = [kick, hat, snare, hat]
    for i, s in enumerate(hit_times(r)):
        h = shapes[i % 4] * 0.5
        a = int(round(s * SR))
        m = min(len(h), n - a)
        x[a:a + m] += h[:m]
    return x


def vocal(r=1.0):
    """Additive sung vowel: harmonics of f0 weighted by three formant resonances."""
    n = int(round(r * (LEAD + NOTE_S * len(NOTES) + 0.5) * SR))
    x = np.zeros(n)
    m = int(round(r * NOTE_S * SR))
    t = np.arange(m) / SR
    fade = np.minimum(1, np.minimum(t / 0.02, (t[-1] - t) / 0.02))
    for j, f0 in enumerate(NOTES):
        s = np.zeros(m)
        k = 1
        while k * f0 < 5000:
            fk = k * f0
            amp = sum(1.0 / (1 + ((fk - fc) / (bw / 2)) ** 2) for fc, bw in VOWEL) + 0.02
            s += amp / k ** 0.5 * np.sin(2 * np.pi * fk * t + 0.7 * k)
            k += 1
        s *= 0.25 / np.max(np.abs(s)) * fade
        a = int(round(r * (LEAD + NOTE_S * j) * SR))
        x[a:a + m] += s
    return x


def tone(r=1.0):
    n = int(round(r * (LEAD + 4.0 + 0.5) * SR))
    x = np.zeros(n)
    m = int(round(r * 4.0 * SR))
    t = np.arange(m) / SR
    fade = np.minimum(1, np.minimum(t / 0.01, (t[-1] - t) / 0.01))
    a = int(round(r * LEAD * SR))
    x[a:a + m] = 0.25 * np.sin(2 * np.pi * 1000 * t) * fade  # -12 dBFS
    return x


def sweep_freq(t, r=1.0):
    f0, f1, T = SWEEP
    return f0 * np.exp(t / (r * T) * math.log(f1 / f0))


def sweep(r=1.0):
    f0, f1, T = SWEEP
    n = int(round(r * (LEAD + T + 0.5) * SR))
    x = np.zeros(n)
    m = int(round(r * T * SR))
    t = np.arange(m) / SR
    k = math.log(f1 / f0)
    fade = np.minimum(1, np.minimum(t / 0.01, (t[-1] - t) / 0.01))
    a = int(round(r * LEAD * SR))
    x[a:a + m] = 0.25 * np.sin(2 * np.pi * f0 * r * T / k * (np.exp(t / (r * T) * k) - 1)) * fade
    return x


GEN = {"drums": drums, "vocal": vocal, "tone": tone, "sweep": sweep}

PROTOCOL = """# Stretch kit protocol

For each app: a new project, 48 kHz, 4/4, master with no effects, fader at 0 dB. For every stimulus and
every ratio, export a 48 kHz 24-bit stereo WAV, no normalise, no dither, from bar 1 for the length given,
into one folder per app named stretch_<item>_<ratio>.wav, ratio written with p for the point:
stretch_drums_0p5.wav, stretch_drums_0p8.wav, stretch_drums_1p25.wav, stretch_drums_2.wav.

| Ratio | Project tempo | Export length = stimulus length x ratio + 1 s |
|---|---|---|
| 0.5 | 240 BPM | |
| 0.8 | 150 BPM | |
| 1.25 | 96 BPM | |
| 2 | 60 BPM | |

1. Import drums.wav, vocal.wav, tone.wav and sweep.wav at bar 1 on four audio tracks (solo one per export).
2. Tell the app each file is 120 BPM and turn on tempo sync / warp (stretch, pitch kept). Set the project
   tempo from the table. Each clip must end up ratio times its original length.
3. The algorithm per app:

| App | Setting | Modes to bounce (one folder each) |
|---|---|---|
| Live | Clip > Warp on, Seg. BPM 120 | Complex Pro (`Live-ComplexPro`), Beats (`Live-Beats`) |
| Logic | Flex Time on, project tempo follows | Polyphonic (`Logic-Polyphonic`), Slicing (`Logic-Slicing`) |
| Bitwig | Clip Inspector: Stretch on, tempo 120 | Elastique Pro (`Bitwig-ElastiquePro`), Slice (`Bitwig-Slice`) |

Then: `python3 tools/re-survey/stretch_kit.py analyse <folder> [<folder> ...]`.
Write down anything the app did on its own (detected a different tempo, moved the clip start).
"""


def make(d):
    ensure_dir(d)
    for k, g in GEN.items():
        bk.write_wav24(os.path.join(d, k + ".wav"), g())
    with open(os.path.join(d, "PROTOCOL.md"), "w") as f:
        f.write(PROTOCOL)
    return d


# ---------------------------------------------------------------- Infinite

def patch_text(wav, seconds, bpm):
    ticks = int(round(seconds * 2 * 960))  # seconds of a 120 BPM file, in ticks of 960 per beat
    return ("infinite-patch 1\n"
            "node 1 Modulators Audio File\n  uid 9001\n  s path %s\n  b loop 0\nend\n"
            "transport %g 4 4 0 0\n"
            "stream 1 0 1 0 0 1 0 stretch\n"
            "cliptick 0 1 0 %d 9001 0 0 0 0 1 0 0 0 0 stretch\n"
            "clipsample 0 1 1\n"
            "clipbpm 0 1 120 %g\n") % (wav, bpm, ticks, seconds)


def render_infinite(out_dir, kit=KIT, binp=None, log=print):
    binp = binp or infinite_bin()
    if not os.path.isdir(kit):
        make(kit)
    ensure_dir(out_dir)
    tmp = tempfile.mkdtemp(prefix="re-stretch-", dir=ensure_dir(os.path.join(RE_OUTPUT, "tmp")))
    fails = 0
    try:
        for item in ITEMS:
            src = os.path.join(kit, item + ".wav")
            seconds = len(GEN[item]()) / SR
            for r in RATIOS:
                p = os.path.join(tmp, "s.inf")
                with open(p, "w") as f:
                    f.write(patch_text(src, seconds, 120.0 / r))
                wav = os.path.join(out_dir, "stretch_%s_%s.wav" % (item, rname(r)))
                rc, out, err = run([binp, "--audio-summary", p, os.path.join(tmp, "s.json"), "--duration",
                                    "%g" % (seconds * r + 1.0), "--sample-rate", "%d" % SR, "--wav", wav,
                                    "--timeline"], timeout=300)
                ok = rc == 0 and os.path.exists(wav)
                fails += 0 if ok else 1
                log("  %-6s x%-5g %s" % (item, r, "ok" if ok else "FAILED rc %d" % rc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


# ---------------------------------------------------------------- analysis

def active_span(m, rel_db=-50.0):
    env = np.abs(m)
    th = env.max() * 10 ** (rel_db / 20)
    i = np.nonzero(env > th)[0]
    return (int(i[0]), int(i[-1])) if len(i) else (None, None)


def onsets(m, sr, rise_db=6.0):
    """Hit starts: the peak envelope (1 ms steps, held over 20 ms so a 50 Hz cycle does not ripple it)
    jumps rise_db above its level 5 ms earlier. Works under the tail of the previous hit."""
    h = sr // 1000
    k = len(m) // h
    blk = np.abs(m[:k * h]).reshape(k, h).max(axis=1)
    held = blk.copy()
    for j in range(1, 20):
        held[j:] = np.maximum(held[j:], blk[:-j])
    env = 20 * np.log10(held + 1e-9)
    floor = env.max() - 60
    out, last = [], -1000
    for i in range(5, k):
        if env[i] > floor and env[i] - env[i - 5] > rise_db and i - last > 40:
            j = i - 5
            while j < i and env[j + 1] - env[i - 5] < 3:
                j += 1
            out.append(j * h)
            last = i
    return np.array(out)


def rise_ms(m, i, sr):
    """10-90 % rise of the hit starting near sample i (peak of |x| over 1 ms blocks in the next 30 ms)."""
    h = sr // 1000
    seg = np.abs(m[max(0, i - 5 * h):i + 30 * h])
    k = len(seg) // h
    if k < 3:
        return None
    blk = seg[:k * h].reshape(k, h).max(axis=1)
    pk, base = blk.max(), blk[:4].min()  # base: the previous hit's tail just before this one
    a10 = np.nonzero(blk >= base + 0.1 * (pk - base))[0]
    a90 = np.nonzero(blk >= base + 0.9 * (pk - base))[0]
    return float((a90[0] - a10[0])) if len(a10) and len(a90) else None


def crest_db(m):
    rms = float(np.sqrt(np.mean(m ** 2)))
    return 20 * math.log10(max(float(np.abs(m).max()), 1e-12) / max(rms, 1e-12))


def cents(f, ref):
    return 1200 * math.log2(f / ref) if f and ref else None


def analyse_item(item, y, r, sr=SR):
    """Numbers for one stretched render y (mono) of `item` at ratio r."""
    res = {}
    src = GEN[item]()
    s0, s1 = active_span(src)
    o0, o1 = active_span(y)
    if o0 is None:
        return {"silent": True}
    if item != "drums":
        res["len_err_pct"] = 100.0 * ((o1 - o0) / (r * (s1 - s0)) - 1.0)
    if item == "drums":
        # hits keep their own length, so length is first-to-last hit, not the active span
        exp = np.array(hit_times(r))
        on = onsets(y, sr) / sr
        if len(on) >= 2:
            res["len_err_pct"] = 100.0 * ((on[-1] - on[0]) / (exp[-1] - exp[0]) - 1.0)
        if len(on):
            err = np.array([on[np.argmin(np.abs(on - e))] - e for e in exp]) * 1000
            off = float(np.median(err))
            res["offset_ms"] = off
            res["timing_ms"] = float(np.max(np.abs(err - off)))
            res["missed"] = int(sum(1 for e in exp if np.min(np.abs(on - e - off / 1000)) > 0.03))
            res["extra"] = max(0, len(on) - len(exp))  # one hit heard as two: a flam
            src_on = onsets(src, sr)
            rs = [rise_ms(src, int(i), sr) for i in src_on]
            ro = [rise_ms(y, int((e + off / 1000) * sr), sr) for e in exp]
            rs, ro = [v for v in rs if v is not None], [v for v in ro if v is not None]
            if rs and ro:
                res["smear_ms"] = float(np.median(ro) - np.median(rs))
        # Against the ideal stretch, not the source: wider gaps between hits raise the crest by themselves
        # (+2.0 / +0.3 / -1.0 / -3.0 dB at 0.5 / 0.8 / 1.25 / 2x), which read as loss before v0.6 1.6. Clipped
        # to full scale like any fixed-point bounce: overlapping hits peak at 1.07 (0.5x) and 1.03 (0.8x).
        res["crest_loss_db"] = crest_db(np.clip(GEN[item](r), -1.0, 1.0)) - crest_db(y)
    elif item == "vocal":
        worst, nh = 0.0, []
        for j, f0 in enumerate(NOTES):
            a = int((r * (LEAD + NOTE_S * j) + 0.25 * r * NOTE_S) * sr)
            seg = y[a:a + int(0.5 * r * NOTE_S * sr)][:sr]
            f = sp.yin(seg, sr, fmin=80, fmax=1000)
            if f is None:
                worst = None
                break
            f = sp.refine(seg, sr, f)
            worst = max(worst, abs(cents(f, f0)))
            nh.append(sp.nonharm_db(seg, sr, f, fmax=8000))
        res["pitch_cents"] = worst
        res["nonharm_db"] = max(nh) if nh else None
    elif item == "tone":
        a = int(r * (LEAD + 0.5) * sr)
        b = int(r * (LEAD + 3.5) * sr)
        seg = y[a:b]
        f = sp.yin(seg[:sr], sr, fmin=100, fmax=5000)
        f = sp.refine(seg[:sr], sr, f) if f else None
        res["pitch_cents"] = cents(f, 1000.0)
        h = int(0.02 * sr)
        k = len(seg) // h
        rm = np.sqrt(np.mean(seg[:k * h].reshape(k, h) ** 2, axis=1))
        res["flutter_db"] = 20 * math.log10(max(rm.max(), 1e-12) / max(rm.min(), 1e-12))
        res["nonharm_db"] = sp.nonharm_db(seg[:sr], sr, f) if f else None
    elif item == "sweep":
        n, hop = 4096, 1024
        win = np.hanning(n)
        errs, lv = [], []
        a0 = int(r * LEAD * sr)
        for i in range(a0, a0 + int(r * SWEEP[2] * sr) - n, hop):
            fe = float(sweep_freq((i - a0 + n / 2) / sr, r))
            if not 100 <= fe <= 8000:
                continue
            S = np.abs(np.fft.rfft(y[i:i + n] * win))
            b = int(np.argmax(S[1:-1])) + 1
            al, am, ac = np.log(S[b - 1] + 1e-30), np.log(S[b] + 1e-30), np.log(S[b + 1] + 1e-30)
            den = al - 2 * am + ac
            fm = (b + (0.5 * (al - ac) / den if den else 0.0)) * sr / n
            errs.append(cents(fm, fe))
            lv.append(20 * math.log10(max(float(np.sqrt(np.mean(y[i:i + n] ** 2))), 1e-12)))
        if errs:
            res["track_cents"] = float(np.sqrt(np.mean(np.square(errs))))
            res["ripple_db"] = float(np.percentile(lv, 99) - np.percentile(lv, 1))
    return res


def analyse_dir(d):
    row = {"app": os.path.basename(os.path.normpath(d)), "items": {}}
    for item in ITEMS:
        for r in RATIOS:
            p = os.path.join(d, "stretch_%s_%s.wav" % (item, rname(r)))
            if not os.path.exists(p):
                row.setdefault("missing", []).append(os.path.basename(p))
                continue
            x, sr, _ = pp.read_wav(p)
            row["items"][(item, r)] = analyse_item(item, x.mean(axis=1) if x.ndim > 1 else x, r, sr)
    return row


def fv(v, s="%.1f"):
    return "-" if v is None else s % v


def report(rows):
    L = ["# Stretch kit results", "",
         "Generated by `tools/re-survey/stretch_kit.py`. Each stimulus stretched to 0.5x / 0.8x / 1.25x / 2x its "
         "length, pitch kept. Ideal: length 0 %, timing 0 ms, smear 0 ms, crest loss 0 dB, pitch 0 cents, "
         "flutter 0 dB, sweep tracking 0 cents. Non-harmonic dB is artefact energy against the whole signal "
         "(lower is cleaner). Timing is the worst hit against the median hit; pre-echo (energy smeared ahead of a "
         "hit) shows as an early hit. Extra onsets are hits heard twice (flams).", ""]
    for item, cols in (("drums", [("len_err_pct", "Length %", "%+.1f"), ("timing_ms", "Timing ms", "%.1f"),
                                  ("missed", "Missed hits", "%d"), ("extra", "Extra onsets", "%d"), ("smear_ms", "Smear ms", "%+.1f"),
                                  ("crest_loss_db", "Crest loss dB", "%.1f")]),
                       ("vocal", [("len_err_pct", "Length %", "%+.1f"), ("pitch_cents", "Pitch cents", "%.1f"),
                                  ("nonharm_db", "Non-harmonic dB", "%.1f")]),
                       ("tone", [("pitch_cents", "Pitch cents", "%+.2f"), ("flutter_db", "Flutter dB", "%.2f"),
                                 ("nonharm_db", "Non-harmonic dB", "%.1f")]),
                       ("sweep", [("track_cents", "Tracking cents", "%.1f"), ("ripple_db", "Ripple dB", "%.1f")])):
        T = []
        for row in rows:
            for r in RATIOS:
                v = row["items"].get((item, r))
                if v is None:
                    continue
                T.append([row["app"], "%gx" % r] + (["silent"] + [""] * (len(cols) - 1) if v.get("silent")
                                                    else [fv(v.get(k), s) for k, _, s in cols]))
        L += ["## %s" % item, "", md_table(["App", "Ratio"] + [h for _, h, _ in cols], T), ""]
    for row in rows:
        if row.get("missing"):
            L.append("- %s missing: %s" % (row["app"], ", ".join(row["missing"])))
    L += [""] + quality(rows)
    return "\n".join(L) + "\n"


def quality(rows):
    """Worst drums numbers over the four ratios, one QUALITY row each per app (docs/quality/registry.tsv)."""
    out = []
    for row in rows:
        dr = [v for (item, _), v in row["items"].items() if item == "drums" and not v.get("silent")]
        if len(dr) != len(RATIOS) or any(k not in v for v in dr for k in ("extra", "timing_ms", "crest_loss_db")):
            continue
        out += [quality_line("stretch.extra_onsets", row["app"], max(v["extra"] for v in dr)),
                quality_line("stretch.timing_ms", row["app"], max(v["timing_ms"] for v in dr)),
                quality_line("stretch.crest_err_db", row["app"], max(abs(v["crest_loss_db"]) for v in dr))]
    return out


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("stretch_kit")
    d = tempfile.mkdtemp(prefix="sk")
    try:
        make(os.path.join(d, "kit"))
        t.check(sorted(os.listdir(os.path.join(d, "kit"))) == sorted([i + ".wav" for i in ITEMS] + ["PROTOCOL.md"]), "kit files")
        t.check(rname(1.25) == "1p25" and rname(2.0) == "2", "ratio names")
        ideal, vari = os.path.join(d, "Ideal"), os.path.join(d, "Varispeed")
        ensure_dir(ideal)
        ensure_dir(vari)
        for item, g in GEN.items():
            src = g()
            for r in RATIOS:
                y = g(r)
                bk.write_wav24(os.path.join(ideal, "stretch_%s_%s.wav" % (item, rname(r))), np.stack([y, y], 1))
                # tape-style resample: right length, pitch moves by 1/r
                v = np.interp(np.arange(int(len(src) * r)) / r, np.arange(len(src)), src)
                bk.write_wav24(os.path.join(vari, "stretch_%s_%s.wav" % (item, rname(r))), np.stack([v, v], 1))
        a = analyse_dir(ideal)
        t.check(not a.get("missing"), "ideal folder complete")
        for r in RATIOS:
            dr = a["items"][("drums", r)]
            t.check(abs(dr["len_err_pct"]) < 1 and dr["timing_ms"] < 1 and dr["missed"] == 0 and dr["extra"] == 0 and abs(dr["smear_ms"]) <= 2  # 1 ms blocks; hits overlap at 0.5x
                    and abs(dr["crest_loss_db"]) < 0.1,
                    "ideal drums x%g: length %.2f %%, timing %.2f ms, smear %s, crest %.2f dB"
                    % (r, dr["len_err_pct"], dr["timing_ms"], dr.get("smear_ms"), dr["crest_loss_db"]))
            vo = a["items"][("vocal", r)]
            t.check(vo["pitch_cents"] is not None and vo["pitch_cents"] < 2, "ideal vocal x%g pitch %s cents" % (r, vo["pitch_cents"]))
            to = a["items"][("tone", r)]
            t.check(abs(to["pitch_cents"]) < 0.5 and to["flutter_db"] < 0.2, "ideal tone x%g: %.2f cents, flutter %.2f dB" % (r, to["pitch_cents"], to["flutter_db"]))
            sw = a["items"][("sweep", r)]
            t.check(sw["track_cents"] < 10, "ideal sweep x%g tracks within %.1f cents" % (r, sw["track_cents"]))
        v = analyse_dir(vari)
        for r in (0.5, 2.0):
            want = -1200 * math.log2(r)
            to = v["items"][("tone", r)]
            t.check(abs(to["pitch_cents"] - want) < 5, "varispeed x%g reads %+.0f cents (want %+.0f)" % (r, to["pitch_cents"], want))
        t.check(v["items"][("sweep", 2.0)]["track_cents"] > 1000, "varispeed sweep x2 is an octave off")
        rep = report([a, v])
        t.check("## drums" in rep and "Varispeed" in rep, "report renders")
        t.check('QUALITY id=stretch.extra_onsets subject="Ideal" value=0.0000' in rep, "QUALITY rows")
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
    ip.add_argument("--dir", default=os.path.join(RE_OUTPUT, "stretch-kit", "Infinite"))
    ip.add_argument("--kit", default=KIT)
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
        return 1 if render_infinite(os.path.expanduser(a.dir), os.path.expanduser(a.kit)) else 0
    if a.cmd == "analyse":
        bad = [x for x in a.dirs if not os.path.isdir(os.path.expanduser(x))]
        if bad:
            print("usage: not a folder: %s" % ", ".join(bad), file=sys.stderr)
            return 2
        rows = [analyse_dir(os.path.expanduser(x)) for x in a.dirs]
        write_out(report(rows), a.out)
        return 1 if any(r.get("missing") for r in rows) else 0
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
