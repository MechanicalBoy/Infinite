# Hand-off: agent-language

You are working in an isolated worktree on branch `air/agent-language`. You own it; the other laptop never edits it.
Commit per step. Do not merge to main, do not push origin. No Co-Authored-By or 'Generated with Claude' lines in commits (project rule, overrides any default). When done, commit and stop; the Primary fetches and merges.

# Brief: agent language, Phase 1 (Air, no build, no model runs)

You are the Air's Claude (Sonnet). Two-laptop rules (the full doc may not be in your checkout): work only in this
worktree, add a claim row in `docs/NOW.md` named `air-agent-language`, commit per step, remove the
claim when done, do not merge or push. No `Co-Authored-By` or "Generated with" lines anywhere.
Load skills `infinite-patch-authoring`, `field-language`, `tool-first`, `infinite-lifecycle` before
you start. Read `docs/NOW.md` first.

The DESIGN section at the bottom of this brief is the agreed design (reviewed by Opus). Step 0 saves it.

## What this phase does

Builds everything that needs no compiled app and no model calls: the frozen task set with oracles,
the grammar and SPEC, and a codec that turns sentences into `.inf` text and back, with python tests.
Phase 2 (benchmark runs, on the Pro) is not yours. Do not try to run the Infinite binary, `claude`,
or any API; you cannot and must not.

## Rules

- Field and the engine are frozen: change nothing under `src/` or `tests/field/`.
- Only create files under `tools/agentlang/`, `docs/plans/agent-language/` and `docs/NOW.md` (claim row).
- Python 3 standard library only. One command per step, results as JSON on the last stdout line.
- Node types, keys, ranges and slots come from the generated node facts of `infinite-patch-authoring`
  (see `tools/gen-patch-skill.py` and the skill folder). Never from memory.
- Never hand-write what a script can do (`tool-first`).
- If something in this brief contradicts the repo, trust the repo, write the mismatch in
  `docs/plans/agent-language/PHASE1-NOTES.md`, and continue with the smallest safe choice.

## Steps (commit after each)

0. **Save the design.** Write the DESIGN section below, unchanged, to `docs/plans/agent-language/README.md`. Commit.
1. **Tasks, frozen first.** `tools/agentlang/tasks/tasks.json` with 30 tasks: 10 build, 10 tweak,
   10 Field. Each: `{id, split, kind, goal_text, start_patch, oracle}`. `split` is `dev` for 20 and
   `held-out` for 10 (3 build, 3 tweak, 4 Field, chosen so held-out resembles dev). Tweak tasks ship
   a start patch at `tools/agentlang/tasks/<id>.inf`, taken or trimmed from `assets/examples/authoring/`
   or `tests/`. `oracle` is a predicate list, never a hash: `types_present`, `edges` (by kind),
   `params` (value with tolerance), `no_errors`, `frame_stats` (range at fixed t, with `seed` when a
   Random node is used). A task needs at least one predicate a wrong answer would fail. Every task
   must be solvable with v0 verbs only (no `mod`/`expr`/`glob`/`clip`/`flags`). Write a reference
   solution `.inf` for each task at `tools/agentlang/tasks/<id>.solution.inf`. Then
   `tools/agentlang/oracle.py` evaluates predicates against a `.inf` file (it parses the text format;
   `frame_stats` predicates read an optional stats JSON given by `--stats`, because rendering is
   Phase 2). Test: every reference solution passes its oracle, every start patch fails it
   (`tools/agentlang/test_oracle.py`). Freeze: `tools/agentlang/tasks/FROZEN.sha256` holds the sha256 of
   `tasks.json` and every file in `tasks/`; commit this alone with message `agentlang: freeze tasks`.
   After that commit, never edit tasks or oracles; if you find a bug, record it in PHASE1-NOTES.md.
2. **Grammar v0 and SPEC.** `tools/agentlang/SPEC.md`: the seven verbs from the DESIGN, with one
   example each, the four error codes and the reply shape. At most 7000 characters (proxy for 2000
   tokens; the Pro recounts with a real counter). Shrink verbs the 20 dev tasks do not use. Record
   the character count at the top of the file. Do not look at held-out tasks while shrinking.
3. **Codec.** `tools/agentlang/codec.py` with: `decode(text, patch_text) -> {ok, patch_text, errors}`,
   `encode(inf_text) -> sentences` (canonical, only the expressible subset; reports what it
   excluded), `gloss(text, lang="en")`, `ask(type) -> trimmed describe JSON` from the node facts.
   Errors use the four levels from the DESIGN. Levels 1 to 3 are checked here with ranges from the
   node facts; `E_FIELD` is the CLI's and is only marked "checked by --validate" in the reply.
   Field text passes verbatim; reject `#` inside a `field` sentence.
