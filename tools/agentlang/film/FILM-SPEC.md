# Film check: the one call (read this instead of the film skill library for the loop)

Run from any film folder, with that folder's python:

    .venv/bin/python <repo>/tools/agentlang/film/film_check.py SCENE [--times 1,2.5] [--n 8] [--mp4 out.mp4 --bpm 145]

It prints ONE JSON line and never raw logs. Set `INF_ASPECT=9x16` for reels, `INF_THEME=dark` for dark.

| Field | Meaning |
|---|---|
| `ok`, `errors[]` | `E_BUILD` scene failed to import/build, `E_RENDER` a still failed; `hint` is the file line plus the exception |
| `warn[]` | off-beat events, empty first frame, near-empty stills, over 35% of 9:16 ink under UI zones, audit FIX count |
| `stills[]` | per still: `ink` (fraction not background), `safe_ink` (9:16 only, share under UI zones) |
| `sheet` | ONE contact sheet PNG; open it once per check, not every still |
| `audit_fixes`, `audit_top` | only with `--mp4`: findings from film_audit.py |
| `log` | full raw output; read only when `errors` is not enough |

## Loop

1. Edit the scene. 2. `film_check`. 3. If `errors`, fix the named line. 4. If `warn`, fix or accept it knowingly.
5. Open `sheet` once. 6. Repeat. Full-size renders and `assemble.py` only when the owner asks.

## Rules the check cannot see (keep)

One visual and motion language per film. Camera grammar carries moments, no overlay FX, no lens blur, no POV.
Owner's music only. Openings need build-up. Values from code, never invented.
