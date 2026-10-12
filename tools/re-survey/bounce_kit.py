#!/usr/bin/env python3
"""re-survey bounce_kit: what a DAW's own bounce/export does to sound and timing, measured from its files.

Step 1 `make` writes a kit (48 kHz, 24-bit WAV + type-1 MIDI) and PROTOCOL.md, the steps to do in each DAW.
Step 2 you bounce each item in the DAW (by hand; nothing here drives a DAW's UI) into one folder per DAW,
named <item>.wav. Step 3 `analyse` measures every bounce against the kit:

  impulse.wav  -> offset of the first spike (samples; export latency / PDC), gain (dB)
  sweep.wav    -> null residual against the source (dB), frequency response deviation 30 Hz-18 kHz (dB)
  sine1k.wav   -> level, THD+N (catches resampling, dither, limiting on the master)
  silence.wav  -> output floor (digital zero, or dither noise and its level)
  pan.wav      -> mono 1 kHz on a track panned centre: centre pan law (dB per side vs the source)
  clicks.mid   -> 16ths at 120 BPM into the DAW's simplest built-in drum/sampler with a sharp attack:
                  onset error vs the grid (mean = offset, sd = jitter, ms)
  tempo.mid    -> quarter notes, tempo 120 then 90 from bar 3 (tempo map in the file): does the DAW follow it

Usage:
  python3 tools/re-survey/bounce_kit.py make [--dir ~/re-output/bounce-kit/kit]
  python3 tools/re-survey/bounce_kit.py analyse ~/re-output/bounce-kit/Logic ~/re-output/bounce-kit/Live ... [--out t.md]
  python3 tools/re-survey/bounce_kit.py --self-test
Infinite can be one of the DAWs: its headless render of the same items lands in the same table.
Exit: 0 ok, 1 a bounce is missing or unreadable / self-test failed, 2 usage error.
"""

import argparse
import math
import os
import struct
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402

SR = 48000
KIT = os.path.join(RE_OUTPUT, "bounce-kit", "kit")
BPM = 120.0
PPQ = 480
ITEMS = ["impulse", "sweep", "sine1k", "silence", "pan", "clicks", "tempo"]


# ---------------------------------------------------------------- kit

def write_wav24(path, x):
    x = np.atleast_2d(x.T).T if x.ndim == 1 else x
    if x.ndim == 1:
        x = x[:, None]
    q = np.clip(np.round(x * 8388607.0), -8388608, 8388607).astype(np.int32)
    b = bytearray()
    for v in q.reshape(-1):
        b += struct.pack("<i", int(v))[:3]
    with wave.open(path, "wb") as w:
        w.setnchannels(q.shape[1])
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(bytes(b))


