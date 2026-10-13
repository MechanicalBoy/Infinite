#!/usr/bin/env python3
"""re-survey av_bench: audio->picture latency and beat-to-frame lock, plus a live audio-reactive scene's frame times.

Stimulus: loop.wav, 8 beats at 128 BPM (one 5 ms 1 kHz click per beat, 48 kHz), played looping. Each app makes a
picture that flashes from the sound, records a movie with the sound in it, and the movie is read back with
AVFoundation (render_bench's video_read.swift): every click in the movie's own audio track against every dark->bright
edge in its picture.

  latency_ms   flash time minus click time, per beat (positive = picture late)
  frame error  flash frame minus the first frame at or after the click (0 = as early as possible)
  lock %       beats whose flash lands 0 or 1 frames after the first possible frame, never early
  jitter_ms    standard deviation of latency;  drift_ms_min  trend of frame error (in ms) over the take
  misses       clicks with no flash within half a beat;  extras  flashes with no click

Infinite variants (headless offline --render, no GUI):
  reactive       Audio File (loop) -> Stereo insert -> Output, Audio Analyze onset -> Shape fill. The insert forces the
                 graph-audio path, so analysis runs in lockstep with the rendered audio.
  reactive-file  the same with the Audio File wired straight into the Output. Finding (2026-10-13): on this path the
                 recorder muxes the file itself, the graph's audio is never processed offline, Audio Analyze never
                 fires (no flashes), and the render can stall to under 1 fps until --timeout. Kept as a regression probe.
  clock          no analysis: fillOpacity = (t * BPM / 60) mod 1 < 0.1, the beat clock against the same audio.
                 Measures beat-to-frame lock of the transport itself.
Live mode (needs the owner's camera and mic, not automated): docs/plans/re-survey/PROTOCOL-av.md.

TouchDesigner (no headless mode; av_bench_td.py, pasted into the Textport by whoever drives the GUI):
  mode av     the same click-and-flash: Audio File In (loop) -> Analyze -> Constant TOP, Movie File Out with audio, real
              time; also logs its own per-frame times.
  mode scene  an audio-reactive 10,000-instance scene at 1280x720, real time, logs every frame's time for 60 s.

Usage:
  python3 tools/re-survey/av_bench.py infinite [--dir ~/re-output/av-bench/Infinite] [--seconds 15] [--fps 30]
  python3 tools/re-survey/av_bench.py td-prep [--mode av|scene]   # writes loop.wav, prints the Textport line
  python3 tools/re-survey/av_bench.py td                          # after TD prints 'AVBENCH done'
  python3 tools/re-survey/av_bench.py movie <movie.mp4>           # analyse any click+flash movie
  python3 tools/re-survey/av_bench.py frames <frames.json>        # analyse a per-frame time log
  python3 tools/re-survey/av_bench.py analyse <dir> ... [--out results.md]
  python3 tools/re-survey/av_bench.py --self-test
Each run writes results.json and quality.txt (QUALITY rows av.*, live.*). Exit: 0 ok, 1 failed, 2 usage error.
"""

import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HERE, RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, quality_line, run, write_out  # noqa: E402
import render_bench as rb  # noqa: E402  (AVFoundation reader, flash edges)

BPM = 128.0
BEAT_S = 60.0 / BPM          # 0.46875 s = 22,500 samples at 48 kHz
BEATS = 8
SR = 48000
TD_SCRIPT = os.path.join(HERE, "av_bench_td.py")


# ---------------------------------------------------------------- stimulus

def loop_wav(path, beats=BEATS):
    n = int(round(beats * BEAT_S * SR))
    x = np.zeros(n, np.float32)
    burst = (0.8 * np.sin(2 * np.pi * 1000 * np.arange(240) / SR)).astype(np.float32)
    for b in range(beats):
        i = int(round(b * BEAT_S * SR))
        x[i:i + 240] = burst
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


# ---------------------------------------------------------------- analysis

