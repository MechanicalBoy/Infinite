# Pilot (Sonnet 5.5, dev tasks b01 b04 t01 t04 f01, 3 arms, 1 run each, Air, pinned app)

| Arm | Pass | Tokens/session (all) | Tokens/session (fresh) | Turns | Cost (5 runs) |
|---|---|---|---|---|---|
| B0 | 5/5 | 101,719 | 4,556 | 6.2 | $0.165 |
| B0p | 5/5 | 84,763 | 4,276 | 5.2 | $0.147 |
| B1 | 5/5 | 21,132 | 2,134 | 3.8 | $0.064 |

B1 / B0p: fresh 0.50, all 0.25, cost 0.44. B1 / B0: fresh 0.47, all 0.21. Gate (at least 20 percent cheaper on fresh
tokens vs B0p, paired, both passed): **passed**, so the full run goes ahead.

## Pilot v1 (kept as evidence, not a result)
B0 and B0p passed only 2/5: valid patches using a `Star` node and a `Ramp` node were failed by an oracle that required
`Shape` and `FieldPixel`. Goals named no node, so only B1's spec steered to them. Fixed as tasks v2 (PHASE1-NOTES.md).

## Caveats
- One run per task, one model; no CI yet (the full run adds 3 reps, 3 models, bootstrap).
- Most of the `all` gap is context size: the skill is about 30 KB, the SPEC about 3.4 KB. `fresh` and `usd` are the gated metrics.
- App: the Pro's build at the time (checksum b8533d65daf8), which includes uncommitted v0.6 work; recorded per run in `app_sha`.
