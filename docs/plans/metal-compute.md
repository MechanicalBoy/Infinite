# Metal compute for particles and simulations (R556): design, scope and gates

Written 2026-10-13. Status: parked (R556, dropped from v0.4.7 on 2026-10-07, `docs/plans/parked-ideas.md`). This doc settles the scope so the work can start the day it is un-parked.

## What was discussed before, and what was not

- Discussed once, as quest R556 "GPU compute path: Metal compute spike for particles/sims". The reason given: the particle system runs on the CPU and is capped at 200,000 (`src/nodes/SimulationNodes.cpp:67`), and macOS OpenGL is 4.1, which has no compute shaders.
- Never discussed or planned: replacing the renderer. Infinite draws with OpenGL on all three platforms (GLFW, core profile 3.3 requested, `src/app/Startup.cpp:916-924`; macOS grants 4.1). On macOS that GL runs on Apple's Metal-backed driver, so "using Metal" already happens underneath without Infinite writing any Metal.
- Known side effect of that layer: GPU timer queries on macOS flush the context and distort frame time (perf tracker `docs/plans/perf/README.md`, `INFINITE_BENCH_GPUTIMERS=0`).

## Decision: scope

1. The renderer stays OpenGL. A Metal renderer is a rewrite of every draw path for no measured gain, and would fork the three-platform parity rule.
2. Metal is used for compute only, on macOS only, for the work that is CPU-bound today: the particle system first, then Cloth and Ocean if the first one pays.
3. Windows and Linux keep the CPU path. They are not given a compute path in this plan. If one is wanted later it is a separate decision (GL 4.3 compute raises the minimum GPU requirement and drops older machines, which the owner's audience on Windows is likely to include).
4. The CPU path stays as the reference and the fallback: same node, same parameters, same saved patches, same result within a stated tolerance. A patch must look the same on all three platforms, only faster on macOS.

## Gate before any build

Measure first. The doc's premise (the CPU path is the limit) is not yet measured.

| Gate | How | Pass |
|---|---|---|
| G1 CPU cost | `INFINITE_BENCH` B4/B6-style run of a Particle System at 50k, 100k, 200k with `GPUTIMERS=0`; per-frame CPU ms of the cook and of the VBO upload | cook plus upload is more than 25% of a 16.7 ms frame at a count a user would set (50k or more), otherwise stop: nothing to gain |
| G2 Spike | one Metal compute kernel integrating positions for N particles, called from the app, N up to 1M | 1M particles update in under 2 ms on the slowest supported Mac |
| G3 Hand-off | cost of getting the result into the GL draw | under 1 ms at 200k, or no copy at all |

If G1 fails, close R556 as "not needed" and say so in the tracker.

## Design (only if the gates pass)

- Where it lives: a macOS-only compute unit beside `src/platform/` (Objective-C++ `.mm`), behind one small interface (`ComputeBackend`: create buffer, run kernel, read or share result) with a CPU implementation used everywhere else. The three-platform rule (`windows-parity`, `linux-parity`) is met by the CPU side being the same interface, not by an empty stub.
- Data hand-off to GL, in order of preference:
  1. Unified memory: on Apple silicon a shared-storage `MTLBuffer` and the GL vertex buffer can be filled by one `memcpy` of the finished positions; at 200k particles × 16 bytes that is 3.2 MB per frame, expected well under 1 ms (G3 verifies).
  2. IOSurface-backed textures for image-shaped results (Reaction-Diffusion style), shared by Metal and GL without a copy.
  3. Do not use a read-back of a GPU-written buffer to the CPU on the render thread: it stalls.
- Threading: kernels are encoded on the render thread and committed without waiting; the result is consumed next frame (one frame of latency, stated in the node's help) or waited on with a bound. Nothing touches the audio thread.
- Determinism: GPU float math is not bit-identical to the CPU. Particle systems seeded from a patch must remain visually the same; the check is a statistical comparison (centre of mass, spread, count alive after N frames), not byte equality. Export renders must pick one path per render and say which in the log.
- Fallback: if the Metal device is missing, the kernel fails to compile, or the device is lost, switch to the CPU path for the rest of the session and log it once. Never fail the patch.
- Save format: unchanged. No new parameters. No "GPU" checkbox: the node chooses (plugin-simple rule).
- Headless: `--frame` and `--render` must use the same selection logic, or tests and exports silently differ from the app.

## Risks

- Maintenance: a second implementation of each simulation doubles the surface that has to stay equal. Mitigation: the first node only, with the statistical equality test in CI on macOS.
- Linux and Windows users get no speed-up while Mac users do, so benchmarks and reviews must say which platform produced a number.
- Apple deprecates OpenGL: if the GL driver is ever removed, a Metal compute unit is a small part of the real problem (the whole renderer). This plan does not address that; it should be a separate decision made on evidence of the deprecation date, not now.
- GPU timer distortion (above) means a before/after comparison must use wall frame time, not GL timer queries.

## What this plan does not claim

- No measurement of CPU particle cost has been made for this doc; G1 is that measurement.
- No Metal code exists in the repository today; `grep -rli metal src` returns nothing.

## Order if un-parked

1. G1 measurement and report (no code).
2. G2 spike on a branch, discard if it misses.
3. Particle System behind `ComputeBackend`, CPU parity test, macOS-only GPU path.
4. Re-measure with the same bench; keep only if better (the keep-only-if-better gate in `feedback_efficient_ab_workflow`).
