# macOS reference shots

Produced by `tools/linux/shots.sh` on macOS, from the same six fixtures at the
same frames the Linux CI run uses:

```bash
OUT_DIR=tools/linux/reference-shots tools/linux/shots.sh
```

`xvfb-harness.sh` copies this directory into `artifacts-linux/` so one
downloaded CI artifact contains both sets and they can be compared side by
side without checking out the repo.

Downscaled to 800px on the long edge before committing - they are for
eyeballing a platform difference, not for pixel comparison. Regenerate them
whenever a fixture's content changes, and regenerate the *whole* set at once
so both sides stay from the same app version.

Note the shots are captured against a throwaway `HOME`: imgui-node-editor
persists canvas pan/zoom per user, and capturing on a machine that has been
used for real editing otherwise restores that operator's saved view and
silently frames an empty canvas.
