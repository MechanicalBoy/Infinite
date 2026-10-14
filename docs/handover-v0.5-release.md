# Handover: ship Infinite v0.5.0 (paste this into a new session)

You are continuing work in <repo> (branch `feature/index-scan-wave3`, main = `main`, latest release v0.4.7). Read AGENTS.md first and follow the skills it names (ship-infinite, run-infinite-hygiene, ci-failure-triage, release-notes-audit). Standing rules: NO Claude attribution anywhere (no Co-Authored-By, no "Generated with Claude Code") in commits/PRs; keep `tools/roadmap/*` uncommitted; three-platform parity; never read GPL/AGPL source; ask before downloading files; don't UI-script the ImGui canvas; after the final build copy build/Infinite.app to ~/Desktop/Infinite.app.

## User intent
The user asked for v0.5.0 ("let's call this v0.5", "can we release now?"). The release is authorized, but CI must be fully green on one commit first. Release notes lead with the UI/UX work. Publish the Tracking pack and `extensions.json` ("yes we need to publish"). Check in with the user right before merging to `main` (it redeploys the public website) and before `gh release create`.

## Current blocker
CI run 38052545220 (commit 8f21e185): everything green (macOS, Windows x64/ARM64, Linux gcc, AppImage, distro smoke, sanitizers after rerun, design ratchet) EXCEPT Linux clang at render-check `modulation`. It reproduces locally on macOS (`python3 tools/render-check.py modulation`).

Findings so far:
- `tests/render/modulation.inf` = Shape(Star) + `mod shape sizeX lfo ...` + `expr shape rotation sin(t) * 90`.
- Old binary `/Users/namansoni/infinte-extensions/build/Infinite.app/Contents/MacOS/Infinite` (commit 6c785fe8) matches the golden; HEAD does not (golden ~16-spike star, HEAD ~10).
- Variant tests (scratchpad e*.inf): the `mod` line renders identically old vs new; the difference is only the `expr ... rotation` line. Constant `expr rotation 0/45` and `sin(0.0)*90` are identical old vs new, but `t*90` and `sin(t)*90` differ: the value of `t` (or how expressions are evaluated per headless frame) changed. Old gave the same image as rotation 45 for both, which is suspicious and may itself be wrong; decide which behaviour is correct before touching the golden.
- Headless frame stepping is `src/app/selftest/Headless.cpp` ~1510-1530 (`SetOfflineVideoTime`, `ApplyModulationAndPalette(frameId)`); Headless.cpp, Patch.cpp and ShapeNode.h are unchanged since 6c785fe8. Suspects: expression/`t` evaluation, Transport offline time, ApplyModulationAndPalette (src/core/GraphNode.h:80 comment, src/app/AppState.cpp), Field changes (055d133e adds beat/noteNum/tick/deg/rand reserved names).
- A `git bisect run` is in progress in the separate worktree `/Users/namansoni/infinte-base` (script `.../scratchpad/bisect_step.sh`, logs /tmp/bisect_run.log and /tmp/bisect_trace.log). CAUTION: the first two steps logged `FAIL modulation: --frame failed (exit 0) ""`, which may be a harness problem (binary not launching in the background, or an older commit failing differently) rather than the golden mismatch. Check /tmp/bisect_check.log before trusting it; if bogus, bisect by hand or just debug the `t` evaluation. Run `git bisect reset` in infinte-base when done.
- Fix the code if the regression is a bug. Regenerate the golden (`python3 tools/render-check.py --update modulation`) only if the new output is verified intended.

## Remaining release steps (in order)
1. Fix modulation, rebuild, run `python3 tools/render-check.py` and the driver gate (`.claude/skills/run-infinite-hygiene/driver.sh`), commit, push, wait for a fully green CI incl. Windows (~40 min). Pre-existing flakes: RECEXPORTTEST (baselined), PLUGINDRAGTEST, NETWORKTEST HTTP 403 (rerun with `gh run rerun <id> --failed` after the run completes).
2. `origin/main` has an extra commit 4e7ffe55 (README Download buttons): merge main into the branch first.
3. Bump `INFINITE_VERSION` to 0.5.0 and `INFINITE_VERSION_RC` to 0,5,0,0 in CMakeLists.txt (~lines 22 and 27) and `website/index.html:537` (v0.4.7 -> v0.5.0); commit.
4. Audit `docs/release-notes-v0.5.0.md` (untracked) with the release-notes-audit skill (verify Sketch 3D 6 presets, 15 templates, 0.45 zoom collapse, Ocean/Audio Ribbon orientation, Field Notes category); commit it.
5. Confirm with the user, merge to `main` (deploys website), wait for CI on the main commit, then `gh release create v0.5.0 --title v0.5.0 --notes-file docs/release-notes-v0.5.0.md --target main`, then `.claude/skills/ship-infinite/driver.sh release` (DMG + Windows zips + AppImage), commit/push the rebuilt DMG.
6. Upload the Tracking pack and `extensions.json` to the release. macOS pack exists (not committed/published): `/private/tmp/claude-501/-Users-namansoni-infinte/004f92c3-6b69-4cfa-b754-a03542fc3350/scratchpad/pack/tracking-macos.zip`, 25M, v0.1.0, sha256 a42ef2419fb23e7159566b8a63b1cbd3a6a8c7d187d142bc925f84ba034c8ede; build script `tools/tracking-spike/build_pack.sh`; catalog URL `https://github.com/n1m21n/Infinite/releases/latest/download/extensions.json`. Open question for the user: Windows/Linux packs need ORT .dll/.so downloads (ask permission) or ship macOS-only.
7. Final build and copy build/Infinite.app to ~/Desktop/Infinite.app.

## Accepted known issues (not blockers)
Sketch SVG per-frame re-parse, main-thread JS budget, MIDI device-loss detection, Windows MIDI timer granularity. Local `--describe` (all types) aborts on macOS from a CoreMotion TCC violation (known; single-type works).
