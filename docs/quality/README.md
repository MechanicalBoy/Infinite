# Quality system

One registry, one row format and one scoreboard for every measurement of Infinite. Started 2026-10-13
with Synths as the pilot. Owner skill: `quality-system`.

## Why

Four efforts measure Infinite, and before this each had its own format, tracker and verdict:

| Effort | Question it answers | Lives in |
|---|---|---|
| Node audits | Is each node correct, by physics or by its own spec? | `docs/plans/node-audits/` |
| Re-survey | What does "good" look like in the apps people compare Infinite to? | `docs/plans/re-survey/`, `tools/re-survey/` |
| Benchmark suite | Is it fast enough on the base M2 8 GB laptop? | `docs/plans/perf/`, `tools/bench.py` |
| Driver checks and sweep skills | Did anything break? How do I investigate this area? | `.claude/skills/run-infinite-hygiene/driver.sh`, `*-sweep` skills |

They stay separate tools. What they share now is the metric: the same id, the same row, one place for targets.

## The loop

```
re-survey ──► competitor numbers set the TARGET
    │
    ▼
registry.tsv (id, pillar, area, unit, better, target, gate, source, exceptions)
    │
    ├── node audits ─┐
    ├── bench suite ─┼──► QUALITY rows ──► quality.py ingest ──► results.jsonl ──► SCOREBOARD.md
    └── probes ──────┘
                         QUALITY rows ──► quality.py check ──► driver.sh fails on a release-gated miss
                                                                │
                                                                ▼
                                       the sweep skill for that area says how to investigate
```

## Files

| File | What | Edited by |
|---|---|---|
| `registry.tsv` | One row per metric. Owns target, gate and exceptions | Hand, one row per new metric |
| `results.jsonl` | Worst value per (metric, subject) per recorded run, with UTC time, commit and machine | `quality.py ingest` only |
| `SCOREBOARD.md` | Status per pillar and metric; Infinite's worst against the best other app | `quality.py board` only |
| `tools/quality/quality.py` | `check`, `ingest`, `board`, `--self-test` | Code |

## The row

```
QUALITY id=synth.alias_db subject="node:Analog" value=-66.2000
```

- `id`: a registry id. An unknown id fails `check` and `ingest`, so the registry stays the one owner.
- `subject`: `node:<Name>` for Infinite's nodes, the tool's own label for anything else (`Vital Audio: Vital`).
- A producer may print many rows for one (id, subject), for example one per note or sample rate. The tool keeps
  the worst by the metric's `better` direction.

| Producer | How it emits |
|---|---|
| SYNTHAUDIT (`src/app/selftest/SynthAudit.cpp`) | `Quality(id, node, value)` next to each measurement, on stdout |
| `tools/re-survey/synth_probe.py` | `quality.txt` beside `results.json` (helper `common.quality_line`) |

## Gates

- `release`: the driver runs `quality.py check --source <CHECK>` on every check whose log has QUALITY rows. A miss
  fails the check unless the subject is listed in `exceptions` with a finding id. It also fails when a release
  metric owned by that check produced no rows at all, so an audit cannot go quiet unnoticed.
- `report`: shown on the scoreboard as `behind`; never fails a run. Competitor comparisons, CPU timings and anything
  still above its target start here and move to `release` once Infinite meets the target, so it stays met.
- A FLAG line inside an audit is that audit's own pointer for investigation. The registry target is the gate.

## Day to day

```bash
python3 tools/quality/quality.py check --source SYNTHAUDIT /tmp/infinite_test_SYNTHAUDIT.log
python3 tools/quality/quality.py ingest /tmp/infinite_test_SYNTHAUDIT.log --note "after F11"
python3 tools/quality/quality.py board
```

Record (`ingest`) after a fix, a new competitor run or a release, not after every run.

## Rollout

| Step | Area | State |
|---|---|---|
| 1 | Synths: SYNTHAUDIT + `synth_probe` (Diva, Serum 2, Vital) | done 2026-10-13 |
| 2 | Benchmark suite B1 to B8 (`tools/bench.py`), reference machine base M2 8 GB | next |
| 3 | Re-survey areas: each block ends in registered metrics plus a short dossier | after 2 |
| 4 | Node audits: FXAUDIT, NOTEAUDIT, IOAUDIT, then block 3 (GEOAUDIT, COMPAUDIT) written straight in | after 3 |
