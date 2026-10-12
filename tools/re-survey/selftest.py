#!/usr/bin/env python3
"""Run every re-survey tool's --self-test. Exit 0 only if all pass.

Usage: python3 tools/re-survey/selftest.py [--quick]   (--quick skips the probes' Infinite renders)
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = ["inventory.py", "plugin_probe.py", "synth_probe.py", "ui_map.py", "capability_map.py", "app_bench.py", "bounce_kit.py", "host_audit.py", "au_oop.py", "load_bench.py", "stretch_kit.py", "builtins_kit.py", "latency_probe.py", "readers.py", "diff.py", "storage.py"]


def main():
    env = dict(os.environ)
    if "--quick" in sys.argv:
        env["INFINITE_BIN"] = "/nonexistent"
    fails = []
    for t in TOOLS:
        rc = subprocess.call([sys.executable, os.path.join(HERE, t), "--self-test"], env=env)
        if rc != 0:
            fails.append(t)
    print("\nre-survey self-test: %s" % ("FAILED " + ", ".join(fails) if fails else "all passed"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
