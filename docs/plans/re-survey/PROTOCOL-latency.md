# Latency protocol: round trip through BlackHole (Block B, area 7)

One sitting, about 5 min per app. No cables: BlackHole 2ch is the loopback.

```
probe clicks ──► BlackHole out ──► app input ──► app output (-6 dB) ──► BlackHole in ──► probe records
       └───────────── direct copy ────────────────────────────────────────┘
gap between the two copies = the app's real round trip
```

## Setup per app

| App | Device | Monitoring |
|---|---|---|
| Live | Settings > Audio: input and output BlackHole 2ch, 48 kHz | one audio track, input "1/2", Monitor "In", volume -6 dB |
| Logic | Settings > Audio: input and output BlackHole 2ch | one audio track, input 1-2, input monitoring on, fader -6 dB |
| Bitwig | Settings > Audio: BlackHole 2ch both ways | one audio track, input "Stereo In", monitor on, -6 dB |
| Infinite | Settings > Audio: BlackHole 2ch both ways | `Audio In` → `Gain` (-6 dB) → `Audio Out` |

## Each buffer size: 64, 128, 256

1. Set the buffer size in the app. Note the latency the app reports (Live and Logic show it next to the buffer).
2. Tell Claude "Live 128" (app and buffer). Claude runs:

   ```
   python3 tools/re-survey/latency_probe.py run "Live 128"
   ```

   It plays 0.5-amplitude clicks into BlackHole for 12 s and refuses to play anywhere but BlackHole.
3. Keep the app's own output on BlackHole for the whole sitting, so nothing reaches the speakers.

## Read-out

| Column | Means |
|---|---|
| Median ms | what a player hears between playing and hearing, minus converters (none on a loopback) |
| Jitter ms | max − min over the clicks; above 0 means the round trip moves |
| vs reported | measured − reported; positive means the app under-reports |