def stimuli():
    n = 8 * SR
    imp = np.zeros(n)
    imp[SR:n - SR:SR] = 0.5  # one spike a second from 1 s (-6 dBFS)
    t = np.arange(6 * SR) / SR
    f0, f1, T = 20.0, 20000.0, 6.0
    k = math.log(f1 / f0)
    sweep = 0.25 * np.sin(2 * np.pi * f0 * T / k * (np.exp(t / T * k) - 1))  # -12 dBFS log sweep
    fade = np.minimum(1, np.minimum(t / 0.01, (T - t) / 0.01))
    sweep = np.concatenate([np.zeros(SR // 2), sweep * fade, np.zeros(SR)])
    s1k = 0.1 * np.sin(2 * np.pi * 1000 * np.arange(4 * SR) / SR)  # -20 dBFS
    return {"impulse": imp, "sweep": sweep, "sine1k": s1k, "silence": np.zeros(4 * SR), "pan": s1k}


def vlq(v):
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.insert(0, (v & 0x7F) | 0x80)
        v >>= 7
    return bytes(out)


def smf(events, tempos):
    """Type-1 SMF: tempo track [(tick, bpm)], one note track [(tick, len_ticks, pitch, vel)]."""
    def track(evs):
        evs.sort(key=lambda e: (e[0], e[1]))
        b, last = bytearray(), 0
        for tick, _order, data in evs:
            b += vlq(tick - last) + data
            last = tick
        b += vlq(0) + b"\xff\x2f\x00"
        return b"MTrk" + struct.pack(">I", len(b)) + bytes(b)
    t0 = [(tick, 0, b"\xff\x51\x03" + struct.pack(">I", int(round(60e6 / bpm)))[1:]) for tick, bpm in tempos]
    t0.append((0, 0, b"\xff\x58\x04\x04\x02\x18\x08"))
    t1 = []
    for tick, ln, p, v in events:
        t1.append((tick, 1, bytes([0x90, p, v])))
        t1.append((tick + ln, 0, bytes([0x80, p, 0])))
    return b"MThd" + struct.pack(">IHHH", 6, 1, 2, PPQ) + track(t0) + track(t1)


def clicks_events():
    q = PPQ // 4
    return [(PPQ * 4 + i * q, q // 2, 60, 100) for i in range(64)]  # bar 2..5, 16ths


def tempo_events():
    return [(PPQ * 4 + i * PPQ, PPQ // 2, 60, 100) for i in range(16)]  # bar 2..5, quarters


def make(d):
    ensure_dir(d)
    for k, x in stimuli().items():
        write_wav24(os.path.join(d, k + ".wav"), x)
    with open(os.path.join(d, "clicks.mid"), "wb") as f:
        f.write(smf(clicks_events(), [(0, BPM)]))
    with open(os.path.join(d, "tempo.mid"), "wb") as f:
        f.write(smf(tempo_events(), [(0, BPM), (PPQ * 8, 90.0)]))
    with open(os.path.join(d, "PROTOCOL.md"), "w") as f:
        f.write(PROTOCOL)
    return d


PROTOCOL = """# Bounce kit protocol

For each DAW: new empty project, 48 kHz, 120 BPM, 4/4, master with no effects, fader at 0 dB.
Export each item from bar 1 / time 0 for the length given, as 48 kHz 24-bit WAV, stereo, no
normalise, no dither (unless the DAW forces it - note that), into one folder per DAW named
<item>.wav (e.g. ~/re-output/bounce-kit/Logic/impulse.wav).

| Item | Do | Export length |
|---|---|---|
| impulse | import impulse.wav at 0 on an audio track, centre pan | 8 s |
| sweep | import sweep.wav at 0 | 7.5 s |
| sine1k | import sine1k.wav at 0 | 4 s |
| silence | import silence.wav at 0 (or export an empty 4 s range) | 4 s |
| pan | import sine1k.wav at 0 on a MONO track, pan centre | 4 s |
| clicks | import clicks.mid on an instrument track with the simplest built-in drum/sampler, a short sharp hit, no swing/groove | bars 1-6 |
| tempo | import tempo.mid WITH its tempo map, same instrument | bars 1-6 |

Then: `python3 tools/re-survey/bounce_kit.py analyse <folder> [<folder> ...]`.
Write down anything the DAW did on its own (a dialog, forced dither, an import that dropped the tempo map).
"""


# ---------------------------------------------------------------- analysis

def load(path):
    x, sr, bits = pp.read_wav(path)
    return x, sr, bits


def first_spike(m, thresh=0.05):
    i = np.nonzero(np.abs(m) > thresh)[0]
    return int(i[0]) if len(i) else None


def rms_db(x):
    return 20 * math.log10(max(float(np.sqrt(np.mean(np.square(x)))), 1e-12))


def align(ref, y):
    """Integer lag of y against ref (cross-correlation by FFT)."""
    n = 1 << int(math.ceil(math.log2(len(ref) + len(y))))
    c = np.fft.irfft(np.fft.rfft(y, n) * np.conj(np.fft.rfft(ref, n)), n)
    lag = int(np.argmax(c))
    return lag - n if lag > n // 2 else lag


def response_dev(ref, y, sr):
    n = 1 << 15
    def spec(x):
        S = np.zeros(n // 2 + 1)
        for i in range(0, max(1, len(x) - n), n // 2):
            seg = x[i:i + n]
            if len(seg) < n:
                break
            S += np.abs(np.fft.rfft(seg * np.hanning(n))) ** 2
        return S
    R, Y = spec(ref), spec(y)
    f = np.arange(len(R)) * sr / n
    band = (f >= 30) & (f <= 18000) & (R > R.max() * 1e-8)
    d = 10 * np.log10((Y[band] + 1e-30) / (R[band] + 1e-30))
    return float(d.max() - np.median(d)), float(np.median(d) - d.min())


def onsets(m, sr, thresh_db=-30):
    env = np.abs(m)
    th = env.max() * 10 ** (thresh_db / 20)
    above = env > th
    idx = np.nonzero(above[1:] & ~above[:-1])[0] + 1
    out, last = [], -sr
    for i in idx:
        if i - last > sr * 0.04:  # one onset per 40 ms
            out.append(i)
            last = i
    return np.array(out)


def analyse_dir(d, kit):
    st = stimuli()
    row = {"daw": os.path.basename(os.path.normpath(d))}
    def get(item):
        p = os.path.join(d, item + ".wav")
        if not os.path.exists(p):
            row.setdefault("missing", []).append(item)
            return None
        x, sr, bits = load(p)
        row["sr"], row["bits"] = sr, bits
        return x
    x = get("impulse")
    if x is not None:
        s = first_spike(x.mean(1))
        row["impulse_offset"] = None if s is None else s - SR
        if s is not None:
            row["impulse_gain_db"] = 20 * math.log10(max(np.abs(x[s - 2:s + 3]).max(), 1e-12) / 0.5)
    x = get("sweep")
    if x is not None:
        ref = st["sweep"]
        m = x[:, 0]
        lag = align(ref, m)
        y = m[lag:lag + len(ref)] if lag >= 0 else np.concatenate([np.zeros(-lag), m])[:len(ref)]
        y = np.pad(y, (0, len(ref) - len(y)))
        g = float(np.dot(y, ref) / np.dot(ref, ref))
        row["sweep_lag"] = lag
        row["null_db"] = rms_db(y - g * ref) - rms_db(ref)
        row["resp_up_db"], row["resp_down_db"] = response_dev(ref, y, row.get("sr", SR))
    x = get("sine1k")
    if x is not None:
        seg = x[SR // 2:SR // 2 + SR, 0]
        row["sine_level_db"] = rms_db(seg) - rms_db(st["sine1k"])
        S = np.abs(np.fft.rfft(seg * pp.bh4(len(seg)))) ** 2
        f = np.arange(len(S)) * row.get("sr", SR) / len(seg)
        fund = np.abs(f - 1000) < 20
        row["thdn_db"] = 10 * math.log10(max(S[~fund & (f > 20) & (f < 20000)].sum(), 1e-30) / max(S[fund].sum(), 1e-30))
    x = get("silence")
    if x is not None:
        row["silence"] = "digital zero" if not np.any(x) else "%.1f dBFS" % rms_db(x)
    x = get("pan")
    if x is not None:
        seg = x[SR // 2:SR // 2 + SR]
        ref = rms_db(st["sine1k"])
        row["pan_l_db"] = rms_db(seg[:, 0]) - ref
        row["pan_r_db"] = rms_db(seg[:, -1]) - ref
    x = get("clicks")
    if x is not None:
        on = onsets(x.mean(1), row.get("sr", SR)) / row.get("sr", SR)
        grid = np.array([e[0] / PPQ * 60 / BPM for e in clicks_events()])
        if len(on):
            err = np.array([(on[np.argmin(np.abs(on - g))] - g) * 1000 for g in grid])
            row["clicks_found"] = int(len(on))
            row["click_offset_ms"] = float(np.median(err))
            row["click_jitter_ms"] = float(np.std(err - np.median(err)))
    x = get("tempo")
    if x is not None:
        on = onsets(x.mean(1), row.get("sr", SR)) / row.get("sr", SR)
        if len(on) >= 8:
            gaps = np.diff(on)
            row["tempo_first_bpm"] = 60.0 / float(np.median(gaps[:3]))
            row["tempo_last_bpm"] = 60.0 / float(np.median(gaps[-3:]))
    return row


def f(v, s="%.1f"):
    return "-" if v is None else s % v


def report(rows):
    T = []
    for r in rows:
        T.append((r["daw"], "%s/%s" % (r.get("sr", "-"), r.get("bits", "-")),
                  f(r.get("impulse_offset"), "%d"), f(r.get("impulse_gain_db"), "%.2f"), f(r.get("null_db")),
                  "+%s / -%s" % (f(r.get("resp_up_db"), "%.2f"), f(r.get("resp_down_db"), "%.2f")),
                  f(r.get("thdn_db")), r.get("silence", "-"),
                  "%s / %s" % (f(r.get("pan_l_db")), f(r.get("pan_r_db"))),
                  "%s / %s" % (f(r.get("click_offset_ms"), "%.2f"), f(r.get("click_jitter_ms"), "%.2f")),
                  "%s -> %s" % (f(r.get("tempo_first_bpm"), "%.0f"), f(r.get("tempo_last_bpm"), "%.0f"))))
    L = ["# Bounce kit results", "", "Generated by `tools/re-survey/bounce_kit.py`. Expected for a transparent bounce: offset 0, gain 0, "
         "null below -90 dB, response +-0.01 dB, silence digital zero, clicks 0 ms / < 0.1 ms, tempo 120 -> 90.", "",
         md_table(["DAW", "SR/bits", "Offset smp", "Gain dB", "Null dB", "Resp dev dB", "THD+N dB", "Silence",
                   "Pan centre L/R dB", "Clicks offset/jitter ms", "Tempo BPM"], T), ""]
    for r in rows:
        if r.get("missing"):
            L.append("- %s missing: %s" % (r["daw"], ", ".join(r["missing"])))
    return "\n".join(L) + "\n"


def self_test():
    import tempfile
    t = SelfTest("bounce_kit")
    d = tempfile.mkdtemp(prefix="bk")
    make(os.path.join(d, "kit"))
    t.check(sorted(os.listdir(os.path.join(d, "kit"))) == sorted([i + (".mid" if i in ("clicks", "tempo") else ".wav") for i in ITEMS] + ["PROTOCOL.md"]), "kit files")
    mid = open(os.path.join(d, "kit", "tempo.mid"), "rb").read()
    t.check(mid[:4] == b"MThd" and mid.count(b"MTrk") == 2 and mid.count(b"\xff\x51\x03") == 2, "tempo.mid has two tempo events")
    # a fake "DAW" that delays 64 samples, -1 dB, renders clicks perfectly, tempo 120 -> 90
    fake = os.path.join(d, "Fake")
    ensure_dir(fake)
    g = 10 ** (-1 / 20)
    for k, x in stimuli().items():
        y = np.concatenate([np.zeros(64), x])[:len(x)] * g
        write_wav24(os.path.join(fake, k + ".wav"), np.stack([y, y], 1))
    def hits(times, n):
        y = np.zeros(n)
        for s in times:
            i = int(round(s * SR))
            y[i:i + 200] += np.exp(-np.arange(200) / 30.0) * 0.5
        return y
    ct = [e[0] / PPQ * 0.5 for e in clicks_events()]
    write_wav24(os.path.join(fake, "clicks.wav"), np.stack([hits(ct, 12 * SR)] * 2, 1))
    tt, s = [], 2.0
    for i in range(16):
        tt.append(s)
        s += 0.5 if 2.0 + 0.5 * (i + 1) <= 4.0 else 60 / 90.0
    write_wav24(os.path.join(fake, "tempo.wav"), np.stack([hits(tt, 14 * SR)] * 2, 1))
    r = analyse_dir(fake, os.path.join(d, "kit"))
    t.check(r.get("impulse_offset") == 64, "offset 64 samples (%s)" % r.get("impulse_offset"))
    t.check(abs(r.get("impulse_gain_db", 9) + 1) < 0.05, "gain -1 dB (%s)" % r.get("impulse_gain_db"))
    t.check(r.get("null_db", 0) < -80 and r.get("sweep_lag") == 64, "delayed sweep nulls after alignment (%s dB)" % r.get("null_db"))
    t.check(r.get("resp_up_db", 9) < 0.1 and r.get("resp_down_db", 9) < 0.1, "flat response")
    t.check(r.get("silence") == "digital zero", "silence is digital zero")
    t.check(abs(r.get("pan_l_db", 9) + 1) < 0.05, "pan reads the -1 dB gain")
    t.check(abs(r.get("click_offset_ms", 9)) < 0.1 and r.get("click_jitter_ms", 9) < 0.05, "clicks on the grid (%s / %s)" % (r.get("click_offset_ms"), r.get("click_jitter_ms")))
    t.check(abs(r.get("tempo_first_bpm", 0) - 120) < 1 and abs(r.get("tempo_last_bpm", 0) - 90) < 1, "tempo 120 -> 90 (%s -> %s)" % (r.get("tempo_first_bpm"), r.get("tempo_last_bpm")))
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    mp = sub.add_parser("make")
    mp.add_argument("--dir", default=KIT)
    an = sub.add_parser("analyse")
    an.add_argument("dirs", nargs="+")
    an.add_argument("--kit", default=KIT)
    an.add_argument("--out")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "make":
        print(make(os.path.expanduser(a.dir)))
        return 0
    if a.cmd == "analyse":
        bad = [x for x in a.dirs if not os.path.isdir(os.path.expanduser(x))]
        if bad:
            print("usage: not a folder: %s" % ", ".join(bad), file=sys.stderr)
            return 2
        rows = [analyse_dir(os.path.expanduser(x), a.kit) for x in a.dirs]
        write_out(report(rows), a.out)
        return 1 if any(r.get("missing") for r in rows) else 0
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
