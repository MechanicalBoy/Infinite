#!/bin/bash
# Pilot v2: 5 dev tasks, three arms, one model. Runs on the Air.
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p tools/agentlang/out; mv tools/agentlang/out/runs.jsonl tools/agentlang/out/pilot1.runs.jsonl 2>/dev/null
for A in B0 B0p B1; do python3 tools/agentlang/harness.py --arm $A --tasks b01,b04,t01,t04,f01 --model claude-sonnet-5-5 --cap-usd 0.6 --out tools/agentlang/out/pilot2.runs.jsonl; done
python3 tools/agentlang/report_runs.py tools/agentlang/out/pilot2.runs.jsonl
