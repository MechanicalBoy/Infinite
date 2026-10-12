#!/usr/bin/env python3
"""re-survey au_oop: the cost of running an Audio Unit out of process (macOS's AU hosting service) vs in process.

Block A step 4 of docs/plans/re-survey/coverage.md (crash isolation). Logic hosts AUs through Apple's hosting
service; Bitwig runs plugins in its own child process; Live and Infinite load them in process. Any AU host can ask
for the service with kAudioComponentInstantiation_LoadOutOfProcess. This measures what that costs, per plugin and
block size, with au_oop.swift (Apple's public AudioToolbox API, built with swiftc):
  instantiate   time to a usable unit
  block wall    median / p99 / max time of one render call (the audio deadline is block/48 kHz)
  overruns      blocks slower than the deadline (a realtime host would drop out on each)
  CPU           this process + AUHostingService (out of process), per second of audio
  latency       what the unit reports (an IPC hop should add none)

Usage:
  python3 tools/re-survey/au_oop.py run ValhallaDelay "Pro-Q 4" [--frames 64,128,256] [--seconds 20] [--runs 3] [--out t.md]
  python3 tools/re-survey/au_oop.py --self-test
Exit: 0 ok, 1 a render failed / self-test failed, 2 usage error or no swiftc.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SWIFT = os.path.join(HERE, "au_oop.swift")
BIN = os.path.join(RE_OUTPUT, "bin", "au_oop")
SERVICE = "AUHostingService"
SR = 48000


def build():
    """Compile au_oop.swift once into ~/re-output/bin (rebuilt when the source is newer)."""
    if os.path.exists(BIN) and os.path.getmtime(BIN) >= os.path.getmtime(SWIFT):
        return BIN
    ensure_dir(os.path.dirname(BIN))
    r = subprocess.run(["swiftc", "-O", SWIFT, "-o", BIN], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("au_oop: swiftc failed:\n" + r.stderr[-2000:])
    return BIN


def cputime(s):
    """ps TIME ('1:02.50' or '0:00.11') -> seconds."""
    m, _, sec = s.strip().rpartition(":")
    return (float(m) * 60 if m else 0.0) + float(sec)


def service_cpu():
    """Total CPU seconds of every AU hosting service process now alive, by pid."""
    out = subprocess.run(["ps", "-axo", "pid=,time=,comm="], capture_output=True, text=True).stdout
    got = {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and SERVICE in parts[2]:
            got[int(parts[0])] = cputime(parts[1])
    return got


def one(binp, au_id, mode, frames, seconds):
    _, typ, sub, manu = au_id.split(":")
    blocks = max(1, int(seconds * SR / frames))
    seen, stop = {}, threading.Event()

    def sample():  # the service may exit with the unit, so keep its last reading per pid
        while not stop.is_set():
            seen.update(service_cpu())
            time.sleep(0.1)

    before = service_cpu()
    th = threading.Thread(target=sample)
    th.start()
    try:
        r = subprocess.run([binp, typ, sub, manu, mode, str(frames), str(blocks)], capture_output=True, text=True,
                           timeout=seconds * 20 + 60)
    finally:
        stop.set()
        th.join()
    seen.update(service_cpu())
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "error": (r.stderr.strip() or "rc %d" % r.returncode)[-160:]}
    if mode == "out":
        d["cpu_service_s"] = sum(v - before.get(p, 0.0) for p, v in seen.items())
    return d


def measure(au_id, frames_list, seconds, runs, log=print):
    binp = build()
    rows = []
    for frames in frames_list:
        for mode in ("in", "out"):
            best = None
            for _ in range(runs):  # keep the run with the lowest p99: the floor of what the mode costs
                d = one(binp, au_id, mode, frames, seconds)
                if not d.get("ok"):
                    best = d
                    break
                if best is None or d["block_ms_p99"] < best["block_ms_p99"]:
                    best = d
            best.update(mode=mode, frames=frames, id=au_id)
            rows.append(best)
            if best.get("ok"):
                cpu = (best["cpu_self_s"] + best.get("cpu_service_s", 0.0)) / best["audio_s"] * 100
                log("  %-22s %-3s %4d  inst %.2f s  block med %.3f p99 %.3f max %.2f ms (deadline %.2f)  cpu %.2f %%" % (
                    au_id, mode, frames, best["instantiate_s"], best["block_ms_median"], best["block_ms_p99"],
                    best["block_ms_max"], best["deadline_ms"], cpu))
            else:
                log("  %-22s %-3s %4d  FAILED %s" % (au_id, mode, frames, best.get("error") or best.get("first_error")))
    return rows


def to_markdown(results):
    L = ["# AU in process vs out of process (macOS AU hosting service)", "",
         "Generated by `tools/re-survey/au_oop.py`. One -12 dBFS 1 kHz sine rendered through the unit's render block "
         "at 48 kHz, best of N runs (lowest p99). CPU = this process + AUHostingService, % of one core per second of "
         "audio. Deadline = one block of audio; a render slower than that is a dropout in a realtime host.", ""]
    rows = []
    for name, rs in results:
        by = {(r["frames"], r["mode"]): r for r in rs}
        for frames in sorted({r["frames"] for r in rs}):
            i, o = by.get((frames, "in"), {}), by.get((frames, "out"), {})
            if not (i.get("ok") and o.get("ok")):
                rows.append((name, frames, "fail" if not i.get("ok") else "ok", "fail" if not o.get("ok") else "ok", "-", "-", "-", "-", "-", "-"))
                continue
            ci = i["cpu_self_s"] / i["audio_s"] * 100
            co = (o["cpu_self_s"] + o.get("cpu_service_s", 0.0)) / o["audio_s"] * 100
            rows.append((name, frames, "%.3f / %.3f" % (i["block_ms_median"], i["block_ms_p99"]),
                         "%.3f / %.3f" % (o["block_ms_median"], o["block_ms_p99"]),
                         "%.2f / %.2f" % (i["block_ms_max"], o["block_ms_max"]), "%d / %d of %d" % (i["overruns"], o["overruns"], i["blocks"]),
                         "%.2f" % i["deadline_ms"],
                         "%.2f -> %.2f" % (ci, co), "%.2f -> %.2f" % (i["instantiate_s"], o["instantiate_s"]),
                         "%g / %g" % (i["latency_s"], o["latency_s"])))
    L += [md_table(["Plugin", "Block", "In: med / p99 ms", "Out: med / p99 ms", "Max in / out ms", "Overruns in / out", "Deadline ms",
                    "CPU % in -> out", "Instantiate s in -> out", "Latency s in / out"], rows), ""]
    return "\n".join(L) + "\n"


def self_test():
    t = SelfTest("au_oop")
    t.check(cputime("0:00.11") == 0.11 and cputime("1:02.50") == 62.5, "ps TIME parsed")
    if subprocess.run(["which", "swiftc"], capture_output=True).returncode != 0:
        t.skip("no swiftc: the AUDelay render is not run")
        return t.done()
    rs = measure("au:aufx:dely:appl", [128], 1.0, 1, log=lambda m: None)
    ok = [r for r in rs if r.get("ok")]
    t.check(len(ok) == 2, "AUDelay renders in and out of process (%s)" % [(r.get("mode"), r.get("ok"), r.get("error")) for r in rs])
    t.check(all(r["peak"] > 0.05 for r in ok), "the sine comes through both ways (%s)" % [round(r["peak"], 3) for r in ok])
    t.check(any("cpu_service_s" in r for r in ok), "the hosting service's CPU is sampled out of process")
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("run")
    rp.add_argument("targets", nargs="+")
    rp.add_argument("--frames", default="64,128,256")
    rp.add_argument("--seconds", type=float, default=20.0)
    rp.add_argument("--runs", type=int, default=3)
    rp.add_argument("--out")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd != "run":
        ap.print_usage(sys.stderr)
        return 2
    aus = pp.list_aus()
    frames = [int(x) for x in a.frames.split(",")]
    results, failed = [], False
    for t in a.targets:
        try:
            tg = pp.resolve(t, aus)
        except ValueError as e:
            print("au_oop: %s" % e, file=sys.stderr)
            return 2
        if tg["kind"] != "au":
            print("au_oop: %s is not an AU effect" % t, file=sys.stderr)
            return 2
        rs = measure(tg["id"], frames, a.seconds, a.runs, log=lambda m: print(m, file=sys.stderr))
        failed |= any(not r.get("ok") for r in rs)
        results.append((tg["name"], rs))
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "au-oop", time.strftime("%Y%m%d-%H%M%S")))
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=1)
    write_out(to_markdown(results), a.out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
