#!/usr/bin/env python3
"""re-survey loopback_rec: capture a DAW's master bus through a loopback device and trim it to t=0.

A DAW with no headless render is played once (Play, no Bounce dialog) with its output on BlackHole 2ch; this
records that device and cuts the take so the first sound of the stimulus sits exactly where a bounce would put
it. builtins_kit then analyses the file like any bounce.

  python3 tools/re-survey/loopback_rec.py rec <App> <Name> synth|fx [--seconds N]   # start, then press Play in the DAW
  python3 tools/re-survey/loopback_rec.py trim in.wav out.wav --first-at 1.0          # trim an existing capture
  python3 tools/re-survey/loopback_rec.py --self-test

Output: ~/re-output/builtins-kit/<App>/synth_<Name>.wav or fx_<Name>.wav, 48 kHz 24-bit stereo.
Set the DAW's output to the loopback device, buffer 256-512, master 0 dB, no limiter or dither, and the
loopback device at unity gain. Limits: the first sound is found by level (-54 dBFS), so a stimulus whose first
event is quieter than that, or an effect that pre-delays it, shifts the alignment; the report's latency
column then reads as zero. Exit: 0 ok, 1 nothing audible / ffmpeg failed / self-test failed, 2 usage error.
"""

import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir  # noqa: E402
import bounce_kit as bk  # noqa: E402
import plugin_probe as pp  # noqa: E402
import builtins_kit as bkit  # noqa: E402
import synth_probe as sp  # noqa: E402

SR = 48000
THRESH = 10 ** (-54 / 20)
DEVICE = "BlackHole 2ch"
LEAD_S = 30.0  # time to press Play after the recorder starts; the trim removes it


def first_at(kind):
    """Seconds into a stimulus at which its first sound starts."""
    if kind == "fx":
        return 1.0  # fxstim.wav: impulse at 1 s
    return float(sp.script()[0][0][0])


def trim_array(x, first_s, sr=SR):
    """Cut/pad x (n, ch) so its first sample above THRESH lands at first_s. None when nothing is audible."""
    i = bk.first_spike(np.max(np.abs(x), axis=1), THRESH)
    if i is None:
        return None
    start = i - int(round(first_s * sr))
    if start >= 0:
        return x[start:]
    return np.vstack([np.zeros((-start, x.shape[1])), x])


def record(path, seconds, device=DEVICE):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", ":" + device,
           "-t", str(seconds), "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s24le", path]
    return subprocess.run(cmd).returncode == 0


def read_capture(path):
    """ffmpeg's own WAV header variants (float, extensible) defeat the wave module, so decode through ffmpeg."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def trim_file(src, dst, first_s):
    y = trim_array(read_capture(src), first_s)
    if y is None:
        return False
    bk.write_wav24(dst, y)
    return True


def self_test():
    t = SelfTest("loopback_rec")
    x = np.zeros((SR * 4, 2))
    x[int(1.37 * SR), :] = 0.5  # impulse arriving 0.37 s late
    y = trim_array(x, 1.0)
    t.check(y is not None and int(np.argmax(np.abs(y[:, 0]))) == SR, "late take trimmed")
    z = np.zeros((SR * 4, 2))
    z[int(0.5 * SR), :] = 0.5  # arrived early: padded
    y = trim_array(z, 1.0)
    t.check(y is not None and int(np.argmax(np.abs(y[:, 0]))) == SR, "early take padded")
    t.check(trim_array(np.zeros((SR, 2)), 1.0) is None, "silence rejected")
    t.check(first_at("fx") == 1.0, "fx first sound")
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("rec")
    rp.add_argument("app")
    rp.add_argument("name")
    rp.add_argument("kind", choices=["synth", "fx"])
    rp.add_argument("--seconds", type=float)
    tp = sub.add_parser("trim")
    tp.add_argument("src")
    tp.add_argument("dst")
    tp.add_argument("--first-at", type=float, required=True)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "trim":
        return 0 if trim_file(a.src, a.dst, a.first_at) else 1
    if a.cmd == "rec":
        secs = a.seconds or (bkit.synth_len() if a.kind == "synth" else pp.TOTAL_S) + LEAD_S + 4.0
        d = ensure_dir(os.path.join(RE_OUTPUT, "builtins-kit", a.app))
        out = os.path.join(d, bkit.fname(a.kind, a.name))
        raw = os.path.join(tempfile.mkdtemp(), "raw.wav")
        print("recording %.0f s from %s: press Play in the DAW now" % (secs, DEVICE))
        if not record(raw, secs):
            print("loopback_rec: ffmpeg failed", file=sys.stderr)
            return 1
        if not trim_file(raw, out, first_at(a.kind)):
            print("loopback_rec: nothing audible on %s" % DEVICE, file=sys.stderr)
            return 1
        print("wrote", out)
        return 0
    ap.print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
