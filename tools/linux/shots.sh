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
# Pick by host OS, not by "which file happens to exist". Both binaries are
# usually present in the same worktree - the container writes build-linux/
# into the same mounted tree the macOS build writes build/ into - so probing
# for build-linux/Infinite first silently handed macOS a Linux ELF and every
# shot died with "cannot execute binary file".
MAC_BIN="build/Infinite.app/Contents/MacOS/Infinite"
LINUX_BIN="build-linux/Infinite"
if [ -n "${BIN:-}" ]; then
  BIN_PATH="$BIN"
elif [ "$(uname -s)" = "Darwin" ]; then
  BIN_PATH="$MAC_BIN"
else
  BIN_PATH="$LINUX_BIN"
fi

if [ ! -x "$BIN_PATH" ]; then
  echo "ERROR: binary not found at $BIN_PATH (set BIN=...)" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
# Absolute, because macOS chdir's a bundled app to Contents/Resources before
# main() runs (Cocoa does it for any .app), so a relative IMAGERESYNTH_SCREENSHOT
# resolves against the bundle and the write fails.
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

export INFINITE_NO_UPDATE_CHECK=1

# Run every fixture against a THROWAWAY HOME.
#
# imgui-node-editor persists the canvas pan/zoom, and ImGui persists window
# layout, under the user's home directory. Capturing references on a machine
# that has actually been used for editing therefore restores that operator's
# saved view - which scrolled the showcase graph completely off-screen and
# produced six "successful" reference shots of an empty canvas. CI never saw
# it because a fresh container has no saved state, which is exactly the kind
# of difference that makes a reference set worthless.
SHOT_HOME="$(mktemp -d)"
trap 'rm -rf "$SHOT_HOME"' EXIT
export HOME="$SHOT_HOME"
export XDG_CONFIG_HOME="$SHOT_HOME/.config"
mkdir -p "$XDG_CONFIG_HOME"

# "Did anything actually render" gate.
#
# Counts distinct colours. File size does NOT work here and the earlier version
# of this script was wrong to use it: a blank-canvas shot came out LARGER than
# the correct one (finely-dithered grid compresses worse than flat node
# panels), so blank frames sailed straight through a 20 kB floor.
#
# Measured on this app at native resolution: an empty editor is 183 colours;
# the six fixtures below span 1125 (kaleidoscope - a white circle on a
# checkerboard is genuinely low-colour) to 7071 (3D render). 600 sits clear of
# both. Measure at NATIVE resolution if you retune this - downscaling
# resamples and roughly doubles the count, which is how 1500 got picked first
# and promptly failed two perfectly good shots.
UNIQ_COLORS_MIN=600
uniq_colors() {
   if command -v identify >/dev/null 2>&1; then
      identify -format "%k" "$1" 2>/dev/null
   elif command -v python3 >/dev/null 2>&1; then
      python3 "$(dirname "$0")/png-uniq-colors.py" "$1" 2>/dev/null
   else
      echo "SKIP"
   fi
}

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
  colors=$(uniq_colors "$out")
  if [ "$colors" = "SKIP" ]; then
    echo "    ok (${bytes} bytes; NO blank-check - install ImageMagick or python3)"
  elif [ -z "$colors" ] || ! [ "$colors" -eq "$colors" ] 2>/dev/null; then
    echo "    FAILED - could not read $out as a PNG"
    status=1
  elif [ "$colors" -lt "$UNIQ_COLORS_MIN" ]; then
    echo "    FAILED - only ${colors} distinct colours (<${UNIQ_COLORS_MIN}): rendered blank"
    status=1
  else
    echo "    ok (${bytes} bytes, ${colors} colours)"
  fi
done

echo
if [ "$status" -eq 0 ]; then
  echo "All ${#SHOTS[@]} shots written to $OUT_DIR"
else
  echo "Some shots failed - see above" >&2
fi
exit "$status"
