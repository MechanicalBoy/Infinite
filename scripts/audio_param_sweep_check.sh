#!/usr/bin/env bash
# Per-param grading of the AUDIOPARAMSWEEPTEST log, shared by
# run-infinite-hygiene/driver.sh and scripts/sweep_runner.sh.
#
# The fixture's final "AUDIO PARAM SWEEP OK/FAIL" line is intentionally ignored:
# each param's own [FAIL]/[pass] line is checked against
# .claude/skills/run-infinite-hygiene/audio-param-sweep-expected.txt in both
# directions (see that file's header for baselined blind spot vs real failure).
#
# Source this file, then call:  audio_param_sweep_grade LOG
# Sets: APS_XFAIL APS_NEWFAIL APS_NOWPASS (counts), APS_DETAIL (array),
#       APS_XFAIL_LOG (path of the baselined lines).
# Returns 0 when there is no new failure and no now-passing baselined param.

APS_EXPECTED_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude/skills/run-infinite-hygiene/audio-param-sweep-expected.txt"

audio_param_sweep_grade() {
  local out="$1" line node param
  APS_XFAIL=0; APS_NEWFAIL=0; APS_NOWPASS=0; APS_DETAIL=()
  APS_XFAIL_LOG="/tmp/infinite_test_AUDIOPARAMSWEEPTEST_xfail.log"
  : > "$APS_XFAIL_LOG"
  while IFS= read -r line; do
    if [[ "$line" =~ \[FAIL\][[:space:]]+(.+[^[:space:]])[[:space:]]+param\ \'([^\']+)\' ]]; then
      node="${BASH_REMATCH[1]}"; param="${BASH_REMATCH[2]}"
      if awk -F'|' -v n="$node" -v p="$param" '$1==n && $2==p {f=1} END {exit !f}' "$APS_EXPECTED_FILE"; then
        APS_XFAIL=$((APS_XFAIL+1))
        echo "  [xfail] ${node}  param '${param}' — baselined, see audio-param-sweep-expected.txt" >> "$APS_XFAIL_LOG"
      else
        APS_NEWFAIL=$((APS_NEWFAIL+1))
        APS_DETAIL+=("new failure: '${node}|${param}' — add a line to audio-param-sweep-expected.txt if this is another rig blind spot, otherwise fix the dropped mailbox push")
      fi
    elif [[ "$line" =~ \[pass\][[:space:]]+(.+[^[:space:]])[[:space:]]+param\ \'([^\']+)\'\ reaches\ audio\ thread ]]; then
      node="${BASH_REMATCH[1]}"; param="${BASH_REMATCH[2]}"
      if awk -F'|' -v n="$node" -v p="$param" '$1==n && $2==p {f=1} END {exit !f}' "$APS_EXPECTED_FILE"; then
        APS_NOWPASS=$((APS_NOWPASS+1))
        APS_DETAIL+=("now passes: '${node}|${param}' — delete its line from audio-param-sweep-expected.txt")
      fi
    elif [[ "$line" =~ ^[[:space:]]*\[FAIL\] ]]; then
      # Not the per-param "reaches audio thread" shape (e.g. a save/load
      # round-trip failure): the expectations file does not cover it.
      APS_NEWFAIL=$((APS_NEWFAIL+1))
      APS_DETAIL+=("new failure (non-param-reach shape): $line")
    fi
  done < "$out"
  [ "$APS_NEWFAIL" -eq 0 ] && [ "$APS_NOWPASS" -eq 0 ]
}
