# Robustness of the canvas and its nodes: spec and first results

Written 2026-10-13. Owner's call: robustness of the canvas and its nodes comes first, before more competitor measurement. Every row names the Infinite decision it informs; a row that cannot change a decision is not here.

Run: `python3 tools/re-survey/stress_kit.py all` (results in `~/re-output/stress/results.md`). A failure is a crash, a hang, a save that leaves a file that no longer opens, or a second save that differs from the first. A clean refusal (exit 3/4/5 with a message) is not a failure.

## Rows

| # | Stress | How | Decision it informs | Status |
|---|---|---|---|---|
| R1 | Every node type alone, wired to an Output: validate, render 2 frames, save, re-save | `stress_kit.py nodes` | Which node needs a fix before a release | 319 types, 0 failures |
| R2 | Damaged patches: cut, flipped bytes, dropped or doubled lines, NaN/inf/huge numbers, wild cable indexes, self-cables | `stress_kit.py fuzz` | Whether a bad file can take the app down on open | 300 files, 0 crashes or hangs |
| R3 | Kill the save at a random moment; the file on disk must still open | `stress_kit.py killsave` | Whether atomic save (fc683464) holds | 150 rounds, 133 killed mid-save, 0 bad files |
| R4 | Kill the GUI mid-session; reopen shows the recovery prompt with the work | owner sitting (`dossiers/A.md`) | Whether autosave is enough | pending |
| R5 | 4000-node project in the GUI: first frame, pan, zoom, select-all, delete | bench, not UI scripting: `caffeinate -dimsu scripts/bench/run_all.sh --quiet --r5 --only B6` (B6 at 4000 nodes, `mode=all` plus `mode=select` with one delete-all; rows `bench.r5_*`); first frame and feel stay an owner sitting (`PROTOCOL-projects.md`) | Canvas cull and draw budget | pending |
| R6 | Plugin that crashes or hangs while loaded and while playing | `host_audit.py` (dossier A) | Plugin isolation | done, dossier A |
| R7 | Audio device unplugged mid-play, then replugged | owner sitting | Device-loss recovery | pending |
| R8 | Eight-hour soak: memory and frame time flat | `caffeinate -dimsu scripts/bench/run_all.sh --soak-long --quiet --only B7` (B7 for 480 min; rows `bench.b7_*`, subject `bench:B7:s:480min`) | Leaks | not run |
| R9 | Random patches: 3 to 9 random nodes, legal cables, in-range parameters; render, listen, save | `stress_kit.py random` | Cable-rule and parameter-range bugs the one-node test cannot reach | 1,200 patches, 0 failures (about 40% render a picture; the rest end in a clean refusal) |

## What the first run says

- R1 to R3 and R9 found nothing. The headless load, render and save paths are sturdy against what these tests throw at them.
- What this does not cover: anything only the GUI does (canvas interaction, undo, drag-connect, the node UI), nodes that need a connected input to do real work, hardware nodes (cameras, MIDI, microphones refuse headless by design), and combinations of nodes.
- So the open risk sits in the GUI rows R4, R5 and R7, and in modulation bindings, which R9 does not yet add.

## Next

1. R9: a random-patch generator that uses the node table's input and output kinds, so cables are legal, and sets random parameters inside each parameter's range from `--describe`.
2. R8 soak on the busiest example patch.
3. Owner sittings R4, R5, R7, batched with the others.
