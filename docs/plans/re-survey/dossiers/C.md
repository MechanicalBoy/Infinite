# C Built-ins, stretch and engine (Live, Logic, Bitwig): dossier

Status: done 2026-10-12 for Infinite's side; the three DAW bounce sittings are pending (protocols below). Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/C.md`

## 1. What it is

- Block C of `coverage.md`: areas 2 (built-in instruments), 3 (built-in effects), 13 (time-stretch) and 1 (engine accuracy).
- Reference apps: Ableton Live 12 Suite, Logic Pro and Bitwig Studio, all installed. Licence: all three are proprietary, so only their own bounces and their manuals are used.
- Built-in devices cannot load outside their DAW, so the DAW side is a bounce sitting: the owner bounces a fixed MIDI or audio stimulus through each built-in, and the analysers read the bounces. Infinite renders the same stimuli headless.

## 2. Method

- Built-ins: `python3 tools/re-survey/builtins_kit.py make` writes `synth.mid`, `fxstim.wav` and `PROTOCOL.md` (which device in which DAW, bounce names). `builtins_kit.py infinite` renders Analog, Wavetable, Oscillator, Metallic, Equation Synth, Field Synth and ten effects plus a dry rig. `builtins_kit.py analyse` gives the two tables in section 5 (`synth_probe` and `plugin_probe` analysers).
- Stretch: `python3 tools/re-survey/stretch_kit.py` (drums, vowel, tone, sweep at 0.5x / 0.8x / 1.25x / 2x, pitch kept). Infinite's side plays arrangement Sample clips through `--audio-summary --timeline`.
- Field Synth release: every preset rendered with one 150 ms note, time from note-off to -40 and -60 dB against the peak, before and after the fix.
- Not done: no DAW source read, no decompiled code kept, no binaries or dumps committed.

## 3. Pillar map

