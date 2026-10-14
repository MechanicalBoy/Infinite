#!/usr/bin/env python3
"""Run the real headless `--validate` on every task's start patch and reference solution.
Phase 1 never compiled the Field kernels; this does. Last stdout line is JSON.

    python3 tools/agentlang/validate_all.py [--app PATH]
"""
import glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = "/Users/namansoni/infinte-main/build/Infinite.app/Contents/MacOS/Infinite"
if "--app" in sys.argv:
    APP = sys.argv[sys.argv.index("--app") + 1]


def validate(path):
    r = subprocess.run([APP, "--validate", path], capture_output=True, text=True, timeout=60)
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        j = {"ok": False, "errors": [{"code": "E_NOJSON", "message": (r.stdout + r.stderr)[-200:]}]}
    return r.returncode, j


bad, n = [], 0
for p in sorted(glob.glob(os.path.join(HERE, "tasks", "*.inf"))):
    rc, j = validate(p)
    n += 1
    # Audio-only patches (an `Utility Audio` node, no picture Output) always warn W_NO_OUTPUT; they render
    # through --audio-summary, so that one warning is not a failure for them.
    audio_only = "Utility Audio" in open(p).read()
    warns = [w for w in (j.get("warnings") or []) if not (audio_only and w.get("code") == "W_NO_OUTPUT")]
    if rc not in (0, 3) or j.get("errors") or warns or (rc == 3 and not (audio_only and not j.get("errors"))):
        bad.append({"file": os.path.basename(p), "rc": rc, "errors": j.get("errors"), "warnings": warns})
for b in bad:
    print(b["file"], json.dumps(b["errors"] or b["warnings"])[:300])
print(json.dumps({"ok": not bad, "validated": n, "failed": len(bad), "files": [b["file"] for b in bad]}))
sys.exit(0 if not bad else 1)