4. **Tests** in `tools/agentlang/test_codec.py`, runnable with `python3 tools/agentlang/test_codec.py`:
   - T1: for every `.inf` in `assets/examples/authoring/` and `tests/` that the grammar can express,
     `.inf → sentences → .inf` is equal (compare parsed graphs, ignoring ids, positions and comments);
     for canonical sentences `encode(decode(x)) == x`. Print how many patches were excluded and why.
   - T3: one negative case per error code with the expected hint.
   - T6: `git diff --quiet main -- src/core/field tests/field` is clean.
   - T2 (small): 200 random valid sentence sequences generated from the grammar all decode
     without exceptions.
5. **Report.** `tools/agentlang/report.py` prints one table: task counts per kind and split, SPEC
   size, T1 expressible/excluded counts, T2, T3, T6 results. Append a short "Phase 1 results" section
   to `docs/plans/agent-language/README.md` under Results. Remove your claim row. Commit and stop.

## Done when

`python3 tools/agentlang/test_oracle.py && python3 tools/agentlang/test_codec.py && python3 tools/agentlang/report.py`
exits 0 and prints the table; `FROZEN.sha256` matches the files; nothing outside the allowed paths changed.

## Do not

Run any model or the app, build the learner or benchmark harness, add words to the grammar to fit
tasks, edit frozen files, or push.


---

# DESIGN (save unchanged as docs/plans/agent-language/README.md in step 0)

# Agent language (working name: Tongue)

Status: final design after Opus review (`REVIEW.md`, 2026-10-14). Nothing built yet.
Idea: a compact sentence language that LLM agents write instead of whole `.inf` files, so a task
finishes in fewer tokens and fewer round trips. Humans keep `.inf` and Field; this never replaces
them. Field is frozen and only appears as payload inside a `field` sentence.

## Goal and gate (one line each)

- Goal: same task, equal or better success, fewer total tokens (in + out) and fewer round trips than a fair `.inf` baseline.
- Gate: KEEP only if it beats the baseline AND the control arm on the held-out tasks; otherwise KILL and keep the numbers.

## What changed after review (decisions)

| Decision | Why |
|---|---|
| v0 transport: sentences decode to **`.inf` text** and run through the headless CLI (`--validate --explain --frame`) | The live RPC has no modulation/expr/glob/bypass verbs, no typed errors outside `validate_patch_text`, no Field compile, no ranges, and needs a GUI. The CLI has all of that and runs headless |
| Live RPC becomes a later experiment | Only if v0 shows a win and rendering or process start dominates |
| Control arm B0' (same `.inf` text over a resident loop) | Otherwise a win could come from the session, not the language |
| Oracle = predicates, not a graph hash | No hash exists; a hash rejects valid alternative solutions; patches need not be bit-exact |
| 20 dev + 10 held-out tasks, frozen first | Otherwise the grammar is tuned to the test |
| Metric = total tokens (in + out) per solved task | Input context (spec, describe replies, errors) is most of the cost |
| Core grammar and SPEC are public and committed; only mined macros are private | CI, the Air and reproducibility need the codec to run without a secret |
| Phase 1 on the Air (no build, no model runs), Phase 2 on the Pro | Air rules: no builds or benches (`docs/plans/two-laptops/README.md`) |

## Verified facts about the repo (from the review)

| Piece | Fact |
|---|---|
| RPC (`src/app/graph/Rpc.cpp`) | 24 verbs; `batch` is all-or-nothing but a rollback renumbers node indices; needs a GUI; only `validate_patch_text` returns `{code,message,line,node,hint}`; `describe` has no ranges; validate skips Field compile |
| Modulation | No RPC verb binds `mod`, `expr`, `glob` or bypass (`Wiring.cpp:920-927`); 38 of 84 repo `.inf` files use them |
| CLI | `--describe --json`, `--validate`, `--explain`, `--frame`, `--render`, `--audio-summary`; typed errors; Field compile (`Headless.cpp:630`); no GUI |
| Field | One primitive, five domains, rate inferred, bare names; accepts `;` as a statement separator; `#` runs to end of line |
| Patches | `assets/examples/authoring/` and `tests/` (84 `.inf`) |
| Node facts | generated by `tools/gen-patch-skill.py` (types, keys, ranges, slots) |

