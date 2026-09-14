#!/usr/bin/env bash
set -euo pipefail

ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts-linux}"
mkdir -p "$ARTIFACTS_DIR"

export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export INFINITE_NO_UPDATE_CHECK=1
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$(mktemp -d)}"
export DISPLAY=":99"

echo "==> Starting Xvfb on display ${DISPLAY}..."
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!

cleanup() {
  if [ -n "${XVFB_PID:-}" ] && kill -0 "$XVFB_PID" 2>/dev/null; then
    kill "$XVFB_PID" 2>/dev/null || true
    wait "$XVFB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Wait a moment for Xvfb to be ready
sleep 1

echo "==> Virtual display OpenGL info:"
glxinfo -B || true

BIN_PATH="${BIN:-build-linux/Infinite}"
if [ ! -x "$BIN_PATH" ]; then
  echo "ERROR: Binary $BIN_PATH not found or not executable" >&2
  exit 1
fi

echo "==> Running INFINITE_SYSINFO..."
INFINITE_SYSINFO=1 "$BIN_PATH" || true

echo "==> MIDI hardware check: $( [ -e /dev/snd/seq ] && echo 'present' || echo 'absent' )"
if [ ! -e /dev/snd/seq ]; then
  # docs/plans/linux/phase-02-audio-midi.md 2.5: neither GitHub Actions
  # runners nor OrbStack/local containers ship the snd-seq kernel module, so
  # a real end-to-end ALSA sequencer device is unreachable here on any
  # platform this harness runs on - documented, not a bug. MidiStart()
  # already handles this by treating "no sequencer available" as
  # non-fatal, and INFINITE_MIDIPARSETEST (below, via driver.sh's
  # MIDIPARSETEST check) is the primary MIDI proof: it feeds synthetic
  # snd_seq_event_t's straight into the parser, with no real handle needed.
  echo "    SKIP real ALSA sequencer device test: no /dev/snd/seq in this container (L4, see phase-02-audio-midi.md)."
fi

echo "==> Running test driver..."
export INFINITE_BIN="$BIN_PATH"
# Run driver with skip-build
EXIT_CODE=0

# Task 2.5: the audio group must be proven on two different miniaudio
# backends - the null backend (always available, no real device) and
# PulseAudio backed by a null sink (exercises the real negotiation path
# without depending on host audio hardware). Only the audio group itself
# needs the double run; other groups/tiers are backend-agnostic.
RUN_AUDIO_TWICE=0
for arg in "$@"; do
  case "$arg" in
    *audio*) RUN_AUDIO_TWICE=1 ;;
  esac
done

if [ "$RUN_AUDIO_TWICE" = "1" ]; then
  echo "==> Audio group pass 1/2: INFINITE_AUDIO_BACKEND=null"
  INFINITE_AUDIO_BACKEND=null ./.claude/skills/run-infinite-hygiene/driver.sh --skip-build "$@" || EXIT_CODE=$?

  PULSE_READY=0
  if command -v pulseaudio >/dev/null 2>&1 && command -v pactl >/dev/null 2>&1; then
    echo "==> Starting a throwaway PulseAudio daemon with a null sink for pass 2/2..."
    pulseaudio --start --exit-idle-time=-1 --disallow-exit -D >/tmp/infinite_pulse.log 2>&1 || true
    if pactl info >/dev/null 2>&1; then
      pactl load-module module-null-sink sink_name=infinite_null_sink >/dev/null 2>&1 || true
      pactl set-default-sink infinite_null_sink >/dev/null 2>&1 || true
      PULSE_READY=1
    fi
  fi

  if [ "$PULSE_READY" = "1" ]; then
    echo "==> Audio group pass 2/2: INFINITE_AUDIO_BACKEND=pulse (null sink)"
    PASS2_EXIT=0
    INFINITE_AUDIO_BACKEND=pulse ./.claude/skills/run-infinite-hygiene/driver.sh --skip-build "$@" || PASS2_EXIT=$?
    if [ "$PASS2_EXIT" -ne 0 ]; then
      EXIT_CODE=$PASS2_EXIT
    fi
    pulseaudio --kill >/dev/null 2>&1 || true
  else
    echo "==> PulseAudio (or pactl) not available in this container - pass 2/2 skipped, null-backend pass above is the audio-group proof for this run."
  fi
else
  ./.claude/skills/run-infinite-hygiene/driver.sh --skip-build "$@" || EXIT_CODE=$?
fi

echo "==> Per-category shots..."
# Soft-fail: a missing shot is reported in the artifact but must not mask the
# driver's own verdict, which is what EXIT_CODE carries.
BIN="$BIN_PATH" OUT_DIR="$ARTIFACTS_DIR/shots" ./tools/linux/shots.sh || true
if [ -d tools/linux/reference-shots ]; then
  # Shipped alongside so the owner can compare Linux vs macOS side by side in
  # the one downloaded artifact, without checking out the repo.
  cp -r tools/linux/reference-shots "$ARTIFACTS_DIR/" 2>/dev/null || true
fi

echo "==> Collecting artifacts into ${ARTIFACTS_DIR}..."
# ONLY files this run produced. The previous version of this step was
#   find . -maxdepth 2 -name "*.png" -exec cp {} "$ARTIFACTS_DIR/" \;
# which swept up PNGs COMMITTED to the repo - docs/screenshot.png,
# website/full_page_capture.png, assets/Infinite*.png - all of them captured on
# macOS. The artifact then looked like proof that Linux rendered correctly
# while containing no Linux pixels at all. Never widen this back to a bare
# find over the worktree.
if [ -f /tmp/infinite_hygiene_shot.png ]; then
  cp /tmp/infinite_hygiene_shot.png "$ARTIFACTS_DIR/hygiene-visual-smoke.png"
fi
for log in /tmp/infinite_shot.log /tmp/infinite_build.log; do
  [ -f "$log" ] && cp "$log" "$ARTIFACTS_DIR/" 2>/dev/null || true
done
# Per-test output. driver.sh writes /tmp/infinite_test_<NAME>.log for every
# check and, on failure, prints only "see <that path>" - which is useless from
# a CI log, because the path is on a runner that no longer exists. A test that
# passes locally on arm64 and fails here on x86_64 is exactly the case this
# harness exists to catch, and without these files there is nothing to read.
mkdir -p "$ARTIFACTS_DIR/test-logs"
cp /tmp/infinite_test_*.log "$ARTIFACTS_DIR/test-logs/" 2>/dev/null || true
if [ -d "${XDG_CONFIG_HOME:-$HOME/.config}/Infinite" ]; then
  cp -r "${XDG_CONFIG_HOME:-$HOME/.config}/Infinite" "$ARTIFACTS_DIR/app-support" 2>/dev/null || true
fi

echo "==> Artifact contents:"
ls -R "$ARTIFACTS_DIR" || true

exit $EXIT_CODE
