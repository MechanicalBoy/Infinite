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

echo "==> Running test driver..."
export INFINITE_BIN="$BIN_PATH"
# Run driver with skip-build
EXIT_CODE=0
./.claude/skills/run-infinite-hygiene/driver.sh --skip-build "$@" || EXIT_CODE=$?

echo "==> Collecting artifacts into ${ARTIFACTS_DIR}..."
find . -maxdepth 2 -name "*.png" -exec cp {} "$ARTIFACTS_DIR/" \; 2>/dev/null || true
if [ -d "$HOME/.config/Infinite" ]; then
  cp -r "$HOME/.config/Infinite"/* "$ARTIFACTS_DIR/" 2>/dev/null || true
fi

exit $EXIT_CODE