def onset_times(x, sr, min_gap_s=BEAT_S / 2):
    """Click starts: rising edges over a quarter of the peak, merged if closer than min_gap_s."""
    if not len(x):
        return []
    thr = 0.25 * float(np.max(np.abs(x)))
    if thr <= 0:
        return []
    e = np.abs(x) > thr
    idx = np.flatnonzero(e[1:] & ~e[:-1]) + 1
    if e[0]:
        idx = np.insert(idx, 0, 0)
    out, last = [], -1e9
    for i in idx:
        if i - last > min_gap_s * sr:
            out.append(float(i) / sr)
            last = i
    return out


def av_stats(onsets, flashes, fps, period=BEAT_S):
    """Pair each click with the first flash from half a frame before it to half a beat after it."""
    fr = 1.0 / fps
    res = {"clicks": len(onsets), "flashes": len(flashes), "fps": fps}
    if not onsets:
        return res
    f = np.array(flashes, float)
    used = set()
    lat, ferr, ot = [], [], []
    for o in onsets:
        cand = [j for j in range(len(f)) if o - fr / 2 <= f[j] < o + period / 2 and j not in used]
        if not cand:
            continue
        j = cand[0]
        used.add(j)
        lat.append(f[j] - o)
        ferr.append(int(round(f[j] * fps)) - int(math.ceil(o * fps - 1e-6)))
        ot.append(o)
    res.update({"matched": len(lat), "misses": len(onsets) - len(lat), "extras": len(flashes) - len(used)})
    if not lat:
        return res
    lat_ms = np.array(lat) * 1000
    ferr = np.array(ferr)
    res.update({"latency_ms": float(np.median(lat_ms)), "latency_mean_ms": float(lat_ms.mean()),
                "latency_min_ms": float(lat_ms.min()), "latency_max_ms": float(lat_ms.max()),
                "jitter_ms": float(lat_ms.std()),
                "frame_error": {str(k): int(v) for k, v in zip(*np.unique(ferr, return_counts=True))},
                "early": int(np.sum(ferr < 0)),
                "lock_pct": 100.0 * float(np.sum((ferr >= 0) & (ferr <= 1))) / len(onsets),
                # drift on frame error, not raw latency: a beat that is not a whole number of frames makes latency
                # a sawtooth whose fit over a short take reads as tens of ms/min of fake drift
                "drift_ms_min": float(np.polyfit(ot, ferr * fr * 1000, 1)[0]) * 60 if len(lat) > 2 else 0.0})
    return res


def analyse_movie(path):
    info = rb.movie_info(path)
    fps = info.get("fps") or 30
    t, l = rb.movie_luma(path)
    x, sr = rb.movie_audio(path)
    # the click at t=0 and its flash are skipped: AAC encoder priming smears the first ~1 ms, which reads as a flash
    # 1 frame early. Pairing starts at the second click.
    on = [o for o in onset_times(x, sr) if o > 0.05]
    fl = rb.flash_times(t, l) if len(l) and l.max() > l.min() else []
    fl = [f for f in fl if on and f > on[0] - 1.0 / fps]
    s = av_stats(on, fl, fps)
    s.update({"movie": path, "frames": info.get("frames"), "video_s": info.get("video_s"), "audio_s": info.get("audio_s")})
    return s


def frame_stats(stamps, target_fps):
    """Per-frame times from a list of frame-start timestamps (seconds)."""
    dt = np.diff(np.array(stamps, float)) * 1000
    if not len(dt):
        return {}
    budget = 1000.0 / target_fps
    return {"frames": int(len(dt) + 1), "target_fps": target_fps, "fps": 1000.0 / float(dt.mean()),
            "p50_ms": float(np.percentile(dt, 50)), "p95_ms": float(np.percentile(dt, 95)),
            "p99_ms": float(np.percentile(dt, 99)), "max_ms": float(dt.max()),
            "drop_pct": 100.0 * float(np.sum(dt > 1.5 * budget)) / len(dt)}


# ---------------------------------------------------------------- Infinite

