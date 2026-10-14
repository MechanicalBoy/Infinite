#!/usr/bin/env python3
"""FINAL gate: paired bootstrap on the held-out tasks, per model, B1 vs B0p (and vs B0).

  verdict.py runs.jsonl [--boot 4000]      last stdout line is JSON {verdict, per_model, rule}

Unit = task. For each arm and task: total tokens (or usd) over its repetitions / solved repetitions ("per solved task");
the arm ratio is sum over tasks, resampled with replacement (paired: the same tasks drawn for both arms), 95% CI.
Metrics: `fresh` (in + cache_create + out), `usd` (billed), `all` (adds cache_read). A model counts as a win when the
95% CI upper bound is below 1 for BOTH `fresh` and `usd` (the conservative pair), mean turns are lower, and B1 solves
no more than one task fewer than B0p. KEEP-GOING needs wins on at least 2 of 3 models. `all` is reported, not gated.
"""
import json, random, sys
from collections import defaultdict

args = [a for a in sys.argv[1:] if not a.startswith("--")]
boot = int(sys.argv[sys.argv.index("--boot") + 1]) if "--boot" in sys.argv else 4000
rows = [json.loads(l) for l in open(args[0]) if l.strip()]
rows = [r for r in rows if r["split"] == "held-out"]
M = {"fresh": lambda r: (r["in"] or 0) + (r["cache_create"] or 0) + (r["out"] or 0),
     "usd": lambda r: r["usd"] or 0.0, "all": lambda r: r["tokens_total"]}


def per_task(rs, metric):
    d = defaultdict(lambda: [0.0, 0, 0, 0.0])  # total, solved, runs, turns
    for r in rs:
        e = d[r["task"]]
        e[0] += M[metric](r); e[1] += bool(r["oracle"]["ok"]); e[2] += 1; e[3] += r["turns"] or 0
    return d


def ratio(a_rs, b_rs, metric, rng):
    A, B = per_task(a_rs, metric), per_task(b_rs, metric)
    ks = sorted(set(A) & set(B))
    def r(sample):
        ta = sum(A[k][0] for k in sample); sa = sum(A[k][1] for k in sample)
        tb = sum(B[k][0] for k in sample); sb = sum(B[k][1] for k in sample)
        return (ta / max(sa, 0.5)) / (tb / max(sb, 0.5))  # per solved task; 0.5 stops a zero-solve blow-up
    pt = r(ks)
    bs = sorted(r([rng.choice(ks) for _ in ks]) for _ in range(boot))
    return {"ratio": round(pt, 3), "ci95": [round(bs[int(.025 * boot)], 3), round(bs[int(.975 * boot) - 1], 3)], "tasks": len(ks)}


rng = random.Random(7)
out = {}
for model in sorted({r["model"] for r in rows}):
    R = {a: [r for r in rows if r["model"] == model and r["arm"] == a] for a in ("B0", "B0p", "B1")}
    if not (R["B1"] and R["B0p"]):
        continue
    ent = {m: ratio(R["B1"], R["B0p"], m, rng) for m in M}
    ent["vs_B0_fresh"] = ratio(R["B1"], R["B0"], "fresh", rng) if R["B0"] else None
    solved = {a: sum(v[1] for v in per_task(R[a], "fresh").values()) / max(1, max(v[2] for v in per_task(R[a], "fresh").values())) for a in R if R[a]}
    turns = {a: round(sum(r["turns"] or 0 for r in R[a]) / len(R[a]), 2) for a in R if R[a]}
    ent["solved_tasks_equiv"] = {a: round(v, 2) for a, v in solved.items()}
    ent["turns"] = turns
    ent["win"] = bool(ent["fresh"]["ci95"][1] < 1 and ent["usd"]["ci95"][1] < 1 and turns["B1"] < turns["B0p"]
                      and solved["B1"] >= solved["B0p"] - 1)
    out[model] = ent
wins = sum(v["win"] for v in out.values())
verdict = "KEEP-GOING" if wins >= 2 and len(out) >= 3 else ("INCONCLUSIVE (fewer than 3 models)" if len(out) < 3 else "STOP")
for m, v in out.items():
    print(f"{m}: win={v['win']} fresh {v['fresh']['ratio']} {v['fresh']['ci95']} usd {v['usd']['ratio']} {v['usd']['ci95']} all {v['all']['ratio']} turns {v['turns']} solved {v['solved_tasks_equiv']}")
print(json.dumps({"verdict": verdict, "wins": wins, "models": len(out), "per_model": out}))
