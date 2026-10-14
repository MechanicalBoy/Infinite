#!/usr/bin/env python3
"""Write or check tasks/FROZEN.sha256 (sha256 of tasks.json and every other file in tasks/).
  freeze.py write    create the file
  freeze.py check    exit 0 when every file matches and none was added or removed
Last stdout line is JSON.
"""
import hashlib, json, os, sys

TASKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
OUT = os.path.join(TASKS, "FROZEN.sha256")


def digests():
    names = sorted(n for n in os.listdir(TASKS) if n != "FROZEN.sha256" and not n.startswith("."))
    return {n: hashlib.sha256(open(os.path.join(TASKS, n), "rb").read()).hexdigest() for n in names}


def main(argv):
    mode = argv[0] if argv else "check"
    d = digests()
    if mode == "write":
        open(OUT, "w").write("".join(f"{h}  {n}\n" for n, h in d.items()))
        print(json.dumps({"ok": True, "files": len(d)}))
        return 0
    want = {}
    for line in open(OUT).read().splitlines():
        h, _, n = line.partition("  ")
        want[n] = h
    bad = sorted(n for n in set(d) | set(want) if d.get(n) != want.get(n))
    print(json.dumps({"ok": not bad, "files": len(d), "mismatch": bad}))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