def inf_patch(variant, wav):
    L = ["infinite-patch 1",
         "node 1 Source Shape", "  id flash", "  f width 320", "  f height 180", "  f size 1", "  f sizeX 1", "  f sizeY 1",
         "  f fillOpacity 0", "  c bgColor 0 0 0", "  f bgOpacity 1", "end",
         "node 2 Modulators Audio File", "  id click", "  s path %s" % wav, "  b loop 1", "end",
         "node 4 Utility Output", "  id out", "  b includeAudio 1", "end", "cable out 0 flash"]
    if variant == "reactive":
        L += ["node 3 Modulators Audio Analyze", "  id an", "end", "node 5 AudioEffects Stereo", "  id fx", "end",
              "aud fx 0 click", "aud out 1 fx", "aud an 0 click", "mod flash fillOpacity an onset 0 1 0.5 0 1"]
    elif variant == "reactive-file":
        L += ["node 3 Modulators Audio Analyze", "  id an", "end",
              "aud out 1 click", "aud an 0 click", "mod flash fillOpacity an onset 0 1 0.5 0 1"]
    elif variant == "clock":
        L += ["aud out 1 click", "expr flash fillOpacity mod(t * %g, 1) < 0.1" % (BPM / 60.0)]
    else:
        raise ValueError(variant)
    return "\n".join(L) + "\n"


def inf_render(binp, patch, movie, seconds, fps, timeout):
    t0 = time.perf_counter()
    rc, out, err = run([binp, "--render", patch, movie, "--duration", "%g" % seconds, "--fps", str(fps),
                        "--codec", "h264", "--timeout", str(timeout)], timeout=timeout + 30)
    st = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    return {"rc": rc, "ok": bool(st.get("ok")), "frames": st.get("frames", 0), "status": st.get("status"),
            "want": int(round(seconds * fps)), "wall_s": time.perf_counter() - t0}


def run_infinite(d, seconds, fps):
    binp = infinite_bin()
    if not binp:
        raise RuntimeError("no Infinite build (set INFINITE_BIN)")
    ensure_dir(d)
    wav = os.path.join(d, "loop.wav")
    loop_wav(wav)
    res = {"app": "Infinite", "variants": {}, "fps": fps, "seconds": seconds}
    for variant, secs, tmo in (("reactive", seconds, 110), ("clock", seconds, 110), ("reactive-file", 2, 30)):
        patch = os.path.join(d, variant + ".inf")
        with open(patch, "w") as f:
            f.write(inf_patch(variant, wav))
        movie = os.path.join(d, variant + ".mp4")
        r = inf_render(binp, patch, movie, secs, fps, tmo)
        if os.path.exists(movie):
            r.update(analyse_movie(movie))
        r["stalled"] = r["frames"] < r["want"]
        res["variants"][variant] = r
        print("Infinite %s: %s" % (variant, json.dumps({k: r.get(k) for k in ("frames", "want", "matched", "misses", "latency_ms", "jitter_ms", "lock_pct")})))
    return res


# ---------------------------------------------------------------- TouchDesigner

def td_prep(d, mode):
    ensure_dir(d)
    loop_wav(os.path.join(d, "loop.wav"))
    print("In a new TouchDesigner project open Dialogs > Textport and paste:\n")
    print("import os; os.environ['AV_TD_MODE'] = '%s'; exec(open(%r).read(), globals())\n" % (mode, TD_SCRIPT))
    print("Wait for 'AVBENCH done' (about %d s), then: python3 %s td" % (20 if mode == "av" else 65, os.path.relpath(__file__)))


def run_td(d):
    res = {"app": "TouchDesigner", "variants": {}, "live": {}}
    for mode in ("av", "scene"):
        p = os.path.join(d, "td_%s.json" % mode)
        if not os.path.exists(p):
            continue
        with open(p) as f:
            j = json.load(f)
        res["version"] = j.get("version")
        if mode == "av" and j.get("movie") and os.path.exists(j["movie"]):
            res["variants"]["reactive"] = analyse_movie(j["movie"])
        if j.get("frame_s"):
            res["live"][mode] = frame_stats(j["frame_s"], j.get("cook_rate", 60))
        if j.get("errors"):
            res.setdefault("errors", []).extend(j["errors"])
    return res


# ---------------------------------------------------------------- report

