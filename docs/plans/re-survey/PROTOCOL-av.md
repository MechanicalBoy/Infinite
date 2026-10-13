# AV protocol: live audio→picture latency (area 10/AV integration, live variant)

`av_bench.py infinite` measures audio→picture latency **offline**: the rendered movie, where both tracks share one
clock. A live set adds the audio device buffer, the display and the speaker, and only a camera that hears the room
can see those. This sitting needs the owner's phone; about 5 minutes per app.

```
loop.wav ──► app ──► speaker ──────────► phone mic ─┐
              └────► picture ──► screen ─► phone cam ┴─► one .mov, one clock ──► av_bench.py movie
```

## Setup

| Item | Setting |
|---|---|
| Phone | iPhone camera, **Slo-mo 240 fps** (latency resolution ~4 ms), on a stand 30-50 cm from the screen, the screen filling most of the frame |
| Room | quiet; speaker next to the screen (1 ms of sound travel per 34 cm, subtract it) |
| Stimulus | `python3 tools/re-survey/av_bench.py td-prep` writes `~/re-output/av-bench/TD/loop.wav` (8 clicks, 128 BPM) |

## Per app

| App | Patch |
|---|---|
| Infinite | the `reactive` patch from `~/re-output/av-bench/Infinite/reactive.inf`, with `Audio Out` added after `fx` and the Output window full screen (Perform) |
| TouchDesigner | `av_bench_td.py` mode `av` (already plays the loop and flashes); add an Audio Device Out CHOP on `av_click`, Perform window full screen |
| Infinite, clock variant | `clock.inf` + `Audio Out`: the beat clock against the heard click |

1. Start the app's patch, let the loop run.
2. Record 20 s of slo-mo.
3. AirDrop the .mov to `~/re-output/av-bench/live/<app>.mov` and tell Claude "Infinite live" (or the app).
4. Claude runs `python3 tools/re-survey/av_bench.py movie ~/re-output/av-bench/live/<app>.mov`.

## Read-out

| Field | Means |
|---|---|
| latency_ms | heard click to seen flash, as the audience gets it (minus sound travel) |
| jitter_ms | spread across beats; display refresh alone gives up to ~16.7 ms at 60 Hz |
| frame_error | in camera frames (240 fps), not app frames |
| lock_pct | meaningless at 240 fps; read latency and jitter instead |

Positive latency = picture after sound. Under ~45 ms picture-late is the usual "feels in sync" bound for a
click and a flash; a picture that leads the sound is noticed sooner (about 20 ms).
