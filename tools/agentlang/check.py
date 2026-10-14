#!/usr/bin/env python3
"""One-call check of a patch: validate + graph + a frame or audio probe, as one compact JSON line.
Used by arm B0' (`./check work.inf`) and by arm B1 (`./al check`). Same code, so the arms differ only in language.

    check.py PATCH [--app PATH] [--t 0]
"""
import json, os, re, subprocess, sys, tempfile

APP = os.environ.get("INFINITE_APP", "/Users/namansoni/infinte-main/build/Infinite.app/Contents/MacOS/Infinite")


def run(args, timeout=120):
    r = subprocess.run([APP] + args, capture_output=True, text=True, timeout=timeout)
    last = (r.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        j = json.loads(last)
    except ValueError:
        j = {"ok": False, "errors": [{"code": "E_NOJSON", "message": (r.stdout + r.stderr)[-200:]}]}
    return r.returncode, j, r.stdout


def validate(patch):
    """-> (ok, errors, warnings). W_NO_OUTPUT is not a failure for audio-only patches (they render by --audio-summary)."""
    text = open(patch).read()
    rc, j, _ = run(["--validate", patch])
    audio_only = "Utility Audio" in text
    warns = [w for w in (j.get("warnings") or []) if not (audio_only and w.get("code") == "W_NO_OUTPUT")]
    errs = j.get("errors") or []
    return (not errs and not warns), errs, warns


def probe(patch, t=0):
    text = open(patch).read()
    out = {}
    if re.search(r"^node \d+ \w+ Output\b", text, re.M) or " Utility Output" in text:
        d = tempfile.mkdtemp()
        _, j, _ = run(["--frame", patch, str(t), d + "/"])
        fs = (j.get("frame_stats") or [{}])[0]
        out["frame"] = {k: fs.get(k) for k in ("mean_luma", "min_luma", "max_luma", "black_percent") if k in fs}
        if j.get("errors"):
            out["frame_errors"] = j["errors"]
    if "Utility Audio" in text:
        f = tempfile.mktemp(suffix=".json")
        _, j, _ = run(["--audio-summary", patch, f])
        a = j.get("audio_summary") or {}
        out["audio"] = {k: a.get(k) for k in ("integrated_lufs", "true_peak_dbtp", "seconds") if k in a}
    return out


def main(argv):
    patch = argv[0]
    t = float(argv[argv.index("--t") + 1]) if "--t" in argv else 0
    ok, errs, warns = validate(patch)
    _, _, ex = run(["--explain", patch])
    graph = "\n".join(l for l in ex.splitlines() if l and not l.startswith("{"))[:1800]
    res = {"ok": ok, "errors": errs[:3], "warnings": warns[:3], "graph": graph}
    if ok:
        res.update(probe(patch, t))
    print(json.dumps(res))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
