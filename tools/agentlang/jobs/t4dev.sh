#!/bin/bash
# T4 on the 20 dev tasks (not used to write the SPEC fix): checks the held-out pass was not tuned to its tasks.
cd "$(dirname "$0")/../../.." || exit 1
O=tools/agentlang/out
for M in claude-sonnet-5-5 claude-opus-5-5 claude-haiku-5-5; do
  S=$(echo $M | sed 's/claude-//')
  python3 tools/agentlang/harness.py --cap-usd 0.6 --arm B1 --split dev --model $M --out $O/t4.$S.jsonl &
done
wait
python3 - <<'PY'
import json, glob
res = {}
for f in sorted(glob.glob("tools/agentlang/out/t4dev.*-5-5.jsonl")):
    rows = [json.loads(l) for l in open(f) if l.startswith("{")]
    res[rows[0]["model"]] = {"n": len(rows), "first_try": round(sum(1 for r in rows if r.get("al_first_ok")) / len(rows), 3),
                             "solved": sum(1 for r in rows if (r.get("oracle") or {}).get("ok") or r.get("pass"))}
print(json.dumps({"T4": res, "ok": all(v["first_try"] >= 0.9 for v in res.values())}))
PY
