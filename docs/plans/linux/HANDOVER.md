# Linux port — handover (phase-01 follow-ups)

Written 2026-09-14. Everything below is state of branch
`feature/linux-step-01-followups` in worktree
`.claude/worktrees/linux-eval`.

## Where things stand

P1 (desktop) is **functionally complete and verified by real execution**, not
by reading code. Evidence gathered this session, all in the arm64
`infinite-linux-dev` container:

| Check | Result |
|---|---|
| Linux clang build | exit 0 |
| `ldd` — no direct libGL/libGLX/libEGL | holds (the Audacity #12093 CI assert) |
| `ldd` — no direct libX11 | holds (GLFW dlopens it) |
| `local.sh test --fast` | 22/22 |
| `--group ui,3d,compositing` | 41 pass, 0 fail, 1 pre-existing xfail |
| `headless-tests.sh` | all pass, incl. a real SIGSEGV→backtrace and a real TLS request to api.github.com |
| macOS `--fast` | 22/22 (no regression from the MediaDecodePortable / SubjectMaskOnnx extractions) |

## Commits on this branch

```
458da32 feat(linux): hide Syphon nodes, ship a window icon, add patch round-trip test
6495926 build(linux): declare libfreetype-dev and record tinyfiledialogs licence
1bd831f fix(linux): collect real Linux shots instead of committed macOS PNGs
da2fdbd perf(linux): cache fontconfig config, resolved paths and FT_Face
```

### The one finding that mattered most

The visual-proof chain was broken in two places at once, and the failure mode
was silent-and-flattering: `xvfb-harness.sh` collected artifacts with
`find . -maxdepth 2 -name "*.png"`, which swept up PNGs **committed to the
repo** (`docs/screenshot.png`, `website/full_page_capture.png`,
`assets/Infinite*.png`) — every one captured on macOS. Meanwhile the driver's
one genuine render went to `/tmp/infinite_hygiene_shot.png` and was never
collected, and neither `--fast` nor `--group` sets `RUN_SHOT` at all. So the
downloaded artifact looked like proof Linux rendered correctly while
containing no Linux pixels. Fixed in `1bd831f`. **Never widen that collection
step back to a bare `find` over the worktree.**

## Left to do, in order

1. ~~Confirm the container build.~~ **Done.** The build caught a real defect
   the review had not: `SetWindowIcon` called `stbi_load`, which does not
   exist in this target — the one `STB_IMAGE_IMPLEMENTATION`
   (`EnvironmentNode.cpp`) is compiled with `STBI_NO_STDIO`, so only the
   `*_from_memory` loaders are emitted. Invisible on macOS and Windows since
   neither takes that branch. Fixed in `fix(linux): decode the window icon
   from memory`. After the fix: build exit 0, `--fast` 22/22, and all six
   `shots.sh` PNGs real (216–364 kB). `2d-text-compositing.png` was inspected
   directly and FreeType text rasterizes correctly through the new face
   cache. **Still to run: the `ui,3d,compositing` group and macOS `--fast`.**

2. **Register `INFINITE_SYPHONPATCHTEST`.** The fixture exists in `main.cpp`
   and prints `SYPHONPATCHTEST OK`, but nothing runs it. Add it to
   `.claude/skills/run-infinite-hygiene/driver.sh` and/or
   `.github/scripts/headless-tests.sh`. An unregistered self-test is worth
   nothing.

3. **Add a group step to CI.** `.github/workflows/build.yml`'s `linux` job
   runs only `xvfb-harness.sh --fast`. Add a second step running
   `--group ui,3d,compositing`, which is where the real rendering coverage
   lives.

4. **Generate `tools/linux/reference-shots/` on macOS**:
   `OUT_DIR=tools/linux/reference-shots tools/linux/shots.sh`, downscale to
   ≤800px, commit as small PNGs. The harness already ships them alongside the
   Linux shots so the two can be compared in one downloaded artifact.

5. **Fix the ONNX build-tree RPATH** so the build binary resolves
   `libonnxruntime.so.1` via `$ORIGIN` — makes build == ship, which is what
   the AppImage needs.

6. **Update `docs/plans/linux/README.md`'s bottom `## Status` table.** It
   still says "not started" for all six phases while the phase table directly
   above it marks P0 COMPLETE (`b25b5bd` / Run 34769650449).

7. **Push both `feature/linux-step-01-desktop` and
   `feature/linux-step-01-followups`** to get x86_64 + GCC CI evidence.
   Everything verified so far is arm64 + clang. Pushing `feature/linux-step-*`
   is pre-authorised.

## Decisions that are the owner's, not mine

- ~~FFmpeg licence for P3.~~ **Settled 2026-09-14 — P3 is unblocked.** GPL
  FFmpeg + libx264, gated behind `INFINITE_ENABLE_GPL_CODECS` (default ON on
  Linux). Full reasoning and the three binding conditions are in
  [phase-03-media.md](phase-03-media.md). Short version: copyright was never
  the issue (the binary is already GPLv3 via the VST3 SDK); the real exposure
  is H.264 *patents*, which is Linux-specific because macOS and Windows get
  their encoder from the OS vendor. Accepted, because this is what every
  comparable FOSS tool ships and option (b) would make Linux record a
  different file than the other two platforms.
- **Merging to `main`.** Owner merges. Do not merge, do not push `main`.
- **FreeType: static FetchContent vs system-dynamic.** Currently
  system-dynamic via pkg-config. Fine for the AppImage either way; worth a
  deliberate call before P5 packaging.

## Housekeeping the owner needs to action

The **main worktree** `/Users/namansoni/infinte` is on
`feature/linux-step-01-desktop` and still holds the *same* Syphon/window-icon
changes uncommitted (`M CMakeLists.txt`, `M src/main.cpp`). They were exported
as a patch and are now committed here as `458da32`, cleaned up. Discard them
in the main worktree rather than committing both copies.

## Working rules that bit this session

- Three-sided `Platform::` obligation: every function in `src/platform/Platform.h`
  needs a definition in `Platform.mm`, `win/*.cpp` **and** `linux/*.cpp`, with
  byte-identical signatures. A stub is legitimate; a missing definition is not.
- No `__linux__` / `_WIN32` in `src/nodes/`: use `#if defined(__APPLE__)` fast
  path, `#else` portable default. Flip polarity rather than add branches.
- Never bare `git stash` / `git stash pop` in a worktree — the stack is shared.
- A fresh worktree needs
  `git submodule update --init --recursive external/vst3sdk` before the macOS
  build will configure. If a configure fails partway, `rm -rf build` before
  retrying: `driver.sh` sees the orphaned `CMakeCache.txt` and takes the
  "already configured" branch straight into `make: Makefile: No such file`.
