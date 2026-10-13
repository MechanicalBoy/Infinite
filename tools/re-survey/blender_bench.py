#!/usr/bin/env python3
"""re-survey blender_bench: Blender beyond render. Geometry-node evaluation, cloth simulation stepping and
dependency-graph fps, against the matched Infinite patch run headless.

Three matched scenes (content and cost match, not pixels):
  instance -> a 100x100 grid of points, a small cube instanced on each (10,000 instances), instance scale animated
              every frame. Blender: geometry nodes Grid -> Instance on Points, Scene Time -> Scale.
              Infinite: Distribute Points in Grid -> Instance on Points (Cube), LFO -> instanceScale.
  subdiv   -> a 32x32-face grid, subdivided twice (smooth), displaced along the normal by an animated noise.
              Blender: Grid -> Subdivision Surface level 2 -> Set Position (normal x 4D noise, W = time).
              Infinite: Plane (detail 32) -> Subdivide (levels 2, smooth) -> Displacement (texture = animated Noise).
  cloth    -> a 32x32-face sheet hanging from its pinned top row, stepped frame by frame from rest.
              Blender: Cloth modifier, pin vertex group (stepping frame by frame is what Bake does).
              Infinite: Plane (detail 32) -> Cloth (pinMode top, defaults).

What each side measures:
  Blender  -> scene.frame_set(f) for every frame, timed inside Blender (blender_bench_blender.py, run headless
              with -b --factory-startup, public bpy API only). One full depsgraph evaluation per frame, nothing
              drawn. "depsgraph fps" = 1000 / median ms. That is the closest HEADLESS proxy for viewport fps:
              real viewport fps adds GPU drawing and overlays and needs the GUI (not measured here).
  Infinite -> ms per frame of an offline --render at 60 fps, as the slope between a 2 s and an 8 s render (startup
              does not count; each rendered twice, faster kept), at a tiny 128x72 so encode and raster are negligible. "net" subtracts the same
              slope for a bare Cube -> Render 3D baseline, leaving geometry evaluation + upload. Infinite always
              draws, so its number is an upper bound on its evaluation cost; Blender's draws nothing.

Usage:
  python3 tools/re-survey/blender_bench.py blender  [--dir ~/re-output/blender-bench/Blender] [--frames 120]
  python3 tools/re-survey/blender_bench.py infinite [--dir ~/re-output/blender-bench/Infinite]
  python3 tools/re-survey/blender_bench.py analyse <dir> ... [--out results.md]   # table + QUALITY rows
  python3 tools/re-survey/blender_bench.py --self-test
Each run writes results.json and quality.txt (QUALITY rows: geo.instance_ms, geo.subdiv_ms, sim.cloth_ms,
geo.eval_fps_*) in its dir. Exit: 0 ok, 1 a run failed / self-test failed, 2 usage error.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HERE, RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, quality_line, run, write_out  # noqa: E402

BL_SCRIPT = os.path.join(HERE, "blender_bench_blender.py")
BLENDER = os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")
SCENES = {"instance": 100, "subdiv": 32, "cloth": 32}     # scene -> size (grid points / faces per side)
FPS = 60
SHORT_S, LONG_S = 2.0, 8.0
REPEATS = 2                      # each length rendered twice, the faster kept (shared machine)
W, H = 128, 72
METRIC = {"instance": "geo.instance_ms", "subdiv": "geo.subdiv_ms", "cloth": "sim.cloth_ms"}


# ---------------------------------------------------------------- Infinite

def _r3d(geo_src):
    return ["node 90 3D Render 3D", "  id r3d", "  f width %d" % W, "  f height %d" % H, "  f camDistance 6", "end",
            "node 91 Utility Output", "  id out", "end", "geo r3d geo_a %s" % geo_src, "cable out 0 r3d"]


def inf_patch(scene, size=None):
    size = size or SCENES.get(scene, 32)
    L = ["infinite-patch 1"]
    if scene == "baseline":
        L += ["node 1 3D Cube", "  id cube", "end"] + _r3d("cube")
    elif scene == "instance":
        L += ["node 1 3D Distribute Points in Grid", "  id grid", "  i countX %d" % size, "  i countY %d" % size,
              "  f spacingX %g" % (10.0 / size), "  f spacingY %g" % (10.0 / size), "end",
              "node 2 3D Cube", "  id cube", "end",
              "node 3 3D Instance on Points", "  id inst", "  i maxPoints %d" % (size * size),
              "  f instanceScale 0.06", "  f scaleRandom 0", "  f rotationRandom 0", "end",
              "node 4 Modulators LFO", "  id lfo", "  f rateBeats 1", "end",
              "geo inst cloud grid", "geo inst shape cube", "mod inst instanceScale lfo 0 0 1 0.5 0.03 0.09"]
        L += _r3d("inst")
    elif scene == "subdiv":
        L += ["node 1 3D Plane", "  id plane", "  i detail %d" % size, "end",
              "node 2 3D Subdivide", "  id sub", "  i op 2", "  i levels 2", "  f smooth 1", "end",
              "node 3 Source Noise", "  id noise", "  f width 256", "  f height 256", "  f scale 6", "  f speed 0.2", "end",
              "node 4 3D Displacement", "  id disp", "  f strength 0.3", "end",
              "geo sub geo plane", "geo disp geo sub", "cable disp texture noise"]
        L += _r3d("disp")
    elif scene == "cloth":
        L += ["node 1 3D Plane", "  id plane", "  i detail %d" % size, "end",
              "node 2 3D Cloth", "  id cloth", "end", "geo cloth geo plane"]
        L += _r3d("cloth")
    else:
        raise ValueError(scene)
    return "\n".join(L) + "\n"


def inf_render(binp, patch, movie, seconds):
    t0 = time.perf_counter()
    rc, out, err = run([binp, "--render", patch, movie, "--duration", "%g" % seconds, "--fps", str(FPS),
                        "--codec", "h264", "--timeout", "110"], timeout=120)
    wall = time.perf_counter() - t0
    st = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    if st.get("elapsed_ms"):
        wall = st["elapsed_ms"] / 1000.0   # the render loop alone, without process launch
    want = int(round(seconds * FPS))
    if rc != 0 or not st.get("ok") or st.get("frames", 0) < want:
        raise RuntimeError("Infinite render failed (%d, %s frames of %d): %s" % (rc, st.get("frames"), want, (st.get("errors") or st.get("status") or err)[:300]))
    return wall, st["frames"]


def slope_ms(binp, d, scene):
    patch = os.path.join(d, scene + ".inf")
    with open(patch, "w") as f:
        f.write(inf_patch(scene))
    (t1, n1), (t2, n2) = [min(inf_render(binp, patch, os.path.join(d, "%s_%g.mp4" % (scene, s)), s) for _ in range(REPEATS))
                          for s in (SHORT_S, LONG_S)]
    for s in (SHORT_S, LONG_S):
        try:
            os.remove(os.path.join(d, "%s_%g.mp4" % (scene, s)))
        except OSError:
            pass
    return 1000.0 * (t2 - t1) / max(n2 - n1, 1), [n1, n2], [t1, t2]


def run_infinite(d):
    binp = infinite_bin()
    if not binp:
        raise RuntimeError("no Infinite build (set INFINITE_BIN)")
    ensure_dir(d)
    res = {"app": "Infinite", "scenes": {}, "method": "--render slope 2 s vs 8 s at %d fps, %dx%d, minus Cube baseline" % (FPS, W, H)}
    base, _, _ = slope_ms(binp, d, "baseline")
    res["baseline_ms"] = base
    print("Infinite baseline: %.2f ms/frame" % base)
    for scene, size in SCENES.items():
        ms, n, wall = slope_ms(binp, d, scene)
        res["scenes"][scene] = {"size": size, "gross_ms": ms, "net_ms": max(ms - base, 0.0), "frames": n, "wall_s": wall}
        print("Infinite %s: %.2f ms/frame gross, %.2f net" % (scene, ms, max(ms - base, 0.0)))
    return res


# ---------------------------------------------------------------- Blender

def bl_run(scene, size, frames, timeout=120):
    rc, so, se = run([BLENDER, "-b", "--factory-startup", "--python", BL_SCRIPT, "--", scene, str(size), str(frames)], timeout=timeout)
    bench = [json.loads(ln[6:]) for ln in so.splitlines() if ln.startswith("BENCH ")]
    if rc != 0 or not bench:
        raise RuntimeError("Blender %s failed (%d): %s" % (scene, rc, (se or so)[-600:]))
    return bench[-1]


def frame_stats(ms):
    """First frame apart (it builds caches); the rest gives median/p95."""
    a = np.array(ms[1:] if len(ms) > 1 else ms, float)
    med = float(np.median(a))
    return {"first_ms": float(ms[0]), "median_ms": med, "p95_ms": float(np.percentile(a, 95)),
            "mean_ms": float(a.mean()), "eval_fps": 1000.0 / med if med > 0 else 0.0}


def run_blender(d, frames):
    if not os.access(BLENDER, os.X_OK):
        raise RuntimeError("no Blender at %s (set BLENDER_BIN)" % BLENDER)
    ensure_dir(d)
    res = {"app": "Blender", "scenes": {}, "method": "scene.frame_set per frame, headless (no drawing); %d frames" % frames}
    for scene, size in SCENES.items():
        b = bl_run(scene, size, frames)
        res["version"] = b.get("version")
        s = frame_stats(b["frame_ms"])
        s.update({"size": size, "elements": b.get("elements", {}), "frame_ms": [round(x, 3) for x in b["frame_ms"]]})
        res["scenes"][scene] = s
        print("Blender %s: median %.2f ms, p95 %.2f ms (%.0f eval fps) %s" % (scene, s["median_ms"], s["p95_ms"], s["eval_fps"], s["elements"]))
    return res


# ---------------------------------------------------------------- report

def per_frame_ms(res, scene):
    s = res.get("scenes", {}).get(scene)
    if not s:
        return None
    return s.get("net_ms") if res["app"] == "Infinite" else s.get("median_ms")


def quality_rows(res):
    rows = []
    for scene in SCENES:
        v = per_frame_ms(res, scene)
        if v is not None:
            rows.append(quality_line(METRIC[scene], res["app"], v))
    return rows


def report(results):
    out = ["# blender_bench: geometry evaluation and simulation per frame", "",
           "Infinite: --render slope at %d fps, %dx%d, net of a Cube -> Render 3D baseline (includes drawing). "
           "Blender: depsgraph evaluation per frame, headless, nothing drawn. Lower is better. "
           "Blender's eval fps is a headless proxy; true viewport fps needs the GUI." % (FPS, W, H), ""]
    rows = []
    for scene, size in SCENES.items():
        r = [scene, size]
        inf = next((x for x in results if x["app"] == "Infinite"), None)
        bl = next((x for x in results if x["app"] == "Blender"), None)
        si = (inf or {}).get("scenes", {}).get(scene, {})
        sb = (bl or {}).get("scenes", {}).get(scene, {})
        r += ["%.2f" % si["gross_ms"] if si else "-", "%.2f" % si["net_ms"] if si else "-",
              "%.2f" % sb["median_ms"] if sb else "-", "%.2f" % sb["p95_ms"] if sb else "-",
              "%.2f" % sb["first_ms"] if sb else "-", "%.0f" % sb["eval_fps"] if sb else "-",
              json.dumps(sb.get("elements", {})) if sb else "-"]
        rows.append(r)
    out.append(md_table(["scene", "size", "Infinite ms gross", "Infinite ms net", "Blender median ms",
                         "Blender p95 ms", "Blender first ms", "Blender eval fps", "Blender elements"], rows))
    inf = next((x for x in results if x["app"] == "Infinite"), None)
    if inf:
        out += ["", "Infinite baseline (Cube -> Render 3D): %.2f ms/frame" % inf.get("baseline_ms", 0)]
    for x in results:
        if x.get("version"):
            out.append("%s %s" % (x["app"], x["version"]))
    out += [""] + [q for x in results for q in quality_rows(x)]
    return "\n".join(out)


def save(d, res):
    with open(os.path.join(d, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(d, "quality.txt"), "w") as f:
        f.write("\n".join(quality_rows(res)) + "\n")


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("blender_bench")
    p = inf_patch("instance")
    t.check("geo inst cloud grid" in p and "i maxPoints 10000" in p and "i countX 100" in p and "mod inst instanceScale lfo" in p,
            "instance patch: 100x100 grid, 10,000 instances, LFO on scale")
    p = inf_patch("subdiv")
    t.check("i levels 2" in p and "geo disp geo sub" in p and "cable disp texture noise" in p and "geo r3d geo_a disp" in p,
            "subdiv patch: Plane -> Subdivide 2 -> Displacement(Noise) -> Render 3D")
    t.check("geo cloth geo plane" in inf_patch("cloth") and "geo r3d geo_a cube" in inf_patch("baseline"), "cloth and baseline wiring")
    s = frame_stats([50.0, 2.0, 2.0, 4.0, 2.0])
    t.check(s["first_ms"] == 50 and s["median_ms"] == 2 and abs(s["eval_fps"] - 500) < 1e-6, "first frame kept apart, median 2 ms = 500 fps")
    fake = [{"app": "Infinite", "baseline_ms": 1, "scenes": {"cloth": {"gross_ms": 3, "net_ms": 2}}},
            {"app": "Blender", "scenes": {"cloth": {"median_ms": 4, "p95_ms": 5, "first_ms": 9, "eval_fps": 250, "elements": {}}}}]
    rep = report(fake)
    t.check('QUALITY id=sim.cloth_ms subject="Infinite" value=2.0000' in rep and 'subject="Blender" value=4.0000' in rep,
            "report emits QUALITY rows for both apps")
    binp = infinite_bin()
    if not binp:
        t.skip("no Infinite build: patch validation")
    else:
        d = tempfile.mkdtemp(prefix="bb")
        try:
            for scene in ("instance", "subdiv", "cloth", "baseline"):
                f = os.path.join(d, scene + ".inf")
                with open(f, "w") as fh:
                    fh.write(inf_patch(scene))
                rc, out, err = run([binp, "--validate", f], timeout=60)
                t.check(rc == 0, "Infinite --validate %s (%s)" % (scene, (out + err).strip().splitlines()[-1][:120] if (out + err).strip() else rc))
        finally:
            shutil.rmtree(d, ignore_errors=True)
    if not os.access(BLENDER, os.X_OK):
        t.skip("no Blender: end-to-end")
    else:
        try:
            b = bl_run("instance", 10, 5)
            t.check(len(b["frame_ms"]) == 5 and b["elements"].get("instances") == 100, "Blender 10x10 instance scene: 100 instances, 5 frames")
        except RuntimeError as e:
            t.check(False, str(e)[:200])
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["infinite", "blender", "analyse"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.cmd:
        ap.print_usage()
        return 2
    if a.cmd in ("infinite", "blender"):
        d = os.path.expanduser(a.dir or os.path.join(RE_OUTPUT, "blender-bench", "Infinite" if a.cmd == "infinite" else "Blender"))
        try:
            res = run_infinite(d) if a.cmd == "infinite" else run_blender(d, a.frames)
        except RuntimeError as e:
            print("blender_bench: %s" % e, file=sys.stderr)
            return 1
        save(d, res)
        write_out(report([res]), a.out)
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
