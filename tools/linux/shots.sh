#!/usr/bin/env bash
#
# Per-category visual shots for the Linux port (phase-01 task 1.8).
#
# Each entry drives one of the app's existing dev fixtures with
# IMAGERESYNTH_SCREENSHOT set, so the binary writes its own PNG from
# glReadPixels - nothing here screen-scrapes the desktop, and nothing here
# copies a PNG that was already committed to the repo. That distinction is the
# whole point: an artifact directory full of the repo's macOS marketing shots
# looks exactly like a passing visual check while proving nothing about Linux.
#
# Run the SAME script on macOS to regenerate tools/linux/reference-shots/, so
# the two sets are produced by identical fixtures at identical frames and can
# be compared side by side.
#
#   tools/linux/shots.sh                      # -> artifacts-linux/shots/
#   OUT_DIR=tools/linux/reference-shots \
#     tools/linux/shots.sh                    # regenerate the macOS references
#
# Assumes a display is already up (xvfb-harness.sh starts one on Linux CI; on
# macOS the session's own display is used).

set -uo pipefail

OUT_DIR="${OUT_DIR:-artifacts-linux/shots}"
if [ -n "${BIN:-}" ]; then
  BIN_PATH="$BIN"
elif [ -x "build-linux/Infinite" ]; then
  BIN_PATH="build-linux/Infinite"
else
  BIN_PATH="build/Infinite.app/Contents/MacOS/Infinite"
fi

if [ ! -x "$BIN_PATH" ]; then
  echo "ERROR: binary not found at $BIN_PATH (set BIN=...)" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

export INFINITE_NO_UPDATE_CHECK=1

# name|fixture env var|screenshot frame
#
# The frame matters: a fixture that prints its own verdict and closes the
# window does so on a fixed frame, so the shot has to land before that or the
# file is never written. 3D/text-3D are the two that self-terminate early.
SHOTS=(
  "2d-text-compositing|INFINITE_SHOWCASE|12"
  "effects-modulators|INFINITE_SHOWCASE2|12"
  "kaleidoscope-macros|INFINITE_SHOWCASE3|12"
  "reaction-diffusion|INFINITE_SHOWCASE4|12"
  "3d-render|INFINITE_3DTEST|12"
  "text-3d|INFINITE_TEXT3DTEST|3"
)

status=0
for entry in "${SHOTS[@]}"; do
  IFS='|' read -r name fixture frame <<< "$entry"
  out="$OUT_DIR/$name.png"
  rm -f "$out"
  echo "==> $name (\$$fixture, frame $frame)"
  env "$fixture=1" \
      IMAGERESYNTH_SCREENSHOT="$out" \
      INFINITE_SCREENSHOT_FRAME="$frame" \
      "$BIN_PATH" > "$OUT_DIR/$name.log" 2>&1 || true

  if [ ! -s "$out" ]; then
    echo "    FAILED - no PNG written (see $OUT_DIR/$name.log)"
    status=1
    continue
  fi

  bytes=$(wc -c < "$out" | tr -d ' ')
  # A window that came up but drew nothing still yields a valid PNG - a flat
  # fill compresses to a few KB, so size is a cheap "did anything render"
  # gate. Real shots of these fixtures are hundreds of KB.
  if [ "$bytes" -lt 20000 ]; then
    echo "    FAILED - PNG is only ${bytes} bytes, almost certainly blank"
    status=1
    continue
  fi
  echo "    ok (${bytes} bytes)"
done

echo
if [ "$status" -eq 0 ]; then
  echo "All ${#SHOTS[@]} shots written to $OUT_DIR"
else
  echo "Some shots failed - see above" >&2
fi
exit "$status"
