#!/bin/bash
# Full run on the Air: held-out x 3 reps x 3 arms x 3 models, dev x 1 rep x 3 arms on sonnet, then T7 (decode-back). Models run in parallel.
cd "$(dirname "$0")/../../.." || exit 1
O=tools/agentlang/out; mkdir -p $O
H="python3 tools/agentlang/harness.py --cap-usd 0.6"
run_model() {
  M=$1; S=$(echo $1 | sed 's/claude-//')
  for A in B0 B0p B1; do $H --arm $A --split held-out --reps 3 --model $M --out $O/full.$S.jsonl; done
  [ "$M" = claude-sonnet-5-5 ] && for A in B0 B0p B1; do $H --arm $A --split dev --model $M --out $O/full.$S.jsonl; done
  $H --arm B1 --split held-out --t7 --model $M --out $O/t7.$S.jsonl
}
for M in claude-sonnet-5-5 claude-opus-5-5 claude-haiku-5-5; do run_model $M & done
wait
cat $O/full.*.jsonl > $O/full.runs.jsonl; cat $O/t7.*.jsonl > $O/t7.runs.jsonl
python3 tools/agentlang/final_suite.py --runs $O/full.runs.jsonl --t7 $O/t7.runs.jsonl > $O/final.json
cat $O/final.json