def quality_rows(res):
    rows, app = [], res["app"]
    r = res.get("variants", {}).get("reactive")
    if r and r.get("matched"):
        rows += [quality_line("av.react_latency_ms", app, r["latency_ms"]), quality_line("av.react_jitter_ms", app, r["jitter_ms"]),
                 quality_line("av.beat_lock_pct", app, r["lock_pct"]), quality_line("av.drift_ms_min", app, r["drift_ms_min"])]
    c = res.get("variants", {}).get("clock")
    if c and c.get("matched"):
        rows.append(quality_line("av.clock_lock_pct", app, c["lock_pct"]))
    s = res.get("live", {}).get("scene")
    if s:
        rows += [quality_line("live.frame_p95_ms", app, s["p95_ms"]), quality_line("live.drop_pct", app, s["drop_pct"])]
    return rows


def report(results):
    out = ["# av_bench: audio->picture latency, beat lock, live frame times", "",
           "loop.wav: %d clicks at %g BPM, looping. Latency = flash minus click in the app's own movie; lock = flash 0-1 "
           "frames after the first possible frame." % (BEATS, BPM), ""]
    rows = []
    for x in results:
        for v, r in x.get("variants", {}).items():
            rows.append([x["app"], v, "%s/%s" % (r.get("frames"), r.get("want", r.get("frames"))), r.get("clicks"), r.get("matched"),
                         r.get("misses"), r.get("extras"), "%.1f" % r["latency_ms"] if "latency_ms" in r else "-",
                         "%.1f" % r["jitter_ms"] if "jitter_ms" in r else "-", "%.0f" % r["lock_pct"] if "lock_pct" in r else "-",
                         json.dumps(r.get("frame_error", {})), "%.2f" % r["drift_ms_min"] if "drift_ms_min" in r else "-",
                         " ".join(n for n, c in (("STALLED", r.get("stalled")), ("NO REACTION", r.get("clicks") and not r.get("matched"))) if c)])
    out.append(md_table(["app", "variant", "frames", "clicks", "matched", "misses", "extras", "latency ms", "jitter ms",
                         "lock %", "frame error", "drift ms/min", "note"], rows))
    live = [[x["app"], m, s["frames"], "%.1f" % s["fps"], "%.1f" % s["p50_ms"], "%.1f" % s["p95_ms"], "%.1f" % s["p99_ms"],
             "%.1f" % s["drop_pct"]] for x in results for m, s in x.get("live", {}).items()]
    if live:
        out += ["", md_table(["app", "mode", "frames", "fps", "p50 ms", "p95 ms", "p99 ms", "drop %"], live)]
    for x in results:
        for e in x.get("errors", []):
            out.append("- %s: %s" % (x["app"], e))
    out += [""] + [q for x in results for q in quality_rows(x)]
    return "\n".join(out)


