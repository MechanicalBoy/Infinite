# Arrangement overhaul — handover

Written at the end of WP8, the last work package. Everything in the plan is
built; nothing is merged.

## Where things are

| | |
|---|---|
| Worktree | `/Users/namansoni/infinte/.claude/worktrees/arrange-step-07` |
| Tip branch | `feature/arrange-step-11-main-sync` — WP8 + `main` merged in + two follow-ups (see *Post-WP8* below). **Merge this one** |
| WP8 branch | `feature/arrange-step-10-thumbs-waves` — unchanged, for reference |
| Authoritative plan | `docs/plans/arrangement/overhaul-prompt.md` — each WP's **"As built"** section beats its original brief wherever they disagree |
| App copy | `~/Desktop/Infinite.app`, rebuilt after every green build |

```
main
 └─ …WP6 bd19fcb
     └─ feature/arrange-step-09-export-queue   87305de (WP7a) → 2ebe2f1 (WP7b) → 357a757 (WP7c)
         └─ feature/arrange-step-10-thumbs-waves   69ac331 (WP8)
             └─ feature/arrange-step-11-main-sync   035de32 (merge main) → f8ef1d0 → 04639e7   ◄ tip
```

Branches are **stacked**, not independent — WP8 contains WP7 contains WP6.
Merging the tip merges the whole overhaul. **The owner merges; no session does.**

## What remains

| Step | Note |
|---|---|
| ~~Run the `verify-gate` agent~~ | **Done** on `04639e7` — *clear to merge*. See *Post-WP8* |
| Merge `feature/arrange-step-11-main-sync` into `main` | Owner only. `main` is already merged in, so it fast-forwards |

## Post-WP8 (the sync branch)

| Commit | What | Why |
|---|---|---|
| `035de32` | Merge `main` (15 Linux-port commits) | No textual conflicts, but two semantic ones — next row |
| `f8ef1d0` | `PlatformLinux.cpp`: `PollTrackpadMagnificationDelta` `float` → `double`; `RevealInFileManager` Phase-0 stub | Linux declared the first with the wrong return type and lacked the second (WP7). Both would have broken the Linux build after the merge. **`feature/linux-step-01-desktop` carries the same `float` and needs the same fix plus a real reveal** (xdg-open / `FileManager1.ShowItems`) |
| `04639e7` | `RunTopology` flushes the bucket in progress when a playing head is outside every window | A clip followed by a gap never published its last 1/16 beat — a flat notch at its right edge. `ARRANGEWAVETEST` G now renders past the clip end and asserts 32/32 (still SKIPs without a device) |

`verify-gate` on `04639e7`:

| Check | Result |
|---|---|
| hygiene `--full` (pre-`04639e7`) / `--fast` (post) | 75/2/3 / 29/29 — baseline |
| panels / audio-pipeline / av-sync / shortcuts | 8/8 · 11/15 (0 new, 423 blind spots) · 18/18 · 41/32 clean |
| windows-parity | pass — mac/win/linux signatures match for both new `Platform::` functions |
| invariant-interaction-audit | pass — both `ClipPeakRing::Write` sites stamp-guarded |
| infinite-code-review | pass |
| data-accuracy-sweep | 8/9 + `IMAGERESYNTH_SELFTEST`. Both failures **pre-existing**: `IMAGERESYNTH_SELFTEST` is WP4's documented 35 texture-less types; `UTILTEST` ("1 upload, SUSPECT - re-uploading through Null") reproduces identically on a build with no arrangement code (`linux-eval` worktree, `e447504`) |
| Routing gap | `verify-gate`'s table has no arrangement row — `src/arrange/` was covered by the always-run skills and the per-WP audits only |

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
| `UTILTEST`, `IMAGERESYNTH_SELFTEST` (data-accuracy-sweep only) | Pre-existing, not arrangement — see *Post-WP8* |

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
