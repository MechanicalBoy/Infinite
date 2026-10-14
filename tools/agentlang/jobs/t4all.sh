#!/bin/bash
# T4 after SPEC fix 2 (nodefacts.json, output/ask/Field Notes rules): held-out x3 then dev x1, same models. Old results move to out/old/.
cd "$(dirname "$0")/../../.." || exit 1
O=tools/agentlang/out; mkdir -p $O/old
for f in $O/t4.*.jsonl $O/t4dev.*.jsonl; do [ -f "$f" ] && mv "$f" "$O/old/$(basename $f .jsonl).$(date +%H%M).jsonl"; done
bash tools/agentlang/jobs/t4.sh
bash tools/agentlang/jobs/t4dev.sh
