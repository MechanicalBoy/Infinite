# Lens 7 — Correctness

**Question:** Is it right, what guarantees does it make, what could silently
undo them, and what proves it stays right?

**Not this lens:** whether it's fast (→ 6), or whether it's wired at all (→ 1b).
This lens assumes it runs and asks whether the answer is correct.

## Trigger questions
- Does the change contain math: DSP, colour, blending, matrices, interpolation, statistics, FFTs?
- Does it establish a guarantee (clamped, normalised, in scale, in budget, in sync, consistent)?
- Does the same computation exist on two paths (CPU vs GPU, macOS vs Windows, bytecode vs GLSL)?
- Does it read external input (files, patches, expressions, plugins, OSC, MIDI)?
- Could it produce NaN/Inf, divide by zero, index out of range, or misalign parallel arrays?
- Does anything test it, and is that test actually run by `driver.sh`?

## Sub-lenses

### 7a Math & numerics
- **Anchors:** `src/audio/DspMath.h` (reuse PolyBLEP, TPT SVF, RBJ biquads, one-pole, dB↔lin, pan, and fast tanh rather than hand-rolling), `src/core/Mesh.h` matrices, `BlendModes.*`, `PortableFft.h`, and colour conversion.
- **Rules:**
  - Colour: textures are `GL_RGBA8` with in-shader `toLinear()` for albedo and emission. Data maps stay linear.
  - Alpha blending is source-over, not additive or max.
- **Owning skills:** `infinite-code-review` (accuracy standard), `data-accuracy-sweep`.

### 7b Invariants
- **Covers:**
  - The four `IGeometrySource` invariants (`ARCHITECTURE.md`): forward all side-channels, honest stamps, separate scene-cache stamps, instancing passthrough.
  - Scale-lock or clamp guarantees in note and modulator nodes.
  - Mailbox slot limits (64).
- **Rule:** before shipping a guarantee, sweep every sibling control that runs after it, then grep for the same undo-shape in sibling nodes.
- **Owning skills:** `invariant-interaction-audit`, `geometry-transform-sweep`, `bug-blast-radius`.
- **Recurring bug patterns:**
  - Parallel-array misalignment in mesh ops.
  - Non-source-over alpha blending.
  - Lane-unsafe constant folding in Field.
  - Passthrough wrappers dropping `GetPointCloud()` / `GetCurve()`.

### 7c Edges & boundaries
- **Validate only at real boundaries:** file load, patch deserialise, user expressions / formulas / Field source, plugin hosting, and OSC / MIDI input. Internal paths trust the contract.
- **Edge checklist:**
  - Disconnected input.
  - Zero-size or empty mesh.
  - 0 or 1 elements or voices.
  - Extreme param values.
  - Tempo change or reverse playback.
  - Sample-rate change.
  - Patch saved by an older build.
- **Owning skills:** `field-compiler` (keep-last-working-program error behaviour), `plugin-host-hardening`.

### 7d Verification
- **Anchors:** `getenv("INFINITE_…")` fixtures in `main.cpp`, `.claude/skills/run-infinite-hygiene/driver.sh` (`TIER1_CHECKS` / `GROUP_*` / `FULL_TESTS`),
  `.claude/skills/run-infinite-hygiene/known-test-failures.txt`, `tests/field/`, `scripts/sweep_runner.sh`, and `scripts/audit_node_params.py`.
- **Rules:**
  - New DSP gets an analytic fixture, not "it sounds right".
  - New nodes are wired into the generic sweeps, not given one-off checks.
  - Every fixed bug class becomes a standing sweep.
  - A fixture that exists is not a fixture that runs, so check `driver.sh`.
- **Owning skills:** `run-infinite-hygiene`, `field-testing`, `verify-gate` (agent), `pillar-parity-audit` (what's verified, per platform).

## Zoom guide
| Zoom | For Correctness it means |
|---|---|
| L1 | What X promises the user (its contract), in one sentence per promise |
| L2 | The guarantees X establishes, the inputs that can violate them, and the tests that cover each |
| L3 | Guarantee → every later stage that could undo it → sibling copies of the same shape |
| L4 | The formula / clamp / index lines, checked against a reference or analytic value |
