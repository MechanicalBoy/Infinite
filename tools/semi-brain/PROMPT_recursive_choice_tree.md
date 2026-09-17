# Prompt: Recursive, graph-grounded choice tree for semi-brain

## Context

`tools/semi-brain/4_engine/brain_core.py`'s `evaluate_choice_tree()` currently
returns three **fixed, hardcoded** branches (Quick Patch / Invariant-Guarded Fix /
Full Rewrite) with hand-set scores — Branch B's numbers are baked in high enough
that it wins almost every time. The `ChoiceBranch` dataclass and its
`compute_value()` weighted formula are real and fine; what's missing is that the
tree doesn't actually grow from the problem, and it doesn't recurse through what
a decision touches.

Separately, `analyze_problem()` already loads a real AST graph at
`1_extractors/output/ast_symbol_graph.json` with this shape:

```json
{
  "stats": {...},
  "subsystems": {...},
  "symbols": {
    "TmpPath": {"kind": "function", "name": "TmpPath", "full_name": "TmpPath",
                "file": "src/main.cpp", "line": 79, "subsystem": "ui_shell"}
  },
  "forward_call_graph": { "TmpPath": ["AppPaths::TempDir"] },
  "reverse_call_graph": { "AppPaths::TempDir": ["AudioRecordings::GetRecordingsDirectory", "TmpPath"] },
  "file_includes": {...}
}
```
(7279 symbols, 4223 forward entries, 5830 reverse entries as of this writing.)
`get_callers_for_symbols()` already walks `reverse_call_graph` one hop to find
callers of the matched symbols — but only one hop, and only for the blast-radius
prose (`Q3_Caller_Graph`), never for branch generation itself.

## The gap

Today: one problem → three fixed archetype branches, scored, done.

Wanted: a decision on `matched_symbols` should **generate new branches from
what the AST graph shows gets touched**, recursively — if fixing symbol X means
its caller Y (per `reverse_call_graph`) now has to handle a new case, that's a
new decision point, which may itself fork. This is the actual "branches emerge
because the code is connected" behavior the user wants, not three static
labels.

## What to build

In `brain_core.py`, add real tree growth on top of what already exists — don't
touch `ProblemFrame`, `analyze_problem()`'s symbol matching, or the RAG
retrieval; they're correct and should stay the source of ground truth.

1. **`build_impact_tree(frame: ProblemFrame, max_depth=3, max_fanout=4) -> ImpactNode`**
   - Root node = the primary matched symbol(s) from `frame.ast_impacted_symbols`.
   - For each node, pull its direct callers via `reverse_call_graph` (already
     have `get_callers_for_symbols`, reuse/generalize it to not cap at 8 and to
     be callable per-symbol at arbitrary depth).
   - Each caller becomes a child node **only if** it's architecturally
     load-bearing enough to matter — filter by: does this caller's `subsystem`
     (from `symbols[caller]["subsystem"]`) differ from the parent's subsystem
     (i.e. crosses a subsystem boundary), or does the caller fan out to ≥2 of
     its own callers (i.e. it's itself a hub). Cheap heuristic, not ML — the
     point is pruning noise like trivial one-line wrappers from the tree, not
     perfect classification.
   - Stop at `max_depth` hops or when a symbol has no more callers
     (`reverse_call_graph.get(sym, [])` is empty).
   - Cap branching at `max_fanout` children per node (take the highest-fanout
     callers first — a caller with many callers of its own is more load-bearing)
     so the tree stays readable for anything with a wide blast radius.

2. **`ImpactNode` dataclass**: `symbol: str`, `file: str`, `line: int`,
   `subsystem: str`, `children: List[ImpactNode]`, `crosses_subsystem: bool`,
   `is_hub: bool` (fanout ≥ 2). This is the actual data structure the tree
   renders from — keep it separate from `ChoiceBranch`, which stays the
   strategy-scoring layer.

3. **Fold the impact tree into branch generation.** Replace the three
   hardcoded `ChoiceBranch` literals in `evaluate_choice_tree()` with branches
   *derived from* `build_impact_tree()`'s actual shape:
   - If the impact tree has 0-1 subsystem crossings and depth ≤1 → only
     propose "Local Fix" and "Invariant-Guarded Fix" (a full rewrite branch is
     noise for a leaf-level change; don't manufacture a third option nobody
     needs).
   - If it crosses ≥2 subsystems or a hub node appears (fanout ≥2 mid-tree) →
     add a branch per distinct subsystem crossed, e.g. "Guard invariant at
     `ParamMailbox` AND update `AudioEngine`'s consumer path" — named from the
     real symbols in the tree, not template strings.
   - Score each generated branch the same way as today (`Inv`, `Plat`, `RT`,
     `RoundTrip`, `Taste`, `Blast`), but derive `blast_penalty` **from the
     actual impact tree's node count and subsystem-crossing count** instead of
     a hardcoded constant (e.g. `blast_penalty = min(1.0, 0.15 * crossings + 0.05 * total_nodes)`).
     This is the one part of the scoring that was pure fiction before — tie it
     to something real.
   - Keep `Inv`/`Plat`/`RT`/`RoundTrip`/`Taste` as heuristic priors seeded from
     `frame.system1_priors` / `frame.negative_taboos_flagged` (as today) since
     those aren't graph-derivable — don't invent false precision there.

4. **CLI/render update** in `semi_brain_cli.py`: render the impact tree itself
   (rich `Tree`, one level per hop, tag hub/crossing nodes) above the existing
   Choice Tree MCTS panel, so the user can see *why* a given branch got
   generated — which real callers forced it — not just the final scored list.

5. **Test**: add a case to `5_evals/benchmark_suite.json` using a symbol
   known to have deep real fan-out (check `stats` / `reverse_call_graph` sizes
   for a good candidate — something like `ParamMailbox` or `INode` is likely
   high-fanout) and assert the generated branch set differs from the
   flat/no-fanout case, so a future regression that silently reverts to
   fixed-3-branches gets caught.

## Constraints

- Don't change `analyze_problem()`'s subsystem inference, RAG retrieval, or
  `SUBSYSTEM_ANCHOR_SYMBOLS` — those are working and out of scope.
- Don't fabricate call-graph edges. If `reverse_call_graph` has no entry for a
  symbol, the tree just stops there — no invented children.
- Keep `ChoiceBranch.compute_value()`'s weighted formula and its hard-pruning
  rule (`RT < 1.0 or Plat < 1.0 → -1.0`) unchanged; only how many branches get
  generated and how `blast_penalty` is derived should change.
- This only touches `tools/semi-brain/`, not `src/`. No Infinite application
  code changes.
