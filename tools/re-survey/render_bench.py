#!/usr/bin/env python3
"""re-survey render_bench: offline video render speed, codec quality and AV sync, Infinite against Blender and
TouchDesigner.

Two matched scenes, each at 720p, 1080p and 4K, 60 fps (TouchDesigner: 720p only, its non-commercial limit):
  instanced -> 10,000 cubes instanced on a 100x100 grid, the grid spinning (Infinite: Distribute Points in Grid
               -> Instance on Points -> Transform -> Render 3D; Blender: geometry nodes, EEVEE)
  blur      -> 900 cubes plus four Gaussian blurs of radius 20 after the render (Blender: compositor blurs)
The scenes match in content and cost, not pixel for pixel: each app lights and shades its own way.

  speed    -> fps of a full movie render (render + encode), as the slope between a short and a long render so
              startup does not count; H264 and ProRes 4444. Blender also: render-only seconds per still.
  quality  -> PSNR and SSIM (luma) of each app's own H264 against its own lossless PNGs of the same frames,
              plus the bitrate it chose. Measures the encoder settings a user gets by default.
  sync     -> a 1 s flash (3 frames white on black) with a 5 ms click on every second, 10 minutes, H264 + AAC.
              Reads every flash and every click back out of the file: offset and drift of audio against picture.

Movies are read with tools/re-survey/video_read.swift (AVFoundation, macOS's own decoder). Blender runs headless
(-b --factory-startup) on render_bench_blender.py, public bpy API only.

Usage:
  python3 tools/re-survey/render_bench.py infinite [--dir ~/re-output/render-bench/Infinite] [--sync-seconds 600]
  python3 tools/re-survey/render_bench.py blender  [--dir ~/re-output/render-bench/Blender] [--sync-seconds 600]
  python3 tools/re-survey/render_bench.py td-prep  # writes click.wav, prints the line to paste in TD's Textport
  python3 tools/re-survey/render_bench.py td       # after TD prints 'BENCH done' (render_bench_td.py)
  python3 tools/re-survey/render_bench.py sync <movie>                  # analyse any flash+click movie
  python3 tools/re-survey/render_bench.py analyse <dir> ... [--out results.md]
  python3 tools/re-survey/render_bench.py --self-test
Exit: 0 ok, 1 a render failed / self-test failed, 2 usage error or no swiftc.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HERE, RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, quality_line, run, write_out  # noqa: E402

SWIFT = os.path.join(HERE, "video_read.swift")
VR_BIN = os.path.join(RE_OUTPUT, "bin", "video_read")
BL_SCRIPT = os.path.join(HERE, "render_bench_blender.py")
BLENDER = os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")
SCENES = ["instanced", "blur"]
SIZES = [(1280, 720), (1920, 1080), (3840, 2160)]  # 720p: the largest TouchDesigner non-commercial renders
FPS = 60
SHORT_S, LONG_S = 1.0, 3.0          # speed slope: two movie lengths, seconds
QUALITY_FRAMES = 30
SYNC_FPS = 30
SR = 48000


def build_reader():
    if os.path.exists(VR_BIN) and os.path.getmtime(VR_BIN) >= os.path.getmtime(SWIFT):
        return VR_BIN
    ensure_dir(os.path.dirname(VR_BIN))
    r = subprocess.run(["swiftc", "-O", SWIFT, "-o", VR_BIN], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("render_bench: swiftc failed:\n" + r.stderr[-2000:])
    return VR_BIN


def vr(*args, timeout=900):
    rc, out, err = run([build_reader()] + list(args), timeout=timeout)
    if rc != 0:
        raise RuntimeError("video_read %s: %s" % (args[0], err.strip()))
    return out


def movie_info(path):
    return json.loads(vr("info", path).strip().splitlines()[-1])


def movie_luma(path):
    a = np.array([[float(v) for v in ln.split()] for ln in vr("luma", path).splitlines() if ln.strip()])
    return a[:, 0], a[:, 1]


def movie_audio(path):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "a.f32")
        meta = json.loads(vr("audio", path, f).strip().splitlines()[-1])
        x = np.fromfile(f, np.float32).reshape(-1, max(meta["channels"], 1))
    return x.mean(axis=1), meta["sr"]


def movie_frames(path, idx):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "f.raw")
        meta = json.loads(vr("frames", path, f, ",".join(str(i) for i in idx)).strip().splitlines()[-1])
        raw = np.fromfile(f, np.uint8).reshape(meta["frames"], meta["height"], meta["width"], 4)
    return [bgra_luma(fr) for fr in raw]


def bgra_luma(a):
    a = a.astype(np.float64)
    return 0.0722 * a[..., 0] + 0.7152 * a[..., 1] + 0.2126 * a[..., 2]


def png_luma(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


# ---------------------------------------------------------------- picture metrics

def psnr(a, b):
    mse = np.mean((a - b) ** 2)
    return 99.0 if mse <= 1e-12 else 10 * np.log10(255.0 ** 2 / mse)


def ssim(a, b, k=8):
    """Mean SSIM over non-overlapping k x k blocks of luma (0..255)."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    A = a[:h, :w].reshape(h // k, k, w // k, k).swapaxes(1, 2).reshape(-1, k * k)
    B = b[:h, :w].reshape(h // k, k, w // k, k).swapaxes(1, 2).reshape(-1, k * k)
    ma, mb = A.mean(1), B.mean(1)
    va, vb = A.var(1), B.var(1)
    cov = ((A - ma[:, None]) * (B - mb[:, None])).mean(1)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    return float(np.mean((2 * ma * mb + c1) * (2 * cov + c2) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2))))


