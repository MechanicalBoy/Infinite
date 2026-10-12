#!/usr/bin/env python3
"""re-survey synth_probe: play notes into an instrument through Infinite's own host and measure what comes out.

Black-box only, like plugin_probe: notes go in (Infinite --audio-summary --notes), audio comes out,
nothing of the instrument is opened or read. Every target plays the same note script at its default
patch (or the settings after @), so rows compare. Infinite's own synths take part as node:<Type>.

Note script (one render, 48 kHz):
  pitch    MIDI 24 36 48 60 72 84 96 108, vel 0.8, 0.8 s on, 1.5 s apart (from 0.5 s)
  velocity MIDI 60 at 0.25 / 0.5 / 1.0
  envelope MIDI 60, 1.0 s on, then 3 s of release
Measured per target: pitch (YIN, refined on the spectrum) -> octave offset of the patch and cents
error per note, aliasing (non-harmonic energy) at MIDI 96 / 108 with 60 as the clean reference,
note-on latency, attack 10-90 %, release to -60 dB, velocity span, L/R correlation, peak level,
determinism (the script rendered twice), CPU (ms of render per second of audio: idle, and per voice
from an 8-voice held chord, slope of a short and a long render so load time cancels).

Targets:
  "Diva" | au:aumu:DiVa:UHfX     an AU instrument by name substring or id
  "vst3 Serum2" | vst3:<id>      a VST3 instrument by bundle name or id
  node:Wavetable                 an Infinite synth node
  "Diva@VCF1: Cutoff=0.5"        settings after @ (host parameter names: plugin_probe.py params X)

Usage:
  python3 tools/re-survey/synth_probe.py run Diva "Serum 2" Vital node:Wavetable [--no-cpu] [--out t.md]
  python3 tools/re-survey/synth_probe.py --self-test
Results JSON: ~/re-output/synth-probe/<stamp>/results.json. Render WAVs are deleted unless --keep.
Limits: the default patch decides a lot (Diva's starts an octave down, a pad has a slow attack), so
compare like with like or set the patch with @settings. 16-bit render: floors near -90 dB.

Exit: 0 ok, 1 a target failed / self-test failed, 2 usage error or no Infinite binary.
"""

import argparse
import json
import math
import os
import shutil
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, RE_TMP, SelfTest, ensure_dir, infinite_bin, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402

SR = 48000
PITCH_NOTES = [24, 36, 48, 60, 72, 84, 96, 108]
VELS = [0.25, 0.5, 1.0]
GAP = 1.5
NOTE_LEN = 0.8
ENV_LEN = 1.0
ENV_TAIL = 3.0
CHORD = [48, 52, 55, 59, 60, 64, 67, 71]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ---------------------------------------------------------------- note script

def script():
    """[(t, pitch, vel, len, tag)] and the total duration."""
    ev, t = [], 0.5
    for m in PITCH_NOTES:
        ev.append((t, m, 0.8, NOTE_LEN, "pitch"))
        t += GAP
    for v in VELS:
        ev.append((t, 60, v, NOTE_LEN, "vel"))
        t += GAP
    ev.append((t, 60, 0.8, ENV_LEN, "env"))
    return ev, t + ENV_LEN + ENV_TAIL


def write_notes(events, d):
    """Infinite's --notes/--note-map pair: pitch comes from the map, so one event type per pitch."""
    types = {}
    for (_, m, _, _, _) in events:
        types["p%d" % m] = {"node": "fx", "pitch": m, "velocity_from": "v", "length_from": "len"}
    evs = [{"t": round(t, 6), "type": "p%d" % m, "v": v, "len": ln} for (t, m, v, ln, _) in events]
    ep, mp = os.path.join(d, "events.json"), os.path.join(d, "map.json")
    with open(ep, "w") as f:
        json.dump(evs, f)
    with open(mp, "w") as f:
        json.dump(types, f)
    return ep, mp


# ---------------------------------------------------------------- targets

