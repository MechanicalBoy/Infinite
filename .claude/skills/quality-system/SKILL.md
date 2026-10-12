---
name: quality-system
description: "One registry, row format, gate and scoreboard for every measurement of Infinite: node audits, re-survey probes, the benchmark suite and driver checks. Use when adding or changing any measured metric, target or exception, when wiring a new audit/probe/bench into the scoreboard, or when asked how good Infinite is against competitors."
---

## When to use (full scope)

- Adding a measurement anywhere (an audit section, a re-survey analyser, a bench variant): it gets a registry row.
- Changing a target, a gate, or accepting an exception.
- A driver check fails with "quality gate".
- "How does Infinite compare on X", "what is still behind", "what is unmeasured".

## The rule

1. **The registry owns targets.** `docs/quality/registry.tsv` is the one place a target, gate or exception lives.
   An audit's own FLAG threshold is a pointer, not the gate.
2. **Measuring tools print rows, they do not judge.** `QUALITY id=<id> subject="<subject>" value=<number>`.
   Infinite subjects are `node:<Name>`; other apps use the tool's label.
3. **New metrics start as `report`.** Move to `release` once Infinite meets the target, so it stays met.
4. **An exception names a finding.** `node:Metallic=F1`, where F1 is a row in the source's findings table
   with owner decision and date. No exception without a finding.
5. **Generated files are never hand-edited**: `results.jsonl` (via `ingest`), `SCOREBOARD.md` (via `board`).
6. **Separate tools stay separate.** Extend the producer (one `Quality(...)` call or one `quality_line`), never
   fold audits, probes and benches into one program.

## Add a metric

1. Add a registry row: `id pillar area unit better target gate source exceptions what` (tab-separated).
   Pillars P1-P8 as in `docs/plans/re-survey/README.md`. `source` = the driver check name (e.g. `SYNTHAUDIT`)
   or the tool (`synth_probe`).
2. Emit rows from the producer next to the measurement.
3. `python3 tools/quality/quality.py check --source <SOURCE> <log>`: must pass, or record an exception.
4. `python3 tools/quality/quality.py ingest <log> --note "..."` then `board`; commit registry, results and
   scoreboard together.
5. `python3 tools/quality/quality.py --self-test` after any change to the tool.

## Gate in the driver

`driver.sh` runs `check --source <check>` on any passing check whose log contains QUALITY rows (generic verdict
path). A release miss, an unknown id, or a release metric that produced no rows fails the check as
"(quality gate)". Fix the cause, or record an exception with its finding. Never loosen a target to pass.

## Map

| Effort | Role in the system | Owner |
|---|---|---|
| Re-survey | Sets targets from competitor numbers | `docs/plans/re-survey/`, `prior-art-scout` rules apply |
| Node audits | Measure correctness per node; findings F1... back exceptions | `docs/plans/node-audits/README.md` |
| Benchmark suite | Measures speed on the reference machine | `docs/plans/perf/README.md`, `run-infinite-hygiene` efficient routes |
| Driver checks | Enforce `release` metrics | `run-infinite-hygiene` |
| Sweep skills | How to investigate a failing metric in their area | the `*-sweep` skills |

Rollout state and the loop diagram: `docs/quality/README.md`.