# ---------------------------------------------------------------- sync analysis

def flash_times(t, luma):
    """Presentation time of every dark->bright edge."""
    thr = (luma.max() + luma.min()) / 2
    on = luma > thr
    return [float(t[i]) for i in range(len(on)) if on[i] and (i == 0 or not on[i - 1])]


def click_times(x, sr):
    thr = 0.25 * np.max(np.abs(x)) if len(x) else 1
    e = np.abs(x) > thr
    idx = np.flatnonzero(e[1:] & ~e[:-1]) + 1
    if len(e) and e[0]:
        idx = np.insert(idx, 0, 0)
    keep = np.insert(np.diff(idx) > sr // 2, 0, True) if len(idx) else idx
    return [float(i) / sr for i in idx[keep]]


def sync_stats(flashes, clicks, frame_s):
    """Pair each flash with the nearest click; offset = audio minus picture (positive = sound late)."""
    if not flashes or not clicks:
        return {"pairs": 0, "flashes": len(flashes), "clicks": len(clicks)}
    c = np.array(clicks)
    off, ft = [], []
    for f in flashes:
        j = int(np.argmin(np.abs(c - f)))
        if abs(c[j] - f) < 0.5:
            off.append(c[j] - f)
            ft.append(f)
    off, ft = np.array(off) * 1000, np.array(ft)
    slope = float(np.polyfit(ft, off, 1)[0]) * 60 if len(off) > 2 else 0.0   # ms per minute
    return {"pairs": len(off), "flashes": len(flashes), "clicks": len(clicks),
            "offset_ms": float(np.median(off)), "first_ms": float(off[0]), "last_ms": float(off[-1]),
            "spread_ms": float(off.max() - off.min()), "drift_ms_per_min": slope,
            "within_frame": bool(np.all(np.abs(off) <= frame_s * 1000 + 0.5))}


def analyse_sync(path):
    info = movie_info(path)
    t, l = movie_luma(path)
    x, sr = movie_audio(path)
    s = sync_stats(flash_times(t, l), click_times(x, sr), 1.0 / max(info.get("fps", SYNC_FPS), 1))
    s.update({"video_s": info.get("video_s"), "audio_s": info.get("audio_s"), "frames": info.get("frames"),
              "audio_codec": info.get("audio_codec"), "length_gap_ms": 1000 * ((info.get("audio_s") or 0) - (info.get("video_s") or 0))})
    return s


def click_wav(path, seconds):
    n = SR * seconds
    x = np.zeros(n, np.float32)
    burst = (0.8 * np.sin(2 * np.pi * 1000 * np.arange(240) / SR)).astype(np.float32)
    for s in range(seconds):
        x[s * SR:s * SR + 240] = burst
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


# ---------------------------------------------------------------- Infinite

def inf_scene(scene, w, h):
    n = 100 if scene == "instanced" else 30
    lines = ["infinite-patch 1",
             "node 1 3D Distribute Points in Grid", "  id grid", "  i countX %d" % n, "  i countY %d" % n,
             "  f spacingX %g" % (10.0 / n), "  f spacingY %g" % (10.0 / n), "  f pointSize 1", "end",
             "node 2 3D Cube", "  id cube", "end",
             "node 3 3D Instance on Points", "  id inst", "  i maxPoints %d" % (n * n),
             "  f instanceScale 0.06", "  f scaleRandom 0", "  f rotationRandom 0", "end",
             "node 4 3D Transform", "  id spin", "end",
             "node 5 Modulators LFO", "  id lfo", "end",
             "node 6 3D Render 3D", "  id r3d", "  f width %d" % w, "  f height %d" % h, "  f camDistance 12", "end",
             "node 7 Utility Output", "  id out", "end"]
    last = "r3d"
    if scene == "blur":
        for i in range(4):
            lines += ["node %d Effects gaussianblur" % (8 + i), "  id blur%d" % i, "  f uRadius 20", "end"]
    lines += ["geo inst cloud grid", "geo inst shape cube", "geo spin geo inst", "geo r3d geo_a spin",
              "mod spin rotZ lfo 0 0 1 0.5"]
    if scene == "blur":
        for i in range(4):
            lines.append("cable blur%d 0 %s" % (i, last))
            last = "blur%d" % i
    lines.append("cable out 0 %s" % last)
    return "\n".join(lines) + "\n"


def inf_sync_patch(wav):
    return "\n".join(["infinite-patch 1",
                      "node 1 Source Shape", "  id flash", "  f width 320", "  f height 180", "  f size 1",
                      "  f sizeX 1", "  f sizeY 1", "  c bgColor 0 0 0", "  f bgOpacity 1", "end",
                      "node 2 Modulators Audio File", "  id click", "  s path %s" % wav, "  b loop 0", "end",
                      "node 3 Utility Output", "  id out", "  b includeAudio 1", "end",
                      "cable out 0 flash", "aud out 1 click",
                      "expr flash fillOpacity mod(t, 1) < 0.1"]) + "\n"


def inf_render(binp, patch, movie, seconds, fps, codec):
    t0 = time.perf_counter()
    rc, out, err = run([binp, "--render", patch, movie, "--duration", "%g" % seconds, "--fps", str(fps),
                        "--codec", codec, "--timeout", "3000"], timeout=3600)
    wall = time.perf_counter() - t0
    st = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    if rc != 0 or not st.get("ok"):
        raise RuntimeError("Infinite render failed (%d): %s" % (rc, (st.get("errors") or err)[:400]))
    return wall, st.get("frames", 0)


def run_infinite(d, sync_s):
    binp = infinite_bin()
    if not binp:
        raise SystemExit("render_bench: no Infinite build (set INFINITE_BIN)")
    ensure_dir(d)
    res = {"app": "Infinite", "speed": {}, "quality": {}, "sync": None}
    for scene in SCENES:
        for w, h in SIZES:
            key = "%s_%dp" % (scene, h)
            patch = os.path.join(d, key + ".inf")
            with open(patch, "w") as f:
                f.write(inf_scene(scene, w, h))
            for codec, ext in (("h264", "mp4"), ("prores4444", "mov")):
                (t1, n1), (t2, n2) = [inf_render(binp, patch, os.path.join(d, "%s_%s_%g.%s" % (key, codec, s, ext)), s, FPS, codec)
                                      for s in (SHORT_S, LONG_S)]
                res["speed"]["%s/%s" % (key, codec)] = {"fps": (n2 - n1) / max(t2 - t1, 1e-6), "frames": [n1, n2], "wall_s": [t1, t2]}
                print("Infinite %s %s: %.1f fps" % (key, codec, res["speed"]["%s/%s" % (key, codec)]["fps"]))
            movie = os.path.join(d, "%s_h264_%g.mp4" % (key, LONG_S))
            pngs = os.path.join(d, key + "_png")
            shutil.rmtree(pngs, ignore_errors=True)
            rc, out, err = run([binp, "--frames-dir", patch, pngs, "--duration", "%g" % (QUALITY_FRAMES / FPS), "--fps", str(FPS)], timeout=1800)
            files = sorted(f for f in os.listdir(pngs) if f.endswith(".png")) if os.path.isdir(pngs) else []
            res["quality"][key] = quality(movie, [os.path.join(pngs, f) for f in files])
            shutil.rmtree(pngs, ignore_errors=True)
    if sync_s:
        wav = os.path.join(d, "click.wav")
        click_wav(wav, sync_s)
        patch = os.path.join(d, "sync.inf")
        with open(patch, "w") as f:
            f.write(inf_sync_patch(wav))
        movie = os.path.join(d, "sync_%ds.mp4" % sync_s)
        inf_render(binp, patch, movie, sync_s, SYNC_FPS, "h264")
        res["sync"] = analyse_sync(movie)
        os.remove(wav)
    return res


# ---------------------------------------------------------------- Blender

def bl_run(job, scene, w, h, n, out, timeout=7200):
    t0 = time.perf_counter()
    rc, so, se = run([BLENDER, "-b", "--factory-startup", "--python", BL_SCRIPT, "--", job, scene, str(w), str(h), str(n), out], timeout=timeout)
    wall = time.perf_counter() - t0
    bench = [json.loads(ln[6:]) for ln in so.splitlines() if ln.startswith("BENCH ")]
    if rc != 0 or not bench:
        raise RuntimeError("Blender %s failed (%d): %s" % (job, rc, (se or so)[-600:]))
    return wall, bench[-1]


def run_blender(d, sync_s):
    if not os.access(BLENDER, os.X_OK):
        raise SystemExit("render_bench: no Blender at %s (set BLENDER_BIN)" % BLENDER)
    ensure_dir(d)
    res = {"app": "Blender", "speed": {}, "quality": {}, "stills": {}, "sync": None}
    n1, n2 = int(SHORT_S * FPS), int(LONG_S * FPS)
    for scene in SCENES:
        for w, h in SIZES:
            key = "%s_%dp" % (scene, h)
            for codec, ext in (("h264", "mp4"), ("prores4444", "mov")):
                t1 = bl_run("movie", scene, w, h, n1, os.path.join(d, "%s_%s_%d.%s" % (key, codec, n1, ext)))[0]
                t2 = bl_run("movie", scene, w, h, n2, os.path.join(d, "%s_%s_%d.%s" % (key, codec, n2, ext)))[0]
                res["speed"]["%s/%s" % (key, codec)] = {"fps": (n2 - n1) / max(t2 - t1, 1e-6), "frames": [n1, n2], "wall_s": [t1, t2]}
                print("Blender %s %s: %.1f fps" % (key, codec, res["speed"]["%s/%s" % (key, codec)]["fps"]))
            st = os.path.join(d, key + "_stills")
            ensure_dir(st)
            fs = bl_run("stills", scene, w, h, 10, st)[1]["frame_s"]
            res["stills"][key] = {"median_s": float(np.median(fs[1:])), "first_s": fs[0]}
            shutil.rmtree(st, ignore_errors=True)
            pngs = ensure_dir(os.path.join(d, key + "_png"))
            bl_run("pngseq", scene, w, h, QUALITY_FRAMES, pngs)
            movie = os.path.join(d, "%s_q.mp4" % key)
            bl_run("movie", scene, w, h, QUALITY_FRAMES, movie)
            res["quality"][key] = quality(movie, sorted(os.path.join(pngs, f) for f in os.listdir(pngs) if f.endswith(".png")))
            shutil.rmtree(pngs, ignore_errors=True)
    if sync_s:
        wav = os.path.join(d, "click.wav")
        click_wav(wav, sync_s)
        movie = os.path.join(d, "sync_%ds.mp4" % sync_s)
        bl_run("sync", wav, 320, 180, sync_s, movie)
        res["sync"] = analyse_sync(movie)
        os.remove(wav)
    return res


# ---------------------------------------------------------------- TouchDesigner (owner-run, no headless mode)

TD_SCRIPT = os.path.join(HERE, "render_bench_td.py")


def td_prep(d, sync_s):
    ensure_dir(d)
    click_wav(os.path.join(d, "click.wav"), sync_s)
    print("In a new TouchDesigner project open Dialogs > Textport and paste:\n")
    print("import os; os.environ['RB_TD_SYNC_S'] = '%d'; exec(open(%r).read(), globals())\n" % (sync_s, TD_SCRIPT))
    print("Wait for 'BENCH done' (~%d min), then: python3 %s td" % (sync_s // 60 + 1, os.path.relpath(__file__)))


def run_td(d):
    with open(os.path.join(d, "td_bench.json")) as f:
        tb = json.load(f)
    res = {"app": "TouchDesigner", "version": tb.get("version"), "speed": {}, "quality": {}, "sync": None}
    for scene in SCENES:
        j = tb["jobs"].get(scene)
        if j:  # Movie File Out in non-realtime mode: frames over wall time, no slope (one length only)
            res["speed"]["%s_720p/h264" % scene] = {"fps": j["fps"], "frames": [j["frames"]], "wall_s": [j["wall_s"]]}
            res["quality"]["%s_720p" % scene] = {"error": "no lossless reference from TD"}
    if tb["jobs"].get("sync"):
        res["sync"] = analyse_sync(tb["jobs"]["sync"]["movie"])
    wav = os.path.join(d, "click.wav")
    if os.path.exists(wav):
        os.remove(wav)
    return res


# ---------------------------------------------------------------- quality and report

def quality(movie, pngs):
    if not pngs:
        return {"error": "no lossless frames"}
    info = movie_info(movie)
    idx = [i for i in (0, len(pngs) // 2, len(pngs) - 1)]
    got = movie_frames(movie, idx)
    ps, ss = [], []
    for i, fr in zip(idx, got):
        ref = png_luma(pngs[i])
        if ref.shape != fr.shape:
            return {"error": "size mismatch %s vs %s" % (ref.shape, fr.shape)}
        ps.append(psnr(ref, fr))
        ss.append(ssim(ref, fr))
    return {"psnr_db": float(np.mean(ps)), "ssim": float(np.mean(ss)), "kbps": info.get("video_kbps"),
            "codec": info.get("codec"), "size": [info.get("width"), info.get("height")]}


def report(results):
    out = ["# render_bench results", ""]
    keys = sorted({k for r in results for k in r["speed"]})
    out += ["## Movie render speed (fps, render + encode, slope %g s -> %g s at %d fps)" % (SHORT_S, LONG_S, FPS), "",
            md_table(["Scene / codec"] + [r["app"] for r in results],
                     [[k] + ["%.1f" % r["speed"][k]["fps"] if k in r["speed"] else "" for r in results] for k in keys]), ""]
    qk = sorted({k for r in results for k in r["quality"]})
    out += ["## H264 quality against the app's own lossless frames (luma)", "",
            md_table(["Scene"] + ["%s %s" % (r["app"], c) for r in results for c in ("PSNR dB", "SSIM", "Mbit/s")],
                     [[k] + [v for r in results for v in (
                         ("%.1f" % r["quality"][k]["psnr_db"], "%.4f" % r["quality"][k]["ssim"], "%.1f" % ((r["quality"][k]["kbps"] or 0) / 1000))
                         if "psnr_db" in r["quality"].get(k, {}) else (r["quality"].get(k, {}).get("error", ""), "", ""))] for k in qk]), ""]
    st = [r for r in results if r.get("stills")]
    if st:
        out += ["## Blender render-only seconds per still (median of frames 2-10)", "",
                md_table(["Scene", "s/frame", "first frame s"], [[k, "%.3f" % v["median_s"], "%.2f" % v["first_s"]] for r in st for k, v in sorted(r["stills"].items())]), ""]
    sy = [r for r in results if r.get("sync")]
    if sy:
        out += ["## AV sync (audio minus picture, positive = sound late)", "",
                md_table(["App", "Pairs", "Offset ms", "First / last ms", "Drift ms/min", "Spread ms", "Audio - video length ms", "Within a frame"],
                         [[r["app"], "%d/%d" % (r["sync"].get("pairs", 0), r["sync"].get("flashes", 0)),
                           "%.2f" % r["sync"].get("offset_ms", float("nan")),
                           "%.2f / %.2f" % (r["sync"].get("first_ms", float("nan")), r["sync"].get("last_ms", float("nan"))),
                           "%.3f" % r["sync"].get("drift_ms_per_min", float("nan")), "%.2f" % r["sync"].get("spread_ms", float("nan")),
                           "%.1f" % r["sync"].get("length_gap_ms", float("nan")), r["sync"].get("within_frame")] for r in sy]), ""]
    return "\n".join(out + quality_rows(results))


def quality_rows(results):
    """QUALITY rows for the scoreboard: render speed, H264 fidelity and sync, one subject per app and scene."""
    q = []
    for r in results:
        q += [quality_line("render.movie_fps", "%s: %s" % (r["app"], k), v["fps"]) for k, v in sorted(r["speed"].items()) if "fps" in v]
        q += [quality_line("render.h264_psnr_db", "%s: %s" % (r["app"], k), v["psnr_db"]) for k, v in sorted(r["quality"].items()) if "psnr_db" in v]
        if r.get("sync") and "offset_ms" in r["sync"]:
            q.append(quality_line("render.sync_offset_ms", r["app"], abs(r["sync"]["offset_ms"])))
            q.append(quality_line("render.sync_drift_ms_min", r["app"], abs(r["sync"].get("drift_ms_per_min", 0.0))))
    return q


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("render_bench")
    rng = np.random.default_rng(1)
    a = rng.uniform(0, 255, (64, 96))
    t.check(psnr(a, a) == 99.0 and abs(ssim(a, a) - 1) < 1e-9, "identical frames: PSNR 99, SSIM 1")
    noisy = np.clip(a + rng.normal(0, 5, a.shape), 0, 255)
    t.check(30 < psnr(a, noisy) < 36, "sigma-5 noise reads %.1f dB PSNR (want ~34)" % psnr(a, noisy))
    t.check(ssim(a, noisy) < ssim(a, np.clip(a + rng.normal(0, 1, a.shape), 0, 255)), "SSIM falls with more noise")
    # synthetic movie: 30 fps, flash on each second; clicks 12 ms late plus 0.5 ms/min drift
    ts = np.arange(0, 120, 1 / 30)
    luma = np.where(np.mod(ts, 1) < 0.1, 1.0, 0.0)
    x = np.zeros(SR * 120, np.float32)
    for s in range(120):
        i = int((s + 0.012 + s * 0.5e-3 / 60) * SR)
        x[i:i + 240] = 0.8
    s = sync_stats(flash_times(ts, luma), click_times(x, SR), 1 / 30)
    t.check(s["pairs"] == 120, "120 flash/click pairs")
    t.check(abs(s["offset_ms"] - 12.5) < 0.6 and abs(s["drift_ms_per_min"] - 0.5) < 0.05,
            "offset %.2f ms, drift %.3f ms/min (want ~12.5, 0.5)" % (s["offset_ms"], s["drift_ms_per_min"]))
    t.check(s["within_frame"], "12 ms is within one 33 ms frame")
    p = inf_scene("blur", 1920, 1080)
    t.check("cable out 0 blur3" in p and p.count("gaussianblur") == 4 and "i countX 30" in p, "blur scene wiring")
    binp = infinite_bin()
    if subprocess.run(["which", "swiftc"], capture_output=True).returncode != 0 or not binp:
        t.skip("no swiftc or no Infinite build: end-to-end sync")
        return t.done()
    d = tempfile.mkdtemp(prefix="rb")
    try:
        wav = os.path.join(d, "click.wav")
        click_wav(wav, 4)
        patch = os.path.join(d, "sync.inf")
        with open(patch, "w") as f:
            f.write(inf_sync_patch(wav))
        movie = os.path.join(d, "s.mp4")
        inf_render(binp, patch, movie, 4, SYNC_FPS, "h264")
        s = analyse_sync(movie)
        t.check(s["pairs"] == 4 and abs(s["offset_ms"]) < 2, "Infinite 4 s movie: %d pairs, offset %.2f ms" % (s["pairs"], s.get("offset_ms", 99)))
        q = os.path.join(d, "q.inf")
        with open(q, "w") as f:
            f.write(inf_scene("blur", 320, 180))
        qm = os.path.join(d, "q.mp4")
        inf_render(binp, q, qm, 0.5, FPS, "h264")
        rc, _, _ = run([binp, "--frames-dir", q, os.path.join(d, "png"), "--duration", "0.5", "--fps", str(FPS)], timeout=300)
        pngs = sorted(os.path.join(d, "png", f) for f in os.listdir(os.path.join(d, "png")) if f.endswith(".png"))
        r = quality(qm, pngs)
        t.check(r.get("psnr_db", 0) > 30 and r.get("ssim", 0) > 0.9, "H264 against own PNGs: %.1f dB, SSIM %.3f" % (r.get("psnr_db", 0), r.get("ssim", 0)))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["infinite", "blender", "td-prep", "td", "sync", "analyse"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--sync-seconds", type=int, default=600)
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.cmd:
        ap.print_usage()
        return 2
    if a.cmd in ("infinite", "blender"):
        d = os.path.expanduser(a.dir or os.path.join(RE_OUTPUT, "render-bench", "Infinite" if a.cmd == "infinite" else "Blender"))
        try:
            res = (run_infinite if a.cmd == "infinite" else run_blender)(d, a.sync_seconds)
        except RuntimeError as e:
            print("render_bench: %s" % e, file=sys.stderr)
            return 1
        with open(os.path.join(d, "results.json"), "w") as f:
            json.dump(res, f, indent=1)
        write_out(report([res]), a.out)
        return 0
    if a.cmd in ("td-prep", "td"):
        d = os.path.expanduser(a.dir or os.path.join(RE_OUTPUT, "render-bench", "TD"))
        if a.cmd == "td-prep":
            td_prep(d, a.sync_seconds)
            return 0
        res = run_td(d)
        with open(os.path.join(d, "results.json"), "w") as f:
            json.dump(res, f, indent=1)
        write_out(report([res]), a.out)
        return 0
    if a.cmd == "sync":
        if len(a.paths) != 1:
            return 2
        print(json.dumps(analyse_sync(a.paths[0]), indent=1))
        return 0
    if not a.paths:
        return 2
    results = []
    for p in a.paths:
        with open(os.path.join(os.path.expanduser(p), "results.json")) as f:
            results.append(json.load(f))
    write_out(report(results), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
