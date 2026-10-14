# Tongue for films and motion design (dialects)

Status: plan, 2026-10-14. Nothing built. Gate decides whether any of it is built (below).

## Why (measured, not guessed)

`tools/agentlang/mine_tokens.py` reads local Claude session logs (never leaves the machine).
Sessions that touch `infinite-launch-video` render/assemble/new_film/film_audit, 50+ turns:

| Measure | Value |
|---|---|
| Sessions | 162 |
| Turns | 53,286 |
| Fresh tokens (input + cache create + output) | 180M |
| Output tokens | 47M |
| Cache reads | 8.0B |
| Render runs | 2,651 (100+ in the biggest sessions, which run 2,000+ turns) |

Tool-result tokens (chars / 4), where the context goes:

| Kind | Tokens | Share |
|---|---|---|
| Shell output (scripts, tools, ffmpeg, logs) | 9.1M | 66% |
| File reads (skills, lib code) | 1.9M | 13% |
| Images (frames, sheets) | 1.1M | 8% |
| Render output | 0.8M | 6% |

Caveat: the match is broad, so these sessions are film-related, not all film-only.

Reading: the cost is **iteration**. Each pass is write code, render, read noisy output, look, fix. The
model re-reads a big skill library and shell chatter every pass, and the cache-read total shows every
extra turn re-pays the whole context.

## The idea

One core grammar (sentence, paragraph, typed errors, resident check), several **dialects**: each is a
small lexicon pack plus a compiler to the tool that already does the work. The model writes the
decision (what the film is), the tool does the doing, one call returns a compact typed reply.

```
 agent ──sentences──► CODEC (core grammar)  ──► dialect compiler ──► existing engine
   ▲                     lex, syntax, sem          infinite | film | blender
   └── one compact typed reply: ok, first error + hint, lint, audit numbers, 1 contact sheet
```

| Dialect | Compiles to | Words (draft) | Check in the reply |
|---|---|---|---|
| infinite (done) | `.inf` | add set wire cut del field ask | validate, explain, frame stats |
| film | a film spec the engine renders (`acts`, `lib/*`) | act, shot, cam, type, sfx, cut, beat | lint (safe areas, palette), `film_audit` numbers, safe contact sheet |
| blender | `bpy` script run by `blender -b -P` | the generated 2,491-operator catalogue, grouped | scene summary, 1 thumbnail |

## What gets cheaper, and why

| Cost today | Dialect fix |
|---|---|
| Re-reading 340KB+ of film skills each session | A SPEC of at most 2k tokens holds the decisions the skills encode (grid, safe areas, one visual language, camera grammar not FX). Rules become lint errors, so the model is told when it breaks one instead of reading all of them first |
| Shell output is 66% of results | The resident check prints one JSON line (pass/fail, first error, a few numbers). Raw logs go to a file, read only on request |
| 2,651 renders, many full-size | `check` renders a cheap preview (low res, few frames, contact sheet) by default; a full render only on `render`. Same rule as today: no full render until asked |
| Fix loops from vague failures | Typed errors with a hint and the nearest valid word, as in v0 |
| Images (8%) | One contact sheet per check, not one image per probe |

## What stays out

- No new renderer. The film dialect compiles to the existing engine; creative taste stays with the owner.
- No FX or style words that break the film rules (camera grammar, one language per film).
- No Blender source reading (GPL). Blender is only an external process through documented `bpy`.

## Gate (same as the core language)

1. Pick 12 film tasks (4 dev-only for building the lexicon, 8 frozen held-out): each with a predicate
   oracle (acts present, cuts on beat within tolerance, safe areas clear, audio LUFS in range, loop
   difference under a threshold). Freeze first.
2. Arms: **F0** today (skills + scripts), **F0p** today plus a resident one-call check (control, so a
   win cannot come from the session alone), **F1** the dialect.
3. Same verdict script: paired bootstrap, 95% CI upper bound below 1 on fresh tokens and dollars,
   fewer turns, no more than one task fewer solved than F0p, on 2 of 3 models.
4. If it fails, STOP and keep the numbers. If F0p alone gets most of the win, ship only the check
   tool (a plain script, no language).

## Build order

| Step | Where | Output |
|---|---|---|
| 1 | Air | Film tasks, oracle, freeze (no renders needed beyond a cheap check) |
| 2 | Pro | `film_check`: one-call lint + audit + contact sheet, one JSON line. Useful even if the language is killed |
| 3 | Air | Film lexicon, SPEC, codec, tests (as Phase 1) |
| 4 | Pro | Benchmark F0, F0p, F1 and verdict |

Step 2 is the likely biggest single win, and it is independent of the language, so it comes first.

## Order against the core language

Wait for the core verdict (full run on the Air, `out/final.json`). If core says STOP, film goes
straight to step 2 only. If KEEP-GOING, steps 1 to 4 run in sequence.
