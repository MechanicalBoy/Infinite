# Workflow protocol: ten common tasks, timed (Block F, area 18)

One sitting, about 15 min per app. It checks the Keystroke-Level Model estimates in
`workflow_cost.py table` against real hands, and confirms the DAW step lists that came from manuals.

```
fresh launch ──► empty project ──► task 1 ... task 10 (each builds on the last) ──► note steps + seconds
```

## Rules

| Rule | Why |
|---|---|
| Practise each task once first, then time the second run | KLM models an expert, not a first try |
| Start the clock on the first input, stop it when the result is heard or on disk | same end point in every app |
| Count every click, key chord, drag and typed word as one step | matches the tool's step count |
| Use the fastest route you know, not the one the table lists | if yours is shorter, the table is wrong: note the route |
| Same plugin (ValhallaSupermassive or any one installed), same sample, same name "song" | removes choice time |

## Per app

| App | Start | Note |
|---|---|---|
| Infinite | new patch, audio off (as launched) | task 1 includes Start Audio |
| Live | new Live Set, one MIDI track selected | |
| Logic | new empty project, new-track dialog open | |
| Bitwig | new project, one instrument track | |

## Read-out

For each app and task, tell Claude "Live 4: 6 steps, 9.5 s, route ..." (route only when it differs).
Claude puts it next to the estimate:

| Column | Means |
|---|---|
| Steps measured vs table | different = the manual route or the code trace was wrong; fix `TASKS` |
| Seconds measured vs KLM | KLM is a ranking tool; more than 2x off on a task means a hidden step (a dialog, a scroll) |
| Rank | does Infinite's place per task hold with real times |

The estimate stays "manual-derived" in the dossier until this sitting confirms it.

## Cheaper route: one screen recording

Instead of timing by stopwatch, record the screen at 60 fps through the whole protocol in one take, then read the
timings offline with `tools/re-survey/video_read.swift` (frame times, 16.7 ms steps). Step counts come from
`workflow_cost.py` and the manual sections it cites.
