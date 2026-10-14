#!/bin/bash
# Diagnose T4 failures: B1 on the two worst held-out tasks, errors kept in each run's .al_log.jsonl.
cd "$(dirname "$0")/../../.." || exit 1
O=tools/agentlang/out
python3 tools/agentlang/harness.py --cap-usd 0.6 --arm B1 --tasks t08,f08 --split all --reps 3 --model claude-sonnet-5-5 --out $O/diag.jsonl
python3 - <<'PY'
import json, os
for l in open("tools/agentlang/out/diag.jsonl"):
    r = json.loads(l); p = r["dir"] + "/.al_log.jsonl"
    print(r["task"], "first_ok", r.get("al_first_ok"), "turns", r["turns"])
    for x in (open(p) if os.path.exists(p) else []):
        x = json.loads(x)
        if not x["ok"]:
            print("  ERR", json.dumps(x.get("err"))[:300], "|", x.get("src", "")[:240].replace("\n", " / ")); break
PY
