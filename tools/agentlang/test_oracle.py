#!/usr/bin/env python3
"""Every reference solution passes its oracle (static predicates; frame_stats stay pending),
every start patch fails it (an empty patch for build and Field tasks). Exit 0 / 1. Last line JSON.
Also checks the split: 20 dev + 10 held-out, 10 per kind, held-out 3 build / 3 tweak / 4 field.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import facts, oracle  # noqa: E402

EMPTY = "infinite-patch 1\n"


def main():
    F = facts.load()
    tasks = oracle.load_tasks()
    bad = []
    for tid, t in tasks.items():
        sol = open(os.path.join(HERE, "tasks", tid + ".solution.inf")).read()
        r = oracle.evaluate(t, sol, None, F)
        if not r["ok"]:
            bad.append(f"{tid}: solution fails: {[x for x in r['results'] if x['pass'] is False]}")
        if not any(p["kind"] != "no_errors" for p in t["oracle"]):
            bad.append(f"{tid}: oracle has no discriminating predicate")
        start = EMPTY
        if t["start_patch"]:
            start = open(os.path.join(HERE, "..", "..", t["start_patch"])).read()
        elif t["kind"] == "tweak":
            bad.append(f"{tid}: tweak task without start patch")
        r = oracle.evaluate(t, start, None, F)
        if r["ok"]:
            bad.append(f"{tid}: start patch passes the oracle")
    split = {}
    for t in tasks.values():
        split[(t["split"], t["kind"])] = split.get((t["split"], t["kind"]), 0) + 1
    want = {("dev", "build"): 7, ("dev", "tweak"): 7, ("dev", "field"): 6,
            ("held-out", "build"): 3, ("held-out", "tweak"): 3, ("held-out", "field"): 4}
    if split != want:
        bad.append(f"split is {split}")
    for b in bad:
        print("FAIL", b)
    print(json.dumps({"ok": not bad, "tasks": len(tasks), "problems": len(bad)}))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
