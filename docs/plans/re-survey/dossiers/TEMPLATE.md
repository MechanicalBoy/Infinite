# {{ID}} {{NAME}}: dossier

Status: draft. Started {{DATE}}. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/{{ID}}.md`

## 1. What it is

- Product, version (from `inventory.py`), how we got access (installed / trial / docs only).
- Licence status: proprietary | permissive (name it) | GPL/AGPL (behaviour and docs only).

## 2. Method

- Tools run (exact commands) and sources read (doc links).
- Not done: no source read, no decompiled code kept, no binaries or dumps committed.

## 3. Pillar map

One bullet per finding, tagged with its pillar, each with evidence (screenshot path in ~/re-output, command, or doc link).

- P2: finding. Evidence: ...

## 4. Comparison

Status is gap, lead or parity. Outcome is quest, perf-target, quality-gap or ignore, then a colon and a one-line reason.
Infinite equivalent is `none` or a repo path in backticks (the lint checks it exists).

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P2 | example feature | `src/path/File.cpp` | gap | ignore: reason in one line | doc link |

## 5. Measurements

Metric, method, numbers with units, setup, and the command that reproduces it. Write "none" if nothing was measured.

## 6. Outcomes

- Quests (count toward the 5-quest cap across all dossiers): ...
- Perf targets: ...
- Quality gaps: ...
- Ignored, with reason: ...

## 7. Storage

- Written to ~/re-output: paths and sizes (`python3 tools/re-survey/storage.py status`).
- Deleted: temp files removed (`storage.py clean-tmp`).