def save(d, res):
    with open(os.path.join(d, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(d, "quality.txt"), "w") as f:
        f.write("\n".join(quality_rows(res)) + "\n")


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("av_bench")
    d = tempfile.mkdtemp(prefix="av")
    try:
        wav = os.path.join(d, "loop.wav")
        loop_wav(wav)
        with wave.open(wav) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32767
        on = onset_times(x, SR)
        t.check(len(on) == 8 and abs(on[1] - BEAT_S) < 1e-4, "loop.wav: 8 clicks %.4f s apart (want %.4f)" % (on[1] - on[0] if len(on) > 1 else 0, BEAT_S))
        t.check(len(rb.click_times(x, SR)) < 8, "render_bench's 0.5 s click merge would drop beats at 128 BPM (why av_bench has its own)")
        # synthetic 30 fps movie: flash 2 frames after the first frame at/after each click, 32 beats
        fps = 30
        onsets = [b * BEAT_S for b in range(32)]
        flashes = [(math.ceil(o * fps - 1e-6) + 2) / fps for o in onsets]
        s = av_stats(onsets, flashes, fps)
        t.check(s["matched"] == 32 and s["misses"] == 0 and s["extras"] == 0, "32 clicks, 32 flashes paired")
        t.check(s["frame_error"] == {"2": 32} and s["lock_pct"] == 0, "2 frames late everywhere: lock 0%")
        t.check(55 < s["latency_ms"] < 100 and s["jitter_ms"] < 20 and abs(s["drift_ms_min"]) < 5, "latency %.1f ms, jitter %.1f" % (s["latency_ms"], s["jitter_ms"]))
        s = av_stats(onsets, [math.ceil(o * fps - 1e-6) / fps for o in onsets[:-2]] + [5.0 + 0.2], fps)
        t.check(s["lock_pct"] == 100 * 30 / 32 and s["misses"] == 2 and s["extras"] == 1 and s["early"] == 0, "best-case frames lock; 2 misses, 1 extra")
        f = frame_stats([i / 60 for i in range(60)] + [1.1] + [1.1 + i / 60 for i in range(1, 30)], 60)
        t.check(f["drop_pct"] > 0 and abs(f["p50_ms"] - 1000 / 60) < 0.1, "frame log: one 110 ms hitch counted as a drop, p50 16.7 ms")
        p = inf_patch("reactive", wav)
        t.check("aud fx 0 click" in p and "aud out 1 fx" in p and "mod flash fillOpacity an onset" in p, "reactive patch routes audio through the Stereo insert")
        t.check("aud out 1 click" in inf_patch("reactive-file", wav) and "mod(t * 2.13333, 1)" in inf_patch("clock", wav), "reactive-file and clock wiring")
        rep = report([{"app": "Infinite", "variants": {"reactive": dict(av_stats(onsets, flashes, fps), frames=1, want=1)}},
                      {"app": "TouchDesigner", "variants": {}, "live": {"scene": f}}])
        t.check('QUALITY id=av.react_latency_ms subject="Infinite"' in rep and 'QUALITY id=live.drop_pct subject="TouchDesigner"' in rep, "QUALITY rows")
        binp = infinite_bin()
        import subprocess
        if not binp or subprocess.run(["which", "swiftc"], capture_output=True).returncode != 0:
            t.skip("no Infinite build or swiftc: end-to-end")
        else:
            pf = os.path.join(d, "r.inf")
            with open(pf, "w") as fh:
                fh.write(inf_patch("reactive", wav))
            mv = os.path.join(d, "r.mp4")
            r = inf_render(binp, pf, mv, 3, 30, 60)
            s = analyse_movie(mv) if os.path.exists(mv) else {}
            t.check(r["frames"] == 90 and s.get("matched", 0) >= 6, "Infinite reactive 3 s: %s frames, %s of %s clicks flashed, latency %s ms"
                    % (r["frames"], s.get("matched"), s.get("clicks"), round(s.get("latency_ms", -1), 1)))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["infinite", "td-prep", "td", "movie", "frames", "analyse"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--mode", choices=["av", "scene"], default="av")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.cmd:
        ap.print_usage()
        return 2
    if a.cmd == "infinite":
        d = os.path.expanduser(a.dir or os.path.join(RE_OUTPUT, "av-bench", "Infinite"))
        try:
            res = run_infinite(d, a.seconds, a.fps)
        except RuntimeError as e:
            print("av_bench: %s" % e, file=sys.stderr)
            return 1
        save(d, res)
        write_out(report([res]), a.out)
        return 0
    if a.cmd in ("td-prep", "td"):
        d = os.path.expanduser(a.dir or os.path.join(RE_OUTPUT, "av-bench", "TD"))
        if a.cmd == "td-prep":
            td_prep(d, a.mode)
            return 0
        res = run_td(d)
        save(d, res)
        write_out(report([res]), a.out)
        return 0
    if a.cmd == "movie" and len(a.paths) == 1:
        print(json.dumps(analyse_movie(a.paths[0]), indent=1))
        return 0
    if a.cmd == "frames" and len(a.paths) == 1:
        with open(a.paths[0]) as f:
            j = json.load(f)
        print(json.dumps(frame_stats(j["frame_s"], j.get("cook_rate", 60)), indent=1))
        return 0
    if a.cmd != "analyse" or not a.paths:
        return 2
    results = []
    for p in a.paths:
        with open(os.path.join(os.path.expanduser(p), "results.json")) as f:
            results.append(json.load(f))
    write_out(report(results), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