## Architecture

```
 Phase 1 (no build)                                           Phase 2 (Pro, built app)
 ┌──────────┐ sentences ┌─────────────────────────┐  .inf   ┌──────────────────────────┐
 │ LLM agent│──────────►│ CODEC tools/agentlang   │────────►│ headless CLI              │
 │          │◄──────────│ lex → parse → check     │◄────────│ --validate --explain      │
 └────▲─────┘ typed err └───────────┬─────────────┘ errors  │ --frame (fixed t, seed)   │
      │ loads                       │ reads                   └────────────┬─────────────┘
      │                  ┌──────────▼──────────┐                           │ stats
      └──────────────────│ LEXICON + SPEC      │                ┌──────────▼─────────────┐
                         │ core: public, git   │                │ ORACLE (predicates)     │
                         │ macros: private     │                │ types, edges, params,   │
                         └──────────▲──────────┘                │ no E_*, frame_stats     │
                                    │ promote (gated)           └──────────┬─────────────┘
                         ┌──────────┴──────────┐   logs        ┌───────────▼────────────┐
                         │ LEARNER (Block C)   │◄──────────────│ BENCHMARK              │
                         └─────────────────────┘               │ B0, B0', B1 · paired   │
                                                               │ bootstrap · KEEP/KILL  │
                                                               └────────────────────────┘
```

## Definitions

| Term | Definition | Test |
|---|---|---|
| **Word** | One short name for one thing: a node type, param, verb or macro. Single token where possible | In lexicon vN or `E_LEX` |
| **Sentence** | One operation: `verb arg*`, one line, fixed arity per verb, no brackets | Parses or `E_SYN` |
| **Paragraph** | Sentences ended by a blank line = one transaction: all decode or none. The codec applies it to the working patch text | Whole paragraph accepted or rejected |
| **Context** | `(working patch, lexicon version, node-type facts)`. Names and ids mean nothing without it. Kept minimal: only names, ids and a version number are shared | Decode needs `(text, lexicon vN, patch)` |
| **Meaning** | The effect: the patch after applying the sentence passes the same oracle predicates and gives `frame_stats` within tolerance at a fixed time and seed | Oracle equivalence, never bit-exact |
| **Valid sentence** | Passes four levels in order, stops at the first failure (below) | Error code |
| **Encode** | `.inf` (the expressible subset) → canonical sentences. `encode(decode(x)) == x` holds for canonical x only | T1 |
| **Decode** | Sentences → `.inf` text (deterministic table lookup); also → gloss in a human language | T1, T3 |
| **Learning** | The lexicon changes between versions; model weights do not. A macro is promoted only through the gate, retired when it stops paying for its context | lexicon diff + held-out re-test |

### Validity levels and errors

| Level | Failure | Code | Example (illustrative) | Reply carries |
|---|---|---|---|---|
| 1 Lexical | word not in lexicon vN | `E_LEX` | `blurr b` | nearest 3 words |
| 2 Syntactic | wrong verb arity or arg kind | `E_SYN` | `set b.radius` | the verb's signature |
| 3 Semantic | name missing, key unknown, value out of range, cable not legal | `E_SEM` | `set b.radius 9` | min, max, current (ranges from generated node facts) |
| 4 Field | kernel fails to compile in its domain | `E_FIELD` | `P` used in a pixel kernel | CLI `--validate` result, mapped to sentence line + Field column |

Reply shape: `{ok, errors:[{code, level, line, hint}]}`; the first error only (one fix per round
trip is cheaper than a list the agent misreads). Levels 1 to 3 are checked by the codec itself;
level 4 is the CLI's.

### Grammar v0 (to be shrunk by experiment, never grown to fit the tasks)

