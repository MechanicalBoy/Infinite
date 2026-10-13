#!/usr/bin/env python3
"""re-survey latency_probe: real round-trip latency and jitter of any app, through a loopback device.

Block B step 2 of docs/plans/re-survey/coverage.md. latency_probe.swift plays a click every `period` seconds
into BlackHole and records BlackHole's input. The app under test uses BlackHole as its audio device and
monitors input straight to output at -6 dB (setup per app in PROTOCOL-latency.md). Each click then arrives
twice: direct, and once more a round trip later through the app. The gap is what the user would hear between
playing and hearing, minus the interface's own converters (there are none on a loopback). Compare it with the
latency the app reports in its preferences.

Usage:
  python3 tools/re-survey/latency_probe.py run "Live 64" [--device BlackHole] [--seconds 12] [--period 0.25]
  python3 tools/re-survey/latency_probe.py analyse rec.wav
  python3 tools/re-survey/latency_probe.py --self-test
Exit: 0 ok, 1 no echo found / self-test failed, 2 usage error, no swiftc, or no loopback device.
"""

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SWIFT = os.path.join(HERE, "latency_probe.swift")
BIN = os.path.join(RE_OUTPUT, "bin", "latency_probe")
DIRECT = 0.6   # of the loudest sample: the probe's own click (the device's volume scales everything)
ECHO = 0.16    # of the loudest sample: the app's copy at -6 dB is 0.5; its own repeat (0.25) comes later


def build():
    if os.path.exists(BIN) and os.path.getmtime(BIN) >= os.path.getmtime(SWIFT):
        return BIN
    ensure_dir(os.path.dirname(BIN))
    r = subprocess.run(["swiftc", "-O", SWIFT, "-o", BIN], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("latency_probe: swiftc failed:\n" + r.stderr[-2000:])
    return BIN


def analyse(x, sr, period):
    """Per click: samples from the direct arrival to the first arrival through the app."""
    x = np.abs(np.asarray(x, dtype=np.float64))
    if x.ndim > 1:
        x = x.max(axis=1)
    step = int(period * sr)
    top = float(x.max()) if len(x) else 0.0
    if top <= 1e-4:
        return {"ok": False, "clicks": 0}
    direct, echo = DIRECT * top, ECHO * top
    gaps, i, n = [], 0, len(x)
    while i < n:
        hit = np.flatnonzero(x[i:] > direct)
        if not len(hit):
            break
        d = i + int(hit[0])
        win = x[d + 4: d + int(step * 0.8)]
        e = np.flatnonzero(win > echo)
        if len(e):
            gaps.append(int(e[0]) + 4)
        i = d + int(step * 0.8)
    if not gaps:
        return {"ok": False, "clicks": 0}
    g = np.array(gaps, dtype=np.float64)
    ms = g / sr * 1000.0
    return {"ok": True, "clicks": len(gaps), "samples_median": float(np.median(g)), "ms_median": float(np.median(ms)),
            "ms_min": float(ms.min()), "ms_max": float(ms.max()), "jitter_ms": float(ms.max() - ms.min()),
            "sample_rate": sr}


def record(label, device, seconds, period, echo=0):
    binp = build()
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "latency", time.strftime("%Y%m%d")))
    wav = os.path.join(out_dir, "%s.wav" % "".join(c if c.isalnum() else "_" for c in label))
    r = subprocess.run([binp, device, "%g" % seconds, "%g" % period, wav] + ([str(echo)] if echo else []),
                       capture_output=True, text=True, timeout=seconds + 30)
    try:
        st = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        st = {"ok": False, "error": (r.stderr.strip() or "rc %d" % r.returncode)[-160:]}
    if not st.get("ok"):
        return st
    a, sr, _ = pp.read_wav(wav)
    res = analyse(a, sr, period)
    res.update(label=label, wav=wav)
    return res


def self_test():
    t = SelfTest("latency_probe")
    sr = 48000
    x = np.zeros(sr * 2)
    for k, gap in zip(range(2400, 2 * sr - 12000, 12000), [500, 503, 497, 500, 501, 499, 500]):
        x[k] = 0.5
        x[k + gap] = 0.25
        x[k + 2 * gap] = 0.125  # the app hearing its own output: a later, quieter repeat must not count
    r = analyse(x, sr, 0.25)
    t.check(r["ok"] and r["samples_median"] == 500 and r["clicks"] == 7, "synthetic gaps found (%s)" % r)
    t.check(abs(r["jitter_ms"] - 6 / 48.0) < 1e-9, "jitter is max - min (%.3f ms)" % r["jitter_ms"])
    t.check(not analyse(np.zeros(sr), sr, 0.25)["ok"], "silence finds no echo")
    if subprocess.run(["which", "swiftc"], capture_output=True).returncode != 0:
        t.skip("no swiftc: the loopback is not run")
        return t.done()
    have = subprocess.run(["system_profiler", "SPAudioDataType"], capture_output=True, text=True).stdout
    if "BlackHole" not in have:
        t.skip("no BlackHole device: the loopback is not run")
        return t.done()
    r = record("selftest", "BlackHole", 3.0, 0.25, echo=240)
    t.check(r.get("ok") and r["samples_median"] == 240, "a known 240-sample echo through BlackHole reads 240 (%s)" %
            {k: r.get(k) for k in ("ok", "samples_median", "clicks", "error")})
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("run")
    rp.add_argument("label")
    rp.add_argument("--device", default="BlackHole")
    rp.add_argument("--seconds", type=float, default=12.0)
    rp.add_argument("--period", type=float, default=0.25)
    rp.add_argument("--out")
    an = sub.add_parser("analyse")
    an.add_argument("wav")
    an.add_argument("--period", type=float, default=0.25)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "analyse":
        x, sr, _ = pp.read_wav(a.wav)
        r = analyse(x, sr, a.period)
    elif a.cmd == "run":
        r = record(a.label, a.device, a.seconds, a.period)
    else:
        ap.print_usage(sys.stderr)
        return 2
    if not r.get("ok"):
        print("latency_probe: no echo found (%s). Is the app monitoring %s input to output?" % (r.get("error", ""), a.__dict__.get("device", "the device")),
              file=sys.stderr)
        return 1
    row = [(r.get("label", a.__dict__.get("wav")), r["clicks"], "%.0f" % r["samples_median"], "%.2f" % r["ms_median"],
            "%.2f" % r["ms_min"], "%.2f" % r["ms_max"], "%.3f" % r["jitter_ms"])]
    write_out(md_table(["App / buffer", "Clicks", "Samples", "Median ms", "Min ms", "Max ms", "Jitter ms"], row) + "\n", a.__dict__.get("out"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