- P5: Field Synth cut every preset dead 30 ms after note-off.
  - The voice envelope had a fixed 30 ms release (`SetADSR(2, 0, 1, 30)`) that freed the voice at note-off. The kernel's own release never sounded: bells, music box, 808, piano, the default pad's 0.3 s release. The step-21 spec says note-off releases the envelope, not cuts it.
  - Measured: all 27 presets fell below -60 dB within 30 ms of note-off; 100 ms after it every one was digital silence.
  - Shipped since 18206edb (2026-09-04, Field Synth's first commit; in every release from v0.3.0 on): needs a release-notes line.
  - Fixed and merged (2846a30a): note-off only drops `gate`. The voice frees itself after 50 ms below -80 dBFS, or after 10 s for a kernel that never decays.
  - The cut had hidden four broken presets. Future Bass Glide Sub, Acoustic Grand Piano, Rhodes and DX7 wrote their damper as `damp = if(gate > 0.5, 1.0, 0.998)` times the output: a constant gain that never accumulates. The damper now multiplies the decaying state (they release in 45–75 ms). Raindrops started new drops forever; it now stops at key-up.
  - Saved patches keep their own kernel text, so a patch saved with one of those presets now rings after key-up. Reload the preset to get the fixed damper.
  - Regression: headless smoke "a note's tail rings past note-off, then the voice frees" (the default pad still sounds 100 ms after note-off and is silent by 1.1 s).
  - Why the harness missed it: `INFINITE_SYNTHAUDIT` printed "release to -60 dB 31 ms" for Field Synth every run but asserts nothing about release. It reads 243 ms now.
- P5: Headless renders ignored the arrangement.
  - A loaded patch always opened in Canvas audio mode, so arrangement clips never played headless; a tempo-synced clip played at native speed from 0 s.
  - Fixed and merged (d6095df2): `--timeline` renders the arrangement's audio lanes. This is what the stretch kit runs on. Smoke: a 120 BPM click clip at beat 2, rendered at 60 BPM, starts at 2.0 s.
- P5: Time-stretch keeps pitch exactly and stays clean on tones, but smears and flams drums.
  - Tone and vowel: 0.0 cents at every ratio; non-harmonic -42 to -66 dB, worst at 2x.
  - Drums: 10–14 extra onsets (flams) at 0.8x–2x, hits up to 30 ms early, 3 dB of crest lost at 1.25x and 2x. A transient-aware stretch (Live's Beats mode, Logic Flex Slicing) keeps hits whole.
  - Sweep tracking 2.7 cents at 0.8x and 1.25x, 9–12 cents at 0.5x and 2x.
- P5: Built-in synths are clean at their defaults.
  - Oscillator, Wavetable and Equation Synth: 0.2 cents pitch error, non-harmonic about -84 dB at C4 and still -82 dB at C8 (no audible aliasing).
  - Analog: 3.5 cents (its drift), -61 dB at C8.
  - Metallic (41 cents, -6 dB) and Field Synth's default pad (sub-octave plus detune) are inharmonic by design.
- P5: Built-in effects are transparent where they should be.
  - EQ, Limiter and Dynamics at defaults add nothing above the rig floor (THD under -66 dB).
  - Drive reports 1.52 ms and Limiter 1.67 ms of latency. PDC aligns them against parallel paths, but the exported file is not shifted back: a bounce through Drive starts 73 samples late. DAW bounces read 0 ms (the kit's PROTOCOL measures this on their side).

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P5 | Synth release follows the patch's own envelope (all three) | `src/nodes/FieldSynthNode.cpp` | parity | ignore: fixed in this block, needs a release-notes line | smoke + `INFINITE_SYNTHAUDIT` |
| P5 | Transient-preserving stretch (Live Beats, Logic Flex Slicing, Bitwig Stretch) | `src/audio/dsp/ClipTimeStretch.h` | gap | quality-gap: drums flam (10–14 extra onsets) and lose 3 dB of crest | `stretch_kit.py` |
| P5 | Tonal stretch keeps pitch (Live Complex Pro, Logic Polyphonic) | `src/audio/dsp/ClipTimeStretch.h` | parity | ignore: 0.0 cents, -42 to -66 dB artefacts; ranking waits on the bounces | `stretch_kit.py` |
| P5 | Clean default oscillators (Live Wavetable/Drift, Logic ES2, Bitwig Polymer) | `src/nodes/AnalogSynthCore.h` | parity | ignore: -82 to -85 dB at C8; ranking waits on the bounces | `builtins_kit.py` |
| P5 | Bounce is latency-compensated against the timeline (all three) | `src/nodes/AudioEffectNode.cpp` | gap | quality-gap: an export through Drive or Limiter starts 1.5–1.7 ms late | `builtins_kit.py` |
| P5 | Headless/offline render of the arrangement | `src/core/HeadlessJob.cpp` | parity | ignore: fixed in this block (`--timeline`) | smoke |

## 5. Measurements

Field Synth, one 150 ms note at C4, time from note-off to -60 dB against the peak (48 kHz):

| Preset group | Before | After |
|---|---|---|
| All 27 presets | 0.00–0.03 s (cut) | rings by its own envelope |
| Pad, leads, basses that read `gate` | 0.03 s | 0.14–2.1 s |
| One-shots (909, toms, snare, laser) | 0.03 s | 1.3–3.9 s |
| Bells, music box, vibraphone, modal | 0.03 s | up to the 10 s cap (they ring by design) |
| Dampers fixed (Future Bass, Piano, Rhodes, DX7) | 0.03 s | 0.01–0.07 s |

Built-ins, Infinite's side (`~/re-output/builtins-kit/infinite.md`):

| Synth | Pitch err ¢ | Non-harm C4 / C8 dB | Attack ms | Release -60 s |
|---|---|---|---|---|
| Analog | 3.5 | -67.8 / -60.9 | 4 | 0.25 |
| Wavetable | 0.2 | -84.2 / -83.9 | 4 | 0.26 |
| Oscillator | 0.2 | -74.0 / -82.1 | 3 | 0.26 |
| Equation Synth | 0.2 | -84.0 / -85.4 | 7 | 0.20 |
| Metallic | 41.4 | -6.3 / -4.9 | 14 | 1.51 |
| Field Synth | 13.8 (octave -1) | -86.2 / -2.2 | 362 | 0.03 before, 0.29 after |

| Effect | Latency ms | Gain 1k dB | THD at -1 dBFS | Tail -60 s |
|---|---|---|---|---|
| Drive | 1.52 | +5.54 | -16.6 | 0.01 |
| Limiter | 1.67 | 0.00 | -104.5 | 0.01 |
| Reverb | 0 | +4.29 | tail | 0.60 (RT60 1.48) |
| Delay | 0 | +3.01 | tail | 1.51 |
| Dynamics | 0 | -3.68 | -66.1 | 0.01 |
| EQ | 0 | 0.00 | -114.2 | 0.01 |

Stretch, Infinite's side (`~/re-output/stretch-kit/infinite.md`):

| Ratio | Drums extra onsets | Drums timing ms | Crest loss dB | Vowel non-harm dB | Sweep tracking ¢ |
|---|---|---|---|---|---|
| 0.5x | 1 | 30 | -0.8 | -49.6 | 11.7 |
| 0.8x | 10 | 30 | -0.1 | -52.3 | 2.7 |
| 1.25x | 10 | 25 | -3.0 | -58.4 | 2.7 |
| 2x | 14 | 23 | -3.2 | -42.3 | 8.8 |

## 6. Outcomes

- Quests: none. Two Infinite bugs found, both fixed and merged with regression checks:
  - Field Synth cut every release at 30 ms (plus four dead dampers and Raindrops): smoke release check;
  - headless renders ignored the arrangement: smoke `--timeline` check.
- Release notes need a line for the Field Synth release (shipped since v0.3.0). It should say that a patch saved with Future Bass, Piano, Rhodes or DX7 needs the preset reloaded.
- Quality gaps:
  - transient-aware stretch: detect onsets and keep each hit whole, stretching only between them (Live Beats, Logic Flex Slicing). The bar is the drums row reading 0 extra onsets;
  - latency-compensated export: shift the rendered file back by the output path's reported latency, so a bounce through Drive or Limiter starts on time.
- Harness gap: `INFINITE_SYNTHAUDIT` measures release but asserts nothing. The smoke check now covers Field Synth.
- Ignored, with reason:
  - Metallic and Field Synth inharmonicity: by design;
  - ranking against the DAWs: waits on the bounce sittings, nothing to decide yet.
- Owner sittings needed: one bounce sitting per DAW (`~/re-output/builtins-kit/kit/PROTOCOL.md`, `~/re-output/stretch-kit/kit/PROTOCOL.md`). After each sitting, run `builtins_kit.py analyse` and `stretch_kit.py analyse` with the DAW's folder added.

## 7. Storage

- Written to ~/re-output: `builtins-kit/` (kit, Infinite renders, results) and `stretch-kit/` (kit, Infinite renders, results).
- Deleted: the scratch preset-tail renders.