```
paragraph := sentence+ blank
sentence  := verb arg* NEWLINE
verbs     := ask add set wire cut del field        # 7; `commit` dropped, `probe` is not a sentence
name      := paragraph-local name given by `add <type> as <name>`, or an id that existed before the paragraph
ask       := ask <type>        # trimmed `--describe --json`: keys, ranges, slots (counted as context)
field     := field <name> <verbatim Field text>    # `;` allowed, `#` not allowed in a field sentence
```

Rules: one canonical spelling per op; fixed argument order; numbers without trailing zeros;
unknown words are errors, never guessed. v0 covers only what `.inf` nodes, params and links can
say. `mod`, `expr`, `glob`, `clip`, `flags` are out of scope for v0 and are counted as excluded in T1.
A probe (`--frame`) is a separate call after the paragraph, never inside it.

### Lexicon row

`word | kind | core expansion | gloss en | since | uses | tokens saved`. Core words and SPEC are
public and committed. Mined macros are private (local file, gitignored). Every log line stores the
core expansion plus the gloss, so audit never depends on the private file. A second gloss
language is added when someone needs it.

## Benchmark and tests

Tasks: 30 = 10 build, 10 tweak (ships a start patch), 10 Field. Split 20 dev + 10 held-out,
written and frozen first in their own commit with a sha256 recorded. The verdict uses held-out only.

| ID | What | Pass |
|---|---|---|
| B0 | 30 tasks through today's loop: patch skill as system context, layout step skipped, same harness | recorded once, frozen |
| B0' | Control: same tasks, `.inf` text over a resident loop (one call = validate + explain + frame) | recorded once, frozen |
| B1 | Same tasks in the new language | beats B0 AND B0' (below) |
| T1 | Round trip: encode(decode(x)) == x over canonical sentences; `.inf` → sentences → `.inf` equal over every patch the v0 grammar can express (report how many are excluded and why) | 100% of expressible |
| T2 | Fuzz: random valid sentences all decode to a patch that `--validate`s | 0 crashes |
| T3 | Each error code has a negative case with the right hint | all present |
| T4 | Cold write: 3 models see only SPEC (≤2k tokens), write the held-out tasks | ≥90% valid first try |
| T5 | Meaning: sugar and core pass the same oracle and give `frame_stats` within tolerance at fixed t | 100% |
| T6 | Field frozen: `git diff --quiet main -- src/core/field tests/field` | clean |
| T7 | Decode-back: agent B re-encodes agent A's intent and its patch passes the same oracle | ≥95% |
| FINAL | One script, one JSON line | gate |

Oracle (same code for every arm): a predicate list per task (required node types present,
required edges by kind, params within tolerance, no `E_*`, `frame_stats` in a range at fixed t and
seed, rendered with the CLI `--frame`; tasks using Random set `f seed`). No exact hash.

Metric: total tokens (in + out) per solved task, counted by each model's own counter, plus UTF-8
bytes as a neutral unit; round trips second; report dollars. Every token that enters context is
counted in both arms, including the skill and the SPEC. Layout and `Comment` nodes are skipped in
every arm (run `tools/patch-layout.py` afterwards, uncounted).

Verdict (Phase 2): paired bootstrap over tasks. KEEP-GOING only if, on the held-out set, the 95%
CI of the total-token ratio vs B0' is below 1, round trips drop, and oracle pass is not lower by
more than one task, on at least 2 of 3 models. Pilot first: 5 dev tasks, one model, all arms; if
the token gain vs B0' is under 20%, STOP and report.

Budget: the full run is about 30 tasks x 3 runs x 3 arms x 3 models, roughly 800 sessions.
State the spend before starting; the pilot is about 45.

## Principles

1. No bloat: SPEC ≤2k tokens, a word must beat its context cost.
2. Short, precise, rule-based: fixed arity, one canonical form, no ambiguity.
3. Lossless on canonical text; decode is many-to-one for sugar.
4. Auditable: any text decodes to `.inf` and a gloss; the core is public.
5. One semantics: never a second engine; agent work opens as a normal patch (layout is run afterwards).
6. Measured: baseline first, held-out only for verdicts, KILL if the numbers do not move.
7. Never promote a macro without re-running T4 on held-out; retire on any drop (dialect drift, Goodhart).

## Phases

| Phase | Where | Work | Done when |
|---|---|---|---|
| 1 | **Air**, no build, no model runs | tasks + oracle, grammar v0 + SPEC, codec (sentences ⇄ `.inf`), T1, T3, T6 as python tests | `PROMPT.md` done-check passes |
| 2 | **Pro**, built app | build, harness for B0, B0', B1, pilot, then full run, T4, T5, T7, verdict | KEEP-GOING or STOP with the table, appended under Results |
| 3 | Pro | learner and self-play (Block C) | only after Phase 2 says KEEP-GOING |

Phase 2 rules to carry over: use the CLI, not the live app; if the live RPC is ever used, only
when the owner's app is closed (a second instance overwrites the shared `control_token`) and with
`INFINITE_CONTROL_PORT` set; pin model ids and settings and run every arm on every model; cap
turns (15) and dollars per task.

## Results

(none yet)
