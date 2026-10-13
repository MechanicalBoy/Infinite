# F Timeline, workflow cost and visual design (Final Cut, Live, Logic, Bitwig): dossier

Status: done 2026-10-13 (Final Cut timeline measured by menu map; DAW workflow columns manual-derived until the timed sitting). Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/F.md`

## 1. What it is

- Block F of `coverage.md`: areas 12 (sequencing and arrangement, against Final Cut's timeline), 18 (workflow cost) and 19 (visual design).
- Reference apps: Final Cut Pro, Ableton Live 12 Suite, Logic Pro and Bitwig Studio, all installed. Licence: all proprietary, so only their manuals, their accessibility tree and their behaviour are used.

## 2. Method

- Final Cut timeline: `python3 tools/re-survey/ui_map.py run "Final Cut Pro Creator Studio"` (menus and shortcuts from the accessibility tree), read against Infinite's arrangement (`src/arrange/`, `timeline-arrangement-architecture` skill).
- Workflow cost: `python3 tools/re-survey/workflow_cost.py table --out ~/re-output/workflow-cost/workflow.md`. Ten tasks, from instrument to export, each a list of clicks, keys, drags and typed words timed with the Keystroke-Level Model (Card, Moran and Newell 1983). Infinite's steps are traced in its code and cite `path::token` (`workflow_cost.py check` fails when one goes stale). The DAWs' steps come from their manuals and stay "manual-derived" until the timed sitting (`PROTOCOL-workflow.md`).
- Visual design: `python3 tools/design/contrast.py` for the token pairs, plus a model of every preset theme's chrome text on the surfaces it is actually drawn on (window, panel, and the field well that text boxes and the library search draw).
- Not done: no source read, no decompiled code kept, no binaries or dumps committed.

## 3. Pillar map

- P1: Making the first sound takes 12 steps in Infinite and 3–4 in each DAW.
  - Audio is off at launch. Only the top-bar Start Audio chip or Shift+K starts it (`src/app/frame/StageMenuBar.cpp::Start Audio`). Every DAW plays on launch.
  - A new patch is empty: Keyboard, synth and Audio Out each come from the node picker. A DAW's new set already has a track that plays.
  - KLM: 24.8 s against 8.0–8.8 s. Task 6 (four notes, 8 steps) and task 8 (import a sample, 3 steps against 1) lose for the same reason: each new part has to be created and wired.
- P6: Infinite wins where the patch already exists.
  - Automate: Shift+drag a knob while playing records the move (2 steps, 5.4 s, against 4–5 steps and 11–13 s).
  - Modulate: LFO from the picker, one drag onto the param pin (6.8 s against 10.8–11.7 s).
  - Export: one Render click on the Output node, no dialog (2.7 s against about 6 s).
  - Over all ten tasks Infinite is last (94 s against 78–84 s), and task 1 alone accounts for the gap.
- P6: Final Cut's whole timeline is a menu of 226 shortcuts, and Infinite's covers the cutting half of it.
  - `ui_map` read 10 menus, 529 items and 226 shortcuts, but no window tree (0 AX nodes, like TouchDesigner): the timeline itself is custom-drawn, so only commands are mapped, not layout or scrub speed.
  - Parity: blade (Cmd+B there, B or Cmd+E here), delete, copy/paste, duplicate, group (Create Storyline, Cmd+G, is the nearest), enable/disable (Final Cut V, here 0), markers (M) with next/previous jump, nudge by one step, Home/End, snapping toggle (N there, the magnet button here), zoom, trim by edge drag.
  - Gaps a Final Cut user feels first: no ripple or gap close (Final Cut's magnetic storyline: Insert W, Append E, Overwrite D, Connect Q, Lift), no keyboard trim (Opt+[ , Opt+] , Extend Edit, Join Clips), no zoom-to-fit (Shift+Z), no skimming (S), no per-clip speed (Retime, Shift+N/H/B).
  - Evidence: `~/re-output/ui-map/finalcut.md`, Infinite shortcuts from `src/app/panels/HelpWindows.cpp` (Arrangement Timeline rows).
- P6: Timeline speed against Final Cut is not measured.
  - Scrub, zoom and many-clip drawing are GUI timings; the canvas is not scripted (owner rule) and Final Cut hides its window from accessibility. Infinite's arrangement has `ARRANGETEST` and `ARRANGEAUDIOTEST` for correctness only, nothing times a 1000-clip redraw.
- P1: Hint text on the field well was below 4.5:1 in 7 of 10 themes.
  - `contrast.py` passes all 42 token pairs, but it does not measure the field well. Text boxes and the library search draw `Text` at 6–7% over the panel, and `THEMECONTRASTTEST` asserted text against the window and panel only.
  - Measured hint (TextDisabled) on the resting well: Nord 3.72, Dracula 3.66, Mocha 3.78, Tokyo Night 3.84, Latte 4.08, GitHub Light 4.03, Solarized Light 4.14. Solarized Light's typed text read 4.1–4.2:1.
  - Shipped since v0.4.7 (79ac4f7d lifted text against the window and panel only). No saved state is affected; portable code, so all three platforms.
  - Fixed on `bugfix/field-text-contrast`: `CategoryColors::FieldWellBg` is the well, `Presets()` lifts text and dim text against it, the library search uses the same tint token, and `THEMECONTRASTTEST` checks 6 rows (text and dim text against window, panel and well). Infinite, Nord Light and Forest Green do not change.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P1 | New project plays a note with no setup (all three DAWs) | `src/app/frame/StageMenuBar.cpp` | gap | quest: first sound in 4 steps - start audio on launch and open new patches with Keyboard → synth → Audio Out | `workflow_cost.py` task 1 |
| P6 | Sample drop lands on a playing track (all three) | `src/app/frame/StageDropHandling.cpp` | gap | quality-gap: a dropped sample's new node wires itself to Audio Out when it is the only sink | `workflow_cost.py` task 8 |
| P6 | Note entry in a clip (all three) | `src/app/panels/HelpWindows.cpp` | gap | ignore: the sequencer must be made and wired once per patch; after that entry is clicks, like a piano roll | `workflow_cost.py` task 6 |
| P6 | Automation lanes (all three) | `src/core/GestureRecorder.h` | lead | ignore: Shift+drag records in 2 steps against 4–5 | `workflow_cost.py` task 4 |
| P2 | Modulators (Bitwig, Live M4L, Logic Modulator) | `src/app/ui/design/components/PinDot.h` | lead | ignore: one drag onto the param pin | `workflow_cost.py` task 5 |
| P6 | Export dialog (all three) | `src/app/frame/StageNodeBodies.cpp` | lead | ignore: one click, no dialog | `workflow_cost.py` task 10 |
| P6 | Zoom to fit (Shift+Z) and zoom keys (Cmd+= / Cmd+-) | `src/app/panels/ArrangePanel.cpp` | gap | quality-gap: Home/End exist, but zoom is wheel-only; add Zoom to Fit as one key | `ui_map` Final Cut View menu |
| P6 | Magnetic storyline: Insert, Append, Overwrite, ripple delete (W, E, D, Delete) | `src/arrange/ArrangeModel.h` | gap | ignore: an arrangement schedules nodes at bar positions, so closing gaps would move music; the gap-close case is a video-edit habit | `ui_map` Final Cut Edit menu |
| P6 | Retime: per-clip speed, hold, blade speed | `src/nodes/VideoSourceNode.h` | gap | ignore: speed lives on the Video node and is reachable by one click on the canvas; revisit if users ask | `ui_map` Final Cut Modify > Retime |
| P6 | Blade, markers, nudge, snapping, group, duplicate, enable/disable | `src/app/panels/HelpWindows.cpp` | parity | ignore: every cutting command has an Infinite key | `ui_map` Final Cut Trim/Mark menus |
| P1 | Readable text on every surface in every theme | `src/core/CategoryColors.cpp` | parity | ignore: fixed in this block, needs a release-notes line | `THEMECONTRASTTEST` |

## 5. Measurements

Workflow cost, steps / KLM seconds (`~/re-output/workflow-cost/workflow.md`; DAW columns manual-derived):

| # | Task | Infinite | Live | Logic | Bitwig | Infinite rank |
|---|---|---|---|---|---|---|
| 1 | Add an instrument and hear a note | 12 / 24.8 s | 4 / 8.8 s | 4 / 8.8 s | 3 / 8.0 s | 4 of 4 |
| 2 | Load a third-party plugin | 3 / 8.6 s | 3 / 7.7 s | 4 / 10.6 s | 3 / 8.6 s | 2 of 4 |
| 3 | Add a built-in effect | 3 / 8.1 s | 2 / 5.5 s | 3 / 8.0 s | 3 / 8.1 s | 3 of 4 |
| 4 | Automate a parameter | 2 / 5.4 s | 5 / 12.3 s | 5 / 13.3 s | 4 / 10.9 s | 1 of 4 |
| 5 | Modulate a parameter with an LFO | 4 / 6.8 s | 4 / 10.8 s | 4 / 11.7 s | 4 / 11.7 s | 1 of 4 |
| 6 | Enter four MIDI notes | 8 / 20.5 s | 6 / 15.1 s | 6 / 14.1 s | 5 / 14.2 s | 4 of 4 |
| 7 | Change the tempo | 3 / 4.0 s | 3 / 4.0 s | 3 / 4.0 s | 3 / 4.0 s | 1 of 4 |
| 8 | Import a sample | 3 / 10.2 s | 1 / 3.8 s | 1 / 3.8 s | 1 / 3.8 s | 4 of 4 |
| 9 | Save the project (first time) | 3 / 3.3 s | 3 / 3.3 s | 3 / 3.3 s | 3 / 3.3 s | 1 of 4 |
| 10 | Export audio or video | 1 / 2.7 s | 4 / 6.2 s | 4 / 6.0 s | 4 / 6.2 s | 1 of 4 |
|  | All ten | 42 / 94.2 s | 35 / 77.5 s | 37 / 83.6 s | 33 / 78.9 s |  |

Contrast, dim text on the resting field well (target 4.5:1):

| Theme | Before | After | Dim text before → after |
|---|---|---|---|
| Nord | 3.72 | 4.50 | #A7AEBA → #BABFC9 |
| Dracula | 3.66 | 4.50 | #939EC1 → #A7B0CC |
| Catppuccin Mocha | 3.78 | 4.50 | #979AA9 → #A6A8B6 |
| Tokyo Night | 3.84 | 4.50 | #8289A8 → #8F95B1 |
| Catppuccin Latte | 4.08 | 4.50 | #646773 → #5E606C |
| GitHub Light | 4.03 | 4.50 | #656D76 → #5E656E |
| Solarized Light | 4.14 | 4.50 | #606969 → #5A6363 (text #556A71 → #50646B) |
| Infinite, Nord Light, Forest Green | ≥ 4.5 | unchanged | |

## 6. Outcomes

- Quests: first sound in 4 steps. Audio starts on launch, and File > New opens Keyboard → synth → Audio Out wired, so task 1 is "hover, press A". Bar: task 1 at 4 steps or fewer in `workflow_cost.py`.
- Quality gaps: a sample dropped on the canvas wires its new node to Audio Out when that is the only sink. Bar: task 8 at 2 steps.
- Quality gaps (cont.): Zoom to Fit as one key in the arrangement. Bar: the whole arrangement fits the panel from a key press.
- Bug fixed with a regression check: field-well contrast (`THEMECONTRASTTEST` now checks the well). Needs a release-notes line: hint and typed text are easier to read in seven themes.
- Ignored, with reason: ripple/magnetic editing and retime (see rows above); note entry (one-time sequencer setup, then parity); the lead tasks need nothing.
- Not measured, protocol pending: timeline scrub/zoom/many-clip speed against Final Cut (GUI timing; needs a frame-time probe inside Infinite or the owner's screen recording).
- Owner sittings needed: the timed workflow sitting (`PROTOCOL-workflow.md`) confirms the DAW step lists and the KLM ranking.

## 7. Storage

- Written to ~/re-output: `workflow-cost/workflow.md`, `ui-map/finalcut.md` and the raw tree under `ui-map/20261013-075926/`.
- Deleted: the theme model and contrast scratch, and `~/re-output/tmp` (`storage.py clean-tmp`).
