#!/usr/bin/env python3
"""Interleaved same-binary A/B of IMGAUDIT GPU times: legacy look vs new.

Runs the audit alternately with INFINITE_IMGAUDIT_LEGACY=1 and without,
`--pairs` times (default 6), waiting for the 1-minute load average to drop
below `--max-load` before each run, and prints the median (and the min, steadier when the GPU clock
switches state mid-run) ms per filter.

  python3 tools/imgaudit_ab.py bloom boxblur gaussianblur diffuseglow
  python3 tools/imgaudit_ab.py --pairs 6 --save /tmp/ab bloom

--save DIR also keeps every run's full output (for the SPEC lines).
"""
import argparse
import os
import re
import statistics
import subprocess
import sys
import time

BIN = "build/Infinite.app/Contents/MacOS/Infinite"
ROW = re.compile(r"^IMGAUDIT (\S+)\s+fmt .*\| gpu\s+([\d.]+) ms")


def load1():
    return os.getloadavg()[0]


def run(legacy, max_load):
    while load1() >= max_load:
        time.sleep(5)
    env = dict(os.environ, INFINITE_IMGAUDIT="1", INFINITE_EXITAFTER="1")
    env.pop("INFINITE_IMGAUDIT_LEGACY", None)
    if legacy:
        env["INFINITE_IMGAUDIT_LEGACY"] = "1"
    out = subprocess.run([BIN], env=env, capture_output=True, text=True, timeout=900).stdout
    times = {}
    for line in out.splitlines():
        m = ROW.match(line)
        if m:
            times[m.group(1)] = float(m.group(2))
    return out, times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("filters", nargs="*")
    ap.add_argument("--pairs", type=int, default=6)
    ap.add_argument("--max-load", type=float, default=6.0)
    ap.add_argument("--save")
    a = ap.parse_args()
    res = {"legacy": {}, "new": {}}
    for i in range(a.pairs):
        for kind in ("legacy", "new"):
            out, times = run(kind == "legacy", a.max_load)
            if a.save:
                os.makedirs(a.save, exist_ok=True)
                with open(os.path.join(a.save, f"{kind}_{i}.txt"), "w") as f:
                    f.write(out)
            for k, v in times.items():
                res[kind].setdefault(k, []).append(v)
        print(f"pair {i + 1}/{a.pairs} done", file=sys.stderr)
    names = a.filters or sorted(res["new"])
    print(f"{'filter':<18} {'legacy':>7} {'new':>7} {'change':>8} | {'min L':>6} {'min N':>6} {'change':>7}")
    for n in names:
        lo, nw = res["legacy"].get(n), res["new"].get(n)
        if not lo or not nw:
            print(f"{n:<18} missing")
            continue
        ml, mn = statistics.median(lo), statistics.median(nw)
        nl, nn = min(lo), min(nw)
        print(f"{n:<18} {ml:7.2f} {mn:7.2f} {100 * (mn - ml) / ml:+7.0f}% | {nl:6.2f} {nn:6.2f} {100 * (nn - nl) / nl:+6.0f}%")


if __name__ == "__main__":
    main()
