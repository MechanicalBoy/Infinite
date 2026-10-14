#!/usr/bin/env python3
"""Write nodefacts.json (ranges, options, defaults) from the built app. Phase 2 / Pro only.

Same route as tools/gen-patch-skill.py: `Infinite --describe <type> --json out.json` per type
(the all-types describe can abort on CoreMotion). Not run in Phase 1: it needs the binary.
Usage: python3 tools/agentlang/dump_facts.py [--bin path/to/Infinite]
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import facts  # noqa: E402

DEFAULT_BIN = os.path.join(facts.ROOT, "build/Infinite.app/Contents/MacOS/Infinite")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=DEFAULT_BIN)
    a = ap.parse_args()
    types, skipped = [], []
    with tempfile.TemporaryDirectory() as d:
        for name in sorted(facts.load(nodefacts=None).types):
            one = os.path.join(d, "one.json")
            r = subprocess.run([a.bin, "--describe", name, "--json", one], capture_output=True)
            if r.returncode == 0:
                types += json.load(open(one))["types"]
            else:
                skipped.append(name)
    json.dump({"types": types}, open(facts.NODEFACTS, "w"))
    print(json.dumps({"ok": not skipped, "types": len(types), "skipped": skipped}))
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