def resolve(target, aus):
    t, settings = pp.split_settings(target)
    suffix = (" @ " + ", ".join("%s=%s" % kv for kv in settings.items())) if settings else ""
    if t.startswith("node:"):
        return {"kind": "node", "type": t[5:], "label": t + suffix, "settings": settings}
    if t.startswith("vst3:"):
        return {"kind": "vst3", "id": t, "label": t + suffix, "name": t, "settings": settings}
    if t.lower().startswith("vst3 ") or t.lower().endswith(".vst3"):
        want = t[5:].strip() if t.lower().startswith("vst3 ") else os.path.basename(t)[:-5]
        hits = [b for b in pp.list_vst3() if want.lower() in os.path.basename(b)[:-5].lower()]
        exact = [b for b in hits if os.path.basename(b)[:-5].lower() == want.lower()]
        hits = exact or hits
        binp = infinite_bin()
        if len(hits) != 1 or not binp:
            raise ValueError("'%s' matches %d VST3 bundles: %s" % (t, len(hits), ", ".join(map(os.path.basename, hits[:8])) or "none"))
        cls = [c for c in pp.vst3_classes(binp, hits[0]) if c["notes"]]
        if len(cls) != 1:
            raise ValueError("%s: %d instrument classes in the bundle" % (hits[0], len(cls)))
        return {"kind": "vst3", "id": cls[0]["id"], "label": cls[0]["name"] + " (VST3)" + suffix, "name": cls[0]["name"],
                "settings": settings}
    if t.startswith("au:"):
        hit = [a for a in aus if a["id"] == t]
        name = hit[0]["name"] if hit else t
        return {"kind": "au", "id": t, "label": name + suffix, "name": name, "settings": settings}
    hits = [a for a in aus if t.lower() in a["name"].lower() and a["type"] == "aumu"]
    exact = [a for a in hits if a["name"].lower().endswith(t.lower())]
    hits = exact if len(exact) == 1 else hits
    if len(hits) != 1:
        names = ", ".join("%s (%s)" % (a["name"], a["id"]) for a in hits[:8]) or "none"
        raise ValueError("'%s' matches %d instruments: %s" % (t, len(hits), names))
    a = hits[0]
    return {"kind": "au", "id": a["id"], "label": a["name"] + suffix, "name": a["name"], "settings": settings}


def patch_text(target, category=None):
    L = ["infinite-patch 1", "node 1 Notes Keyboard", "  id keys", "end"]
    if target["kind"] in ("au", "vst3"):
        L += ["node 2 AudioEffects Plugin", "  id fx", "  s plugin_format " + target["kind"], "  s plugin_id " + target["id"],
              "  s plugin_name " + target.get("name", target["label"]), "  b plugin_accepts_notes 1"]
        slots = pp.plugin_mapping(target) if target.get("settings") else []
        if slots:
            L.append("  i map_slots %d" % len(slots))
        for i, (addr, name, lo, hi, v) in enumerate(slots):
            L += ["  b map%d_assigned 1" % i, "  s map%d_addr %s" % (i, addr), "  s map%d_name %s" % (i, name),
                  "  f map%d_min %r" % (i, lo), "  f map%d_max %r" % (i, hi), "  f map%d_value %r" % (i, v)]
        L += ["end", "node 3 Utility Audio Out", "  id out", "end", "note fx 1 keys", "aud out audio fx"]
    else:
        L += ["node 2 %s %s" % (category, target["type"]), "  id fx"]
        for k, v in target.get("settings", {}).items():
            try:
                L.append("  f %s %r" % (k, float(v)))
            except ValueError:
                L.append("  s %s %s" % (k, v))
        L += ["end", "node 3 Utility Audio Out", "  id out", "end", "note fx 0 keys", "aud out audio fx"]
    return "\n".join(L) + "\n"


def render(binp, target, cat, events, dur, wav, tmp):
    ep, mp = write_notes(events, tmp)
    # Strict: a plugin that does not load must fail the row, not pass silence through.
    st = pp.render(binp, patch_text(target, cat), wav, SR, dur, tmp, ["--notes", ep, "--note-map", mp])
    if st.get("notes", {}).get("injected") != len(events):
        raise RuntimeError("only %s of %d notes were injected" % (st.get("notes", {}).get("injected"), len(events)))
    for p in st.get("plugins") or []:
        if not p.get("ready"):
            raise RuntimeError("%s did not load" % p.get("name"))
    return st


# ---------------------------------------------------------------- analysis (pure numpy)

