# Per-voice modulation (v0.6 2.12)

Status: design, decisions settled (agent, 2026-10-14). Semi-brain brief run first: it pointed at
`ParamMailbox`, `Modulation.h`, the synth cores' `Voice` structs and `new-modulator-node`; no past
attempt at this exists.

## The gap

`IModulator::Value01()` is one number per frame. Every voice of a synth reads the same cutoff, so
"each note gets its own filter sweep" (Bitwig poly modulators, VCV polyphonic cables) is impossible,
and a modulator is sampled at the UI frame rate (ramped per sample by `ParamMailbox`, but stepped in
time to the frame).

## What a user gets

A `per voice` switch on **LFO**, **Random** and **MSEG**. Switched on and cabled straight into a
synth's knob, the modulator runs once per voice, on the audio thread, every sample:

| Modulator | Per voice |
|---|---|
| LFO | each note starts the cycle at the node's `phase`; rate, shape, low/high as set; S&H draws a different sequence per note |
| Random | each note gets its own sequence, stepping at the node's rate, with the node's smoothing |
| MSEG | the note is the trigger: plays in on note-on, loops / sustains while the key is held, plays out on release |
| Envelope (2.14) | the note is the gate: attack/hold/decay on note-on, sustain while held, release on note-off; a retrigger starts the attack from the level reached. ADSR output only (centred needs the shared input) |
| Voice Spread (2.13) | always per voice, no switch: a fixed value from the note's place among the keys held at its note-on |
| Note Expression (2.15) | always per voice, no switch: the note's own MPE pressure or slide from MIDI Notes, smoothed over 5 ms; starts at its note-on value, moves on each expression update |

Everything else is unchanged: the same modulator cabled to any other control, or to a synth knob
with the switch off, behaves exactly as today. With the switch on, the knob on screen keeps showing
the shared value (what one voice started now would roughly see), and a synth playing with no notes
patched (free-running) uses the shared value too.

## Decisions

1. **One switch, off by default.** Turning modulators per voice automatically when they meet a
   synth would change every saved patch whose transport-synced LFO drives a synth. A switch keeps
   old patches identical and costs one checkbox on three nodes. Bitwig's own model is the same idea
   (a modulator is Poly or not).
2. **Only direct bindings go per voice.** A per-voice LFO feeding Math, Smooth or another modulator
   still speaks its shared value there. VCV's "mono consumers take the sum/first channel" maps to
   this: a consumer that is not a voice param reads the shared value. Chains of per-voice
   transforms are a later step if anyone asks; the common uses (per-note filter sweep, per-note
   vibrato, per-note random pan/pitch) are all one cable.
3. **Numeric params only.** A per-voice binding to a dropdown or switch stays shared: switching a
   mode per voice mid-note has no defined meaning in the cores. Integer-stepped knobs (Analog's
   octave and semitone) do go per voice, snapped to their step exactly as the shared path snaps
   them; unison count is not a voice param at all, so it stays shared by decision 4.
4. **Which params.** Each core lists the params its voice loop already evaluates per voice:
   - Analog: osc 1/2 fine, semi, octave, pulse width, FM, osc mix, osc 1/2 level, sub, noise,
     cutoff, resonance, drive, key track, detune, attack, decay, sustain, release.
   - Wavetable: per engine position, level, pan, detune, width, fine, warp amount, warp ratio,
     cutoff, resonance; global mix and FM depth.
   Volume, glide, unison count, stereo spread, pitch bend and the free-running frequency stay
   shared (they act on the whole instrument or on the voice allocator).
5. **First consumers: Analog and Wavetable.** They are the two synths with a full voice loop and the
   ones 2.16 (SIMD voices) rewrites next; the interface is generic, so Sampler / Oscillator join by
   implementing it when there is a reason.
6. **The binding's own shaping still applies.** lo/hi range, curve and smoothing (`smoothMs`) work
   per voice exactly as they do on the shared path (curve = `pow(v, 2^(3c))`, smoothing = one-pole
   with the same time constant, then snap/clamp to the knob's range).
7. **Clock.** Per-voice instances run on the voice's own time from note-on: Hz mode at `rateHz`,
   Beats / Synced at the current tempo (synced periods resolved on the main thread, the same
   division table). They keep running while the transport is paused, as the voices do.
8. **Audio rate.** A per-voice value is computed every sample, so it moves inside a frame; that is
   the audio-rate part of the row. No rate range is widened here.

## Mechanism

```
 main thread, once per frame (CookFrame apply loop)
   binding: modulator --(per voice on, IVoiceModSource::VoiceSpec)--> synth knob
            synth (IVoiceModTarget::VoiceParamFor(&member)) says which voice param it is
   -> VoiceMod::Plan per synth { sources[8]: Spec (POD copy of the modulator's params),
                                 routes[16]: source, param id, lo, hi, curve, smoothMs, min, max, step }
   -> published by value through a lock-free triple buffer (no pointers to nodes cross threads)
 audio thread, the synth's ProcessBlock
   VoiceMod::Runtime: per voice x source state (position, gate, note serial), per voice x route smoother
   NoteOn(voice) restarts that voice's sources; NoteOff(voice) drops their gate
   per sample, per active voice: evaluate the sources the routes use, write the routed values over a
   per-voice copy of the shared params, render the voice from that copy
```

- The shape maths (LFO shapes, Random's hash + smoothing, MSEG segments, loop/sustain stepping)
  moves into pure functions shared by `Value01()` and the voice kernel, so the two cannot drift.
- Real-time rules hold: the plan is fixed-size POD, the runtime allocates nothing, no locks, no
  `dynamic_cast` on the audio thread. An empty plan costs one branch per voice per sample.
- A binding removed, a modulator deleted, or the switch turned off: the next frame publishes a plan
  without that route and the voice falls back to the shared value at once.

## Tests

- `VOICEMODTEST` (headless, in the hygiene and `modulation-sweep` drivers): the kernel's LFO at
  0.37 s matches `LFONode::Value01()` at the same transport position; Random stays in low..high and
  differs per note; MSEG per voice follows its own note-on, loops while held, plays out on release
  without touching other voices; curve, lo/hi, step, clamp and smoothing match CookFrame's shaping;
  an empty plan turns the runtime off; two Analog voices started 0.1 s apart each run their own
  LFO; Analog and Wavetable renders change with a plan and stay finite; the switch saves.
- `VOICEMODFRAMETEST` (windowed): an LFO cabled into Analog's cutoff publishes a one-route plan
  whose source is that LFO only while the switch is on, the shared knob still follows the cable,
  and switching off publishes an empty plan.
- `modulation-sweep` and the hygiene group stay green; `docs/node_param_audit.md` shows the new
  switch as modulatable.
- Smoke patch: `tests/render/lfo-per-voice.inf` (Random Note Generator into Analog, per-voice LFO on
  cutoff), checked with `--audio-summary`: sounds, no clipping, and differs from the switch-off render.
