# Phase 1 notes (mismatches and choices)

| Brief said | Repo says | Choice |
|---|---|---|
| 84 `.inf` files in `assets/examples/authoring/` and `tests/` | 81 `.inf` under `assets/examples`, `assets/templates` and `tests` (3 in `authoring/`) | T1 runs over all 81 |
| Ranges come from the generated node facts | The skill table has types, slots and kinds only; ranges and options need `Infinite --describe --json` (the app) | `facts.py` reads `nodefacts.json` when it exists (`dump_facts.py`, Phase 2). Without it the codec checks types, slots, kinds, value shape and names, and says `checked_by: "--validate (ranges, Field)"`. The range and unknown-key negative cases in T3 use a small injected facts table |
| Key tags (`f`, `i`, `b`, `c`, `s`) | Not in the skill table | Harvested from the repo's own `.inf` files (`harvest_keys.py` -> `keys_seen.json`, 73 types, no clashes). An unknown key gets its tag from the value (number -> `f`, word -> `i`, else `s`); `encode` excludes a patch whose tag cannot be derived that way |
| Node category | A few files write another category than the skill table (`AudioUtility` vs `Utility`) | The decoder writes the table's category; the comparison ignores category (the loader resolves by type) |
| `wire shape out` | `Output` has two input slots (`in`, `audio`) | Slot is optional only when the destination has exactly one input slot; the SPEC examples use `out.in` |
| `tests/field/` | Exists; `main` branch is local | T6 runs `git diff --quiet main -- src/core/field tests/field` from the repo root |
| Field task kernels | Written from the language skill and corpus examples, not compiled | `E_FIELD` is unchecked in Phase 1; Phase 2 runs `--validate` on every reference solution first and fixes the oracle's `contains` regexes only through a recorded note (tasks stay frozen) |

## Known limits of the frozen task set (record, do not edit)

- `frame_stats` predicates (b01, f01, f02, f07 where used) stay `pending` until Phase 2 supplies `--stats`.
  Their `seed` is `null` because no task uses Random.
- `no_errors` is a static stand-in (load, types, slots, kinds, taken slots, unreachable nodes). The CLI's `--validate` is the real one.
- Option keys (`shapeType`, `waveform`) are written `i <key> <option name>` as the repo's examples do.
- `ask` is not used by any reference solution (they are single paragraphs), but the tasks need key names the goal text does not give (b02 says "radius", the key is `uRadius`), so the verb stays.

## T1 exclusions (38 of 81 patches)

`mod` 29, `expr` 2, `glob` 1, `blendfix` 1 (records outside v0), `flags` lines (bypass), `uid` records, slot names beyond the node's declared inputs (`Mixer.in_9`, `Blend` slot 2), and one test patch that deliberately wires a taken slot (the decoder rejects it, correctly).

## Done check

`python3 tools/agentlang/test_oracle.py && python3 tools/agentlang/test_codec.py && python3 tools/agentlang/report.py` exits 0.
`python3 tools/agentlang/freeze.py check` matches `tasks/FROZEN.sha256`. `oracle.py` and `tasks/` were not edited after the freeze commit.
