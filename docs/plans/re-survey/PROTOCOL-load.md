# Load protocol: N-track template per DAW (Block B, area 6)

One sitting per DAW, about 15 min. The same chords Infinite renders in `load_bench.py`.

## Stimulus

- MIDI: `~/re-output/load-bench/chords-30s.mid` (C, Am, F, G held chords, one per bar, 120 BPM, 32 s).
  Rebuild with `python3 tools/re-survey/load_bench.py midi ~/re-output/load-bench/chords-30s.mid --seconds 32`.
- Audio device: built-in output, 48 kHz, buffer 256.

## The template (same in every DAW)

| Track part | Live | Logic | Bitwig |
|---|---|---|---|
| Synth | Wavetable, default preset | Retro Synth, Wavetable mode | Polymer, default |
| Effect | Reverb, default | ChromaVerb, default | Reverb, default |
| Clip | the MIDI file, looped | the MIDI file, looped | the MIDI file, looped |

1. Build one track: synth, then effect, then the MIDI clip looped.
2. Duplicate it to 8 tracks. Save as `load-8`.
3. Duplicate to 32, 64, 128 tracks, saving `load-32`, `load-64`, `load-128`.

## Each size

1. Open `load-N`, press play, wait 10 s.
2. Tell Claude "Live N playing" (or Logic, Bitwig). Claude runs, without touching the app:

   ```
   python3 tools/re-survey/app_bench.py run "Ableton Live 12 Suite" --idle 20
   ```

   An app that is already running is measured as it is and left open.
3. Note in one line:

   | Field | Where |
   |---|---|
   | DAW CPU meter | Live: CPU top right. Logic: View > Show Toolbar, CPU meter. Bitwig: DSP meter, bottom right |
   | Dropouts | crackles heard, or the DAW's overload indicator |
   | Stop size | first N where it crackles; stop going up there |

## What it is compared with

- Infinite renders the same graph headless: `python3 tools/re-survey/load_bench.py run --tracks 8,32,64,128`.
- Infinite runs its audio graph on one thread, so the DAWs' multicore scaling shows up as CPU % above 100.