def yin(x, sr, fmin=10.0, fmax=5000.0, thresh=0.12):
    """YIN f0 of a steady segment (Hz), or None."""
    x = x - np.mean(x)
    n = len(x)
    tmax = min(int(sr / fmin), n // 2)
    tmin = max(2, int(sr / fmax))
    w = n - tmax
    if w < 64:
        return None
    # d(tau) = sum_{j<w} (x[j] - x[j+tau])^2, its cross term by FFT
    N = 1 << int(math.ceil(math.log2(2 * n)))
    rw = np.fft.irfft(np.fft.rfft(x, N) * np.conj(np.fft.rfft(x[:w], N)), N)[:tmax + 1]
    e = np.cumsum(np.concatenate([[0.0], x * x]))
    energy0 = e[w]
    lag_energy = e[np.arange(tmax + 1) + w] - e[:tmax + 1]
    d = energy0 + lag_energy - 2 * rw
    d[0] = 0.0
    cm = np.ones_like(d)
    cs = np.cumsum(d[1:])
    cm[1:] = d[1:] * np.arange(1, len(d)) / np.maximum(cs, 1e-20)
    tau = None
    for k in range(tmin, tmax):
        if cm[k] < thresh:
            while k + 1 < tmax and cm[k + 1] < cm[k]:
                k += 1
            tau = k
            break
    if tau is None:
        k = tmin + int(np.argmin(cm[tmin:tmax]))
        if cm[k] > 0.5:
            return None
        tau = k
    if 1 <= tau < len(cm) - 1:
        a, b, c = cm[tau - 1], cm[tau], cm[tau + 1]
        den = a - 2 * b + c
        tau = tau + (0.5 * (a - c) / den if den != 0 else 0.0)
    return sr / tau


def refine(x, sr, f0):
    """Sharpen f0 on the spectrum: the strongest of harmonics 1..4 near k*f0, parabolic on log magnitude."""
    n = len(x)
    S = np.abs(np.fft.rfft(x * pp.bh4(n)))
    best = None
    for k in range(1, 5):
        fk = f0 * k
        if fk > sr * 0.45:
            break
        b = int(round(fk * n / sr))
        r = max(3, int(fk * 0.03 * n / sr))  # +-3 %: covers one sample of period error at 5 kHz
        lo, hi = max(1, b - r), min(len(S) - 2, b + r)
        i = lo + int(np.argmax(S[lo:hi + 1]))
        if best is None or S[i] > best[0]:
            a, m, c = np.log(S[i - 1] + 1e-30), np.log(S[i] + 1e-30), np.log(S[i + 1] + 1e-30)
            den = a - 2 * m + c
            p = 0.5 * (a - c) / den if den != 0 else 0.0
            best = (S[i], (i + p) * sr / n / k)
    return best[1] if best else f0


def nonharm_db(x, sr, f0, fmax=20000.0):
    """Energy outside the harmonics of f0 (aliasing + noise), dB relative to all energy 20 Hz..fmax."""
    n = len(x)
    S = np.abs(np.fft.rfft(x * pp.bh4(n))) ** 2
    f = np.arange(len(S)) * sr / n
    band = (f >= 20) & (f <= min(fmax, sr / 2 - 100))
    harm = np.zeros(len(S), bool)
    k = 1
    while k * f0 <= fmax:
        tol = max(4 * sr / n, k * f0 * 0.004)
        harm |= np.abs(f - k * f0) <= tol
        k += 1
    tot = S[band].sum()
    nh = S[band & ~harm].sum()
    return 10 * math.log10(max(nh, 1e-30) / max(tot, 1e-30))


def envelope(mono, sr, period_s, hop_ms=1.0):
    """Peak |x| over the trailing `period_s` (one cycle of the note), every hop_ms. An RMS over a hop
    shorter than a cycle would swing with the waveform; one cycle is the resolution of the times."""
    h = max(1, int(sr * hop_ms / 1000))
    m = len(mono) // h
    blk = np.max(np.abs(mono[:m * h].reshape(m, h)), axis=1)
    k = max(1, int(math.ceil(period_s * sr / h)))
    out = blk.copy()
    for j in range(1, k):
        out[j:] = np.maximum(out[j:], blk[:-j])
    return out, h / sr


def db(x):
    return 20 * math.log10(max(x, 1e-12))


def analyse(out, sr, events):
    mono = out.mean(axis=1)
    env, dt = envelope(mono, sr, 1.0 / midi_hz(60))
    res = {"peak_dbfs": db(float(np.max(np.abs(out)))), "clip_frac": float(np.mean(np.abs(out) >= 0.999))}
    pitches = []
    for (t, m, v, ln, tag) in events:
        if tag != "pitch":
            continue
        seg = mono[int((t + 0.3) * sr):int((t + 0.7) * sr)]
        row = {"midi": m, "level_db": db(float(np.sqrt(np.mean(seg ** 2)))) if len(seg) else None}
        f = yin(seg, sr) if len(seg) and row["level_db"] > -70 else None
        if f:
            f = refine(seg, sr, f)
            ratio = f / midi_hz(m)
            octv = int(round(math.log2(ratio)))
            row.update({"hz": f, "octave": octv, "cents": 1200 * math.log2(ratio) - 1200 * octv,
                        "nonharm_db": nonharm_db(seg, sr, f)})
            # tail of the previous note still sounding under this one
            pre = env[int((t - 0.02) / dt):int(t / dt)]
            row["bleed_db"] = db(float(np.max(pre))) - db(float(np.max(env[int(t / dt):int((t + 0.7) / dt)]) or 1e-12)) if len(pre) else None
        pitches.append(row)
    res["pitch"] = pitches
    good = [p for p in pitches if "cents" in p]
    if good:
        octs = [p["octave"] for p in good]
        res["octave"] = max(set(octs), key=octs.count)
        res["cents_worst"] = max(abs(p["cents"]) for p in good if p["octave"] == res["octave"]) \
            if any(p["octave"] == res["octave"] for p in good) else None
        res["octave_jumps"] = sum(1 for p in good if p["octave"] != res["octave"])
    by = {p["midi"]: p for p in pitches}
    for m in (60, 96, 108):
        res["nonharm_%d" % m] = by.get(m, {}).get("nonharm_db")
    vel = []
    for (t, m, v, ln, tag) in events:
        if tag == "vel":
            seg = mono[int((t + 0.2) * sr):int((t + 0.7) * sr)]
            vel.append(db(float(np.sqrt(np.mean(seg ** 2)))))
    res["vel_db"] = vel
    res["vel_span_db"] = vel[-1] - vel[0] if len(vel) == len(VELS) else None
    (t, m, v, ln, _) = [e for e in events if e[4] == "env"][0]
    i0, ioff = int(t / dt), int((t + ln) / dt)
    seg = env[i0:ioff]
    pk = float(np.max(seg)) if len(seg) else 0.0
    if pk > 1e-6:
        above = np.nonzero(seg >= pk * 0.01)[0]
        res["onset_ms"] = above[0] * dt * 1000 if len(above) else None
        a10 = np.nonzero(seg >= pk * 0.1)[0]
        a90 = np.nonzero(seg >= pk * 0.9)[0]
        res["attack_ms"] = (a90[0] - a10[0]) * dt * 1000 if len(a10) and len(a90) else None
        at_off = float(np.mean(env[max(i0, ioff - 10):ioff]))
        tail = env[ioff:]
        below = np.nonzero(tail <= at_off * 1e-3)[0]
        res["release_s"] = below[0] * dt if len(below) else None
        res["release_floor_db"] = db(float(np.min(tail[-int(0.2 / dt):]))) - db(at_off) if len(tail) else None
        s = out[int((t + 0.2) * sr):int((t + ln) * sr)]
        if s.shape[1] >= 2 and np.std(s[:, 0]) > 0 and np.std(s[:, 1]) > 0:
            res["lr_corr"] = float(np.corrcoef(s[:, 0], s[:, 1])[0, 1])
    return res


# ---------------------------------------------------------------- run

def cpu_slope(binp, target, cat, notes_fn, tmp):
    """ms of render per second of audio, from a 2 s and a 32 s render (load time cancels)."""
    times = []
    for dur in (2.0, 32.0):
        st = render(binp, target, cat, notes_fn(dur), dur, os.path.join(tmp, "cpu.wav"), tmp)
        times.append(st.get("elapsed_ms", 0))
    return (times[1] - times[0]) / 30.0


def probe(targets, cpu=True, keep=False, log=print):
    binp = infinite_bin()
    if not binp:
        raise SystemExit(2)
    aus = pp.list_aus()
    resolved = [resolve(t, aus) for t in targets]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tmp = ensure_dir(os.path.join(RE_TMP, "synth-probe-" + stamp))
    events, dur = script()
    results = []
    for r in resolved:
        row = {"target": r, "sr": SR}
        try:
            cat = pp.node_category(binp, r["type"], tmp) if r["kind"] == "node" else None
            a, b = os.path.join(tmp, "a.wav"), os.path.join(tmp, "b.wav")
            st = render(binp, r, cat, events, dur, a, tmp)
            render(binp, r, cat, events, dur, b, tmp)
            out, _, bits = pp.read_wav(a)
            out2, _, _ = pp.read_wav(b)
            row.update(analyse(out, SR, events))
            row["wav_bits"] = bits
            diff = float(np.max(np.abs(out - out2))) if out.shape == out2.shape else 1.0
            row["deterministic"] = diff == 0.0
            row["rerender_diff_db"] = db(diff) if diff > 0 else None
            row["warnings"] = [w.get("message") for w in st.get("warnings", [])]
            if keep:
                row["wav"] = a
            if cpu:
                idle = cpu_slope(binp, r, cat, lambda d: [(d - 0.01, 60, 0.0, 0.005, "x")], tmp)
                busy = cpu_slope(binp, r, cat, lambda d: [(0.05, m, 0.7, d, "x") for m in CHORD], tmp)
                row["cpu_idle_ms_per_s"] = idle
                row["cpu_per_voice_ms_per_s"] = (busy - idle) / len(CHORD)
            row["ok"] = True
        except Exception as e:  # one bad instrument must not stop the table
            row["ok"] = False
            row["error"] = str(e)
        results.append(row)
        log("probed %-32s %s" % (r["label"], "ok" if row["ok"] else "FAILED: " + row["error"]))
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "synth-probe", stamp))
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=1, default=float)
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return results, out_dir


