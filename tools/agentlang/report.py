#!/usr/bin/env python3
"""Phase 1 report: one table. Runs test_oracle, test_codec and the freeze check; exit 0 when all pass.
Usage: python3 tools/agentlang/report.py     (last stdout line is JSON)
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(HERE, script), *args], capture_output=True, text=True)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "{}"
    return r.returncode, json.loads(last)


def main():
    tasks = json.load(open(os.path.join(HERE, "tasks", "tasks.json")))["tasks"]
    counts = {}
    for t in tasks:
        counts.setdefault(t["kind"], {"dev": 0, "held-out": 0})[t["split"]] += 1
    spec = open(os.path.join(HERE, "SPEC.md")).read()
    rc_o, o = run("test_oracle.py")
    rc_c, c = run("test_codec.py")
    rc_f, f = run("freeze.py", "check")
    t1, t2, t3, t6 = c.get("T1", {}), c.get("T2", {}), c.get("T3", {}), c.get("T6", {})
    rows = [("tasks", " ".join(f"{k}: {v['dev']} dev + {v['held-out']} held-out" for k, v in counts.items())),
            ("tasks frozen (sha256)", "match" if rc_f == 0 else f"MISMATCH {f.get('mismatch')}"),
            ("oracle test", "solutions pass, start patches fail" if rc_o == 0 else "FAIL"),
            ("SPEC size", f"{len(spec)} chars (limit 7000)"),
            ("T1 round trip", f"{t1.get('round_trip_equal')} equal of {t1.get('patches')} patches; "
                              f"{t1.get('excluded')} excluded; canonical {t1.get('canonical_ok')}/40"),
            ("T1 excluded by", ", ".join(f"{k} {v}" for k, v in t1.get("excluded_by", {}).items())),
            ("T2 fuzz", f"{t2.get('decoded')}/{t2.get('cases')} decoded"),
            ("T3 negatives", f"{t3.get('cases')} cases, E_LEX E_SYN E_SEM + E_FIELD marked"),
            ("T6 Field frozen", "clean" if t6.get("clean") else "CHANGED")]
    w = max(len(r[0]) for r in rows)
    for k, v in rows:
        print(f"{k:<{w}}  {v}")
    ok = rc_o == 0 and rc_c == 0 and rc_f == 0 and len(spec) <= 7000
    print(json.dumps({"ok": ok, "spec_chars": len(spec), "t1_equal": t1.get("round_trip_equal"),
                      "t1_excluded": t1.get("excluded"), "t2": t2.get("decoded"), "t3": t3.get("cases"),
                      "t6": t6.get("clean")}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
