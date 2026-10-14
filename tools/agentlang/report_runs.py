#!/usr/bin/env python3
"""Summarise out/runs.jsonl: per arm, tasks passed, mean tokens, turns, usd, and the token ratio vs B0p.
  report_runs.py [runs.jsonl]       last stdout line is JSON. `fresh` = in + cache_create + out; `all` adds cache_read.
"""
import json, os, sys
from collections import defaultdict

p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "runs.jsonl")
rows = [json.loads(l) for l in open(p) if l.strip()]
by = defaultdict(list)
for r in rows:
    by[r["arm"]].append(r)
fresh = lambda r: (r["in"] or 0) + (r["cache_create"] or 0) + (r["out"] or 0)
summ = {}
for arm, rs in sorted(by.items()):
    n = len(rs)
    summ[arm] = {"runs": n, "passed": sum(bool(r["oracle"]["ok"]) for r in rs),
                 "fresh_tokens": round(sum(map(fresh, rs)) / n), "all_tokens": round(sum(r["tokens_total"] for r in rs) / n),
                 "turns": round(sum(r["turns"] or 0 for r in rs) / n, 1), "usd": round(sum(r["usd"] or 0 for r in rs), 3)}
# paired by task, only tasks present in both arms and passed in both
def ratio(a, b):
    A = {r["task"]: r for r in by.get(a, [])}
    B = {r["task"]: r for r in by.get(b, [])}
    ks = [k for k in A if k in B and A[k]["oracle"]["ok"] and B[k]["oracle"]["ok"]]
    if not ks: return None
    return {"tasks": ks, "fresh": round(sum(fresh(A[k]) for k in ks) / sum(fresh(B[k]) for k in ks), 3),
            "all": round(sum(A[k]["tokens_total"] for k in ks) / sum(B[k]["tokens_total"] for k in ks), 3)}
res = {"arms": summ, "B1_vs_B0p": ratio("B1", "B0p"), "B1_vs_B0": ratio("B1", "B0"), "B0p_vs_B0": ratio("B0p", "B0")}
for arm, s in summ.items():
    print(f"{arm:4} runs {s['runs']:2} passed {s['passed']:2} fresh {s['fresh_tokens']:>7} all {s['all_tokens']:>8} turns {s['turns']:>4} usd {s['usd']}")
for k in ("B1_vs_B0p", "B1_vs_B0"):
    v = res[k]
    print(k, "ratio (below 1 = B1 cheaper):", v and {"fresh": v["fresh"], "all": v["all"], "paired_tasks": len(v["tasks"])})
print(json.dumps(res))
