# Arrangement overhaul — handover

Written at the end of WP8, the last work package. Everything in the plan is
built; nothing is merged.

## Where things are

| | |
|---|---|
| Worktree | `/Users/namansoni/infinte/.claude/worktrees/arrange-step-07` |
| Tip branch | `feature/arrange-step-10-thumbs-waves` (WP8) |
| Authoritative plan | `docs/plans/arrangement/overhaul-prompt.md` — each WP's **"As built"** section beats its original brief wherever they disagree |
| App copy | `~/Desktop/Infinite.app`, rebuilt after every green build |

```
main
 └─ …WP6 bd19fcb
     └─ feature/arrange-step-09-export-queue   87305de (WP7a) → 2ebe2f1 (WP7b) → 357a757 (WP7c)
         └─ feature/arrange-step-10-thumbs-waves   (WP8)   ◄ tip
```

Branches are **stacked**, not independent — WP8 contains WP7 contains WP6.
Merging the tip merges the whole overhaul. **The owner merges; no session does.**

## What remains

| Step | Note |
|---|---|
| Run the `verify-gate` agent on the tip branch | The plan asks for it explicitly as the final gate. Advisory — it reports, it does not block or merge |
| Merge | Owner only |

## State of the test suite on this machine

Treat these as the baseline; a run that matches them is clean.

| Driver | Expected |
|---|---|
| `run-infinite-hygiene --fast` | **29/29** |
| `run-infinite-hygiene --full` | **75 passed, 2 failed, 3 xfail** |
| `panels-sweep` | **8/8** |
| `audio-pipeline-sweep` | **11/15** |
| `av-sync-sweep` | **18/18** |

The failures that are *expected* and **not** regressions:

| Fixture | Why |
|---|---|
| `AUDIOLIFECYCLETEST`, `AUDIORECOVERYTEST` | This machine cannot open an audio device (CoreAudio `-10875`). Both fail at `AudioEngine::Start succeeds`. Everything downstream of that line is a cascade |
| `MOLDERTEST` | Pre-existing, unbaselined, handled on its own branch. Do not fold it into this work |
| `AUDIOPARAMSWEEPTEST` | 423 baselined blind spots. Count them (`grep -c '\[FAIL\]'`) — 423 means nothing new |
| `GROUPTEST`, `DRAGTEST`, `PLUGINDRAGTEST` | Listed in `known-test-failures.txt`; the driver prints them as `[xfail]` and that file IS the confirmation |

The same device gap makes three assertions print `SKIP` rather than run:
the WP7 end-to-end WAV take, WP8's "playback fills the waveform", and the
render fixture's live-rate check. **Re-run `INFINITE_ARRANGERENDERTEST` and
`INFINITE_ARRANGEWAVETEST` anywhere an audio device opens** — that is the
single largest hole in the verification.

## Rules that were in force and should stay in force

- Never UI-script the ImGui canvas. Verify with fixtures and code reading; the owner checks visuals by hand.
- After every successful build, `cp -R build/Infinite.app ~/Desktop/Infinite.app`.
- Every `Platform::` change needs **both** sides — `Platform.mm` and `win/PlatformWin.cpp`. WP7 added `RevealInFileManager`; the Windows side is written but **still uncompiled** (no Windows machine here).
- **Never run two hygiene/sweep drivers at once** — they share `/tmp/infinite_test_<NAME>.log` and corrupt each other's verdict.
- zsh: `INFINITE_$t=1 ./Infinite` does not expand. Use `env INFINITE_$t=1 …`.

## The three invariants the whole overhaul rests on

| Invariant | Where it is enforced |
|---|---|
| `gArrange` is the only arrangement state | No parallel model, no bridge. The WP5b bridge deletion is what made this true |
| `gArrange.revision` is the only change signal — one edit = one bump = exactly one rebuild | Every edit path (paste, drop, split, duplicate, undo, drag-restore) bumps it; the audio topology, the compositor and WP8's visual caches all key off it and nothing else |
| A clip's peak cache always matches the clip's shape | WP8's `ArrangeClipShape` stamp. The subtle half is the **audio thread**: it can still be mid-block on the old topology when an edit lands, so buckets arrive after the cache was zeroed with indices that are still in range. The stamp is the only thing that can reject them |

If a future change adds a cache keyed on the model and filled asynchronously,
that third row is the shape to copy — and `invariant-interaction-audit` is
the skill that finds when it was not.

## Debts, collected

| Debt | From |
|---|---|
| The render overwrite check runs at enqueue, not at start | WP7 |
| The export queue is session-only (by design); only render defaults persist | WP7 |
| `Settings::renderSampleRate` is serialised and read by nothing — kept for patch-format compatibility | WP7c |
| "Match Clips" size detection has no fixture (needs live textures) | WP7 |
| `settings.zoom` / `settings.scroll` persisted but unused | WP6 |
| Thumbnail refresh is time-based (1 s), not content-based | WP8 |
| The Windows `RevealInFileManager` has never been compiled | WP7 |
