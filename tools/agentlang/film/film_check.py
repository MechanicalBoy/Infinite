#!/usr/bin/env python3
"""film_check.py SCENE [--dir FILM_DIR] [--times t1,t2,..] [--n 8] [--height 270] [--mp4 FILE --bpm N]

One call = build the scene, render cheap stills, lint, and print ONE JSON line. Raw output goes to
out/check/<scene>.log and is never printed. The agent reads the line, opens the one contact sheet if it
needs to look, and renders full size only when the owner asks.

Run with the film's own python: <film>/.venv/bin/python film_check.py act7
Checks: build errors (trimmed), beat-grid events, first-frame strength, dead stills, negative space,
9:16 safe-area ink (INF_ASPECT=9x16), optional finished-mp4 audit (film_audit.py findings).
"""
import argparse, importlib, json, os, subprocess, sys, time, traceback

ap = argparse.ArgumentParser()
ap.add_argument("scene")
ap.add_argument("--dir", default=os.path.expanduser(os.environ.get("FILM_DIR", "~/infinite-launch-video")))
ap.add_argument("--times", default=None)
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--height", type=int, default=270)
ap.add_argument("--mp4", default=None)
ap.add_argument("--bpm", type=float, default=None)
a = ap.parse_args()

D = os.path.abspath(a.dir)
os.chdir(D); sys.path.insert(0, D)
os.makedirs("out/check", exist_ok=True)
LOG = f"out/check/{a.scene}.log"
res = {"ok": True, "scene": a.scene, "errors": [], "warn": [], "log": os.path.join(D, LOG)}
logf = open(LOG, "w")


def fail(code, hint):
    res["ok"] = False
    res["errors"].append({"code": code, "hint": hint})


def tail(text, n=6):
    ls = [l.strip() for l in text.strip().splitlines() if l.strip()]
    where = [l for l in ls if l.startswith("File") and (D + "/scenes/" in l or D + "/lib/" in l)]
    return " | ".join(([where[-1]] if where else []) + ls[-1:])


# 1. build ---------------------------------------------------------------
try:
    from lib.core import BEAT, PORTRAIT
    from lib.cut import Warped
    mod = importlib.import_module(f"scenes.{a.scene}")
    cls = [v for v in vars(mod).values() if isinstance(v, type) and getattr(v, "name", None) == a.scene][0]
    scene = Warped(cls(), a.scene)
    t0, t1 = scene.t0, scene.t1
    evs = scene.events()
except Exception:
    tb = traceback.format_exc(); logf.write(tb)
    fail("E_BUILD", tail(tb)); print(json.dumps(res)); sys.exit(1)
res.update(t0=round(t0, 3), t1=round(t1, 3), events=len(evs), portrait=bool(PORTRAIT))

# 2. beat grid -----------------------------------------------------------
step, tol = BEAT / 4, 0.02
off = [e["t"] for e in evs if min(e["t"] % step, step - e["t"] % step) > tol]
res["off_grid"] = len(off)
if off:
    res["warn"].append(f"{len(off)} of {len(evs)} events off the 1/16 grid (first at {off[0]:.3f}s)")

# 3. stills --------------------------------------------------------------
ts = [float(x) for x in a.times.split(",")] if a.times else \
     [round(t0 + (t1 - t0) * (i + 0.5) / a.n, 3) for i in range(a.n)]
p = subprocess.run([sys.executable, "render.py", a.scene, "--height", str(a.height),
                    "--stills", ",".join(map(str, ts))], capture_output=True, text=True)
logf.write(p.stdout + p.stderr)
if p.returncode:
    fail("E_RENDER", tail(p.stderr or p.stdout)); print(json.dumps(res)); sys.exit(1)

import numpy as np
from PIL import Image, ImageDraw
pre = ("dark_" if os.environ.get("INF_THEME") == "dark" else "") + ("v_" if PORTRAIT else "")
rows, ims = [], []
for t in ts:
    im = Image.open(f"out/{pre}{a.scene}_still_{t:06.3f}.png").convert("RGB")
    arr = np.asarray(im).astype(np.int16)
    bg = np.median(arr.reshape(-1, 3), axis=0)
    ink = (np.abs(arr - bg).sum(axis=2) > 40)
    H, W = ink.shape
    r = {"t": t, "ink": round(float(ink.mean()), 3)}
    if PORTRAIT:
        z = np.zeros_like(ink)
        z[: int(H * .14)] = 1; z[int(H * .78):] = 1; z[int(H * .40):int(H * .78), int(W * .86):] = 1
        r["safe_ink"] = round(float((ink & z.astype(bool)).sum() / max(ink.sum(), 1)), 3)
    rows.append(r)
    d = ImageDraw.Draw(im, "RGBA")
    if PORTRAIT:
        red = (255, 60, 60, 70)
        d.rectangle([0, 0, W, H * .14], fill=red); d.rectangle([0, H * .78, W, H], fill=red)
        d.rectangle([W * .86, H * .40, W, H * .78], fill=red)
    d.text((6, 4), f"{t}", fill=(255, 0, 0))
    ims.append(im.resize((640, int(640 * H / W))))
res["stills"] = rows
if rows[0]["ink"] < 0.01 and t0 == ts[0]:
    res["warn"].append("first frame is empty")
dead = [r["t"] for r in rows if r["ink"] < 0.005]
if dead:
    res["warn"].append(f"{len(dead)} near-empty stills at {dead[:4]}")
if PORTRAIT:
    bad = [r["t"] for r in rows if r.get("safe_ink", 0) > 0.35]
    if bad:
        res["warn"].append(f"over 35% of ink under UI zones at {bad[:4]}")
cols = 2
w, h = ims[0].size
sheet = Image.new("RGB", (cols * w, ((len(ims) + 1) // cols) * h), "gray")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
res["sheet"] = os.path.join(D, f"out/check/{a.scene}_sheet.png")
sheet.save(res["sheet"])

# 4. finished mp4 audit --------------------------------------------------
if a.mp4:
    audit = os.path.expanduser("~/.claude/skills/film-direction/scripts/film_audit.py")
    q = subprocess.run([sys.executable, audit, a.mp4, "--bpm", str(a.bpm or 60 / BEAT)], capture_output=True, text=True)
    logf.write(q.stdout + q.stderr)
    fixes = [l.strip() for l in q.stdout.splitlines() if "FIX" in l]
    res["audit_fixes"] = len(fixes)
    res["audit_top"] = fixes[:5]
    if fixes:
        res["warn"].append(f"{len(fixes)} audit FIX lines")

logf.close()
res["warn"] = res["warn"][:6]
print(json.dumps(res))
sys.exit(0 if res["ok"] else 1)