def fmt(v, spec="%.1f"):
    return "-" if v is None else spec % v


def to_markdown(results):
    rows = []
    for r in results:
        if not r.get("ok"):
            rows.append((r["target"]["label"], "FAILED: " + r.get("error", "")) + ("",) * 11)
            continue
        oc = r.get("octave")
        rows.append((r["target"]["label"],
                     "-" if oc is None else "%+d" % oc,
                     fmt(r.get("cents_worst"), "%.1f") + ("" if not r.get("octave_jumps") else " (%d off)" % r["octave_jumps"]),
                     fmt(r.get("nonharm_60")), fmt(r.get("nonharm_96")), fmt(r.get("nonharm_108")),
                     fmt(r.get("onset_ms"), "%.1f"), fmt(r.get("attack_ms"), "%.0f"), fmt(r.get("release_s"), "%.2f"),
                     fmt(r.get("vel_span_db")), fmt(r.get("lr_corr"), "%.2f"),
                     "yes" if r.get("deterministic") else "no (%s dB)" % fmt(r.get("rerender_diff_db"), "%.0f"),
                     "%s / %s" % (fmt(r.get("cpu_idle_ms_per_s"), "%.2f"), fmt(r.get("cpu_per_voice_ms_per_s"), "%.2f"))))
    L = ["# Synth probe (%d Hz, %d-bit render)" % (SR, results[0].get("wav_bits", 0) if results else 0), "",
         "Generated by `tools/re-survey/synth_probe.py`. Black-box: notes in through Infinite's own host, audio out. "
         "Default patch of each instrument unless settings follow @.", "",
         md_table(["Target", "Octave", "Pitch err ¢ (worst)", "Non-harm 60", "Non-harm 96", "Non-harm 108",
                   "Onset ms", "Attack ms", "Release -60 s", "Vel span dB", "L/R corr", "Same twice", "CPU ms/s idle / voice"], rows), "",
         "- Octave: the patch's transposition (most common over the notes); pitch error is measured within it.",
         "- Non-harm: energy off the harmonic series in dB (aliasing + noise + drift); 60 is the clean reference.",
         "- Onset: note-on to -40 dB of the note's peak. Attack 10-90 % (peak envelope, one-cycle resolution: ~4 ms at MIDI 60). Release: note-off to -60 dB (- = never, e.g. a floor).",
         "- Same twice: the whole script rendered twice; analog-drift synths differ by design.",
         "- CPU: render ms per second of audio, offline. Per voice = (8-voice chord - idle) / 8.", ""]
    for r in results:
        if r.get("ok"):
            L.append("- %s per note: %s" % (r["target"]["label"], ", ".join(
                "%d:%s" % (p["midi"], "silent" if "cents" not in p else "%+.0f¢/%.0f" % (p["cents"], p["nonharm_db"]))
                for p in r["pitch"])))
            for w in r.get("warnings", []):
                L.append("- WARNING %s: %s" % (r["target"]["label"], w))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("synth_probe")
    k = np.arange(int(0.4 * SR))
    for hz, odd in ((16.35, False), (32.7, False), (261.63, False), (4186.0, False), (4186.0, True)):
        hs = range(1, int(20000 / hz) + 1, 2 if odd else 1)
        wave = sum(np.sin(2 * np.pi * hz * h * k / SR) / h for h in hs)
        f = refine(wave, SR, yin(wave, SR))
        t.check(abs(1200 * math.log2(f / hz)) < 2.0, "pitch of a band-limited %s at %g Hz within 2 cents (got %.2f Hz)"
                % ("square" if odd else "saw", hz, f))
    sine = np.sin(2 * np.pi * 1000 * k / SR)
    t.check(nonharm_db(sine, SR, 1000.0) < -100, "a clean sine has no non-harmonic energy")
    alias = sine + 0.01 * np.sin(2 * np.pi * 1730 * k / SR)
    nh = nonharm_db(alias, SR, 1000.0)
    t.check(abs(nh + 40) < 1, "a -40 dB inharmonic tone reads -40 dB (got %.1f)" % nh)
    ev, dur = script()
    t.check(len(ev) == len(PITCH_NOTES) + len(VELS) + 1 and dur > 20, "note script shape")
    synth = np.zeros((int(dur * SR), 2))
    for (st, m, v, ln, tag) in ev:
        a, b = int(st * SR), int((st + ln) * SR)
        kk = np.arange(b - a)
        hz = midi_hz(m)
        tone = v * 0.3 * sum(np.sin(2 * np.pi * hz * h * kk / SR) / h for h in range(1, max(2, int(18000 / hz)) + 1))
        synth[a:b, 0] += tone
        synth[a:b, 1] += tone
    res = analyse(synth, SR, ev)
    t.check(res.get("octave") == 0 and res.get("cents_worst", 99) < 2, "ideal synth: octave 0, pitch error < 2 cents (%s)" % res.get("cents_worst"))
    t.check(res.get("vel_span_db") is not None and abs(res["vel_span_db"] - 12.04) < 0.2, "velocity 0.25 -> 1 = +12 dB on a linear synth")
    t.check(res.get("onset_ms", 9) < 2 and res.get("attack_ms", 9) <= 5,
            "ideal synth: instant onset, attack within one cycle (%s / %s ms)" % (res.get("onset_ms"), res.get("attack_ms")))
    if not infinite_bin():
        t.skip("no Infinite binary: integration part (set INFINITE_BIN or build)")
        return t.done()
    res, out_dir = probe(["node:Wavetable"], cpu=False, log=lambda *_: None)
    w = res[0]
    t.check(w.get("ok"), "node:Wavetable renders (%s)" % w.get("error", "ok"))
    t.check(w.get("ok") and w.get("octave") is not None and w.get("cents_worst", 99) < 10,
            "node:Wavetable plays in tune (octave %s, worst %s cents)" % (w.get("octave"), w.get("cents_worst")))
    shutil.rmtree(out_dir, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("run", help="probe instruments")
    rp.add_argument("targets", nargs="+")
    rp.add_argument("--no-cpu", action="store_true")
    rp.add_argument("--keep", action="store_true", help="keep render WAVs in ~/re-output/tmp")
    rp.add_argument("--out", help="markdown table path (default stdout)")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd != "run":
        ap.print_usage(sys.stderr)
        return 2
    if not infinite_bin():
        print("no Infinite binary (build it, or set INFINITE_BIN)", file=sys.stderr)
        return 2
    try:
        aus = pp.list_aus()
        for t in a.targets:
            r = resolve(t, aus)
            if r["kind"] in ("au", "vst3") and r["settings"]:
                pp.plugin_mapping(r)
    except ValueError as e:
        print("usage: %s" % e, file=sys.stderr)
        return 2
    res, out_dir = probe(a.targets, cpu=not a.no_cpu, keep=a.keep, log=lambda m: print(m, file=sys.stderr))
    write_out(to_markdown(res), a.out)
    print("results: %s" % os.path.join(out_dir, "results.json"), file=sys.stderr)
    return 0 if all(r.get("ok") for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
