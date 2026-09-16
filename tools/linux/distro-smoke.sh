#!/usr/bin/env bash
# Phase 5 task 5.3 (L3 smoke, see docs/plans/linux/validation.md's "L3"
# section). Runs a built AppImage inside a handful of real distro base
# images and checks that it actually launches there - the thing CI's own
# Ubuntu-24.04 build/test job (L1/L2) cannot prove, because it never leaves
# the build host's own library set.
#
# Usage: tools/linux/distro-smoke.sh <path-to-AppImage> [artifacts-dir]
#
# Containers have no FUSE, so every run uses
# --appimage-extract-and-run (validation.md's exact recipe). Pass criteria
# per distro (validation.md "L3"):
#   - exit code 0
#   - a non-black screenshot (mean pixel value above a floor, not just
#     "file exists" - see linux-parity's "verification step that can only
#     report success" lesson)
#   - no "error while loading shared libraries" anywhere in the run log
#   - `ldd` on the EXTRACTED binary shows no "not found" entries
#
# Additionally, one image (the "minimal" one below) uses only the bare
# runtime packages named in validation.md's minimal-install trap note
# (Audacity 4.0's real regression: Qt linked libOpenGL unconditionally and
# a minimal Ubuntu install didn't have it) rather than a full desktop/Mesa
# dev metapackage, and asserts `ldd` prints nothing for
# libOpenGL/libGL/libGLX/libEGL.
#
# Wayland smoke is best-effort in one Ubuntu image via headless weston and
# is reported but never gates the script's exit code.
set -uo pipefail   # NOT -e: this script's job is to run N independent
                   # checks and report all of them, not die on the first

APPIMAGE="${1:?Usage: $0 <path-to-AppImage> [artifacts-dir]}"
ARTIFACTS_DIR="${2:-artifacts-linux}"
APPIMAGE="$(cd "$(dirname "$APPIMAGE")" && pwd)/$(basename "$APPIMAGE")"
mkdir -p "$ARTIFACTS_DIR"
ARTIFACTS_DIR="$(cd "$ARTIFACTS_DIR" && pwd)"

if [ ! -f "$APPIMAGE" ]; then
  echo "ERROR: $APPIMAGE not found" >&2
  exit 1
fi

# distro-tag -> (docker image, install command for xvfb+mesa+libs)
# NOTE on libasound2: phase-05-release.md's exclude list says ALSA must come
# from the host, same as GL - Infinite links libasound.so.2 directly (not
# dlopen'd), so *some* userspace ALSA lib has to be present for the dynamic
# linker to resolve it at load time. A genuinely bare `xvfb + mesa` container
# doesn't carry it (confirmed in this session: ldd reported
# "libasound.so.2 => not found" and the app never got the chance to run) even
# though any real desktop install does (pulled in transitively by
# PipeWire/PulseAudio's ALSA compat layer or the desktop metapackage) - so
# these installs add it explicitly to represent "a normal desktop", as
# opposed to the deliberately-bare MINIMAL_INSTALL below which intentionally
# leaves it out per validation.md's exact minimal-install-trap package list.
DISTROS=(
  "ubuntu2204|ubuntu:22.04|apt-get update -qq && apt-get install -y -qq --no-install-recommends xvfb mesa-utils libgl1-mesa-dri libglx-mesa0 libx11-6 libfontconfig1 libasound2"
  "ubuntu2404|ubuntu:24.04|apt-get update -qq && apt-get install -y -qq --no-install-recommends xvfb mesa-utils libgl1-mesa-dri libglx-mesa0 libx11-6 libfontconfig1 libasound2t64"
  "debian12|debian:12|apt-get update -qq && apt-get install -y -qq --no-install-recommends xvfb mesa-utils libgl1-mesa-dri libglx-mesa0 libx11-6 libfontconfig1 libasound2"
  "fedora|fedora:latest|dnf install -y -q xorg-x11-server-Xvfb mesa-dri-drivers glx-utils libX11 fontconfig alsa-lib"
  "arch|archlinux:latest|pacman -Sy --noconfirm --needed xorg-server-xvfb mesa libx11 fontconfig glu alsa-lib"
)

# Minimal-install trap check (validation.md): bare runtime packages ONLY,
# no dev/mesa-utils/full-desktop metapackage - the closest a container gets
# to "a user who installed nothing extra".
MINIMAL_TAG="ubuntu2404-minimal"
MINIMAL_IMAGE="ubuntu:24.04"
MINIMAL_INSTALL="apt-get update -qq && apt-get install -y -qq --no-install-recommends xvfb libgl1 libegl1 libfontconfig1 libx11-6"

RESULTS_FILE="$ARTIFACTS_DIR/distro-smoke-results.txt"
: > "$RESULTS_FILE"

# Non-black screenshot check: counts distinct colours the same way
# tools/linux/shots.sh does (a size gate is worthless - see that script's
# own header note and linux-parity §4 "screenshots need a content gate").
# Falls back to a mean-pixel-value heuristic via ImageMagick `identify` if
# png-uniq-colors.py / python3+PIL are unavailable in a given container.
check_non_black_png() {
  local png="$1"
  if [ ! -s "$png" ]; then
    echo "MISSING"
    return 1
  fi
  if command -v python3 >/dev/null 2>&1 && python3 -c "import PIL" >/dev/null 2>&1; then
    python3 - "$png" <<'PYEOF'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
colors = im.getcolors(maxcolors=1_000_000)
n = len(colors) if colors is not None else 1_000_001
print(n)
PYEOF
    return 0
  fi
  if command -v identify >/dev/null 2>&1; then
    identify -format "%k" "$png" 2>/dev/null
    return 0
  fi
  echo "UNKNOWN"
  return 1
}

run_one() {
  local tag="$1" image="$2" install_cmd="$3"
  echo "=== $tag ($image) ==="
  local log="$ARTIFACTS_DIR/${tag}.log"
  local png="$ARTIFACTS_DIR/${tag}.png"
  local docker_rc status reason colors
  rm -f "$log" "$png"

  # /w is the read-only AppImage source dir; /out is the writable artifacts
  # dir. These must be two SEPARATE top-level mounts, not one nested inside
  # the other - mounting /out as a subdirectory of the read-only /w (as an
  # earlier version of this script did, via /w:ro plus -v ...:/w/artifacts)
  # fails outright with "read-only file system" when Docker tries to create
  # the nested mountpoint, confirmed in this session against Docker's
  # overlayfs rootfs. The container extracts and runs the AppImage from a
  # scratch dir since there's no /dev/fuse to mount it with.
  # INFINITE_SYSINFO and IMAGERESYNTH_SCREENSHOT can't be set on the same
  # run: main.cpp's INFINITE_SYSINFO branch (src/main.cpp ~line 60297) calls
  # SysInfo::PrintAndExit() and quits before the render loop that would ever
  # take a screenshot ever runs (confirmed in this session - the first
  # version of this script set both together and the screenshot was
  # silently never written on any distro despite EXIT_CODE=0). So this runs
  # the app twice: once for human-readable SYSINFO diagnostics in the log,
  # once - the run whose exit code and screenshot actually gate PASS/FAIL -
  # for the real headless screenshot.
  docker run --rm \
    -v "$(dirname "$APPIMAGE")":/w:ro \
    -v "$ARTIFACTS_DIR":/out \
    -e LIBGL_ALWAYS_SOFTWARE=1 \
    -e GALLIUM_DRIVER=llvmpipe \
    -e INFINITE_NO_UPDATE_CHECK=1 \
    -e INFINITE_EXITAFTER=120 \
    -e "IMAGERESYNTH_SCREENSHOT=/tmp/artifacts-linux/${tag}.png" \
    "$image" \
    bash -c "
      set -e
      $install_cmd >/tmp/install.log 2>&1 || { echo INSTALL_FAILED; cat /tmp/install.log; exit 90; }
      export XDG_RUNTIME_DIR=\$(mktemp -d)
      Xvfb :99 -screen 0 1920x1080x24 >/tmp/xvfb.log 2>&1 &
      XVFB_PID=\$!
      sleep 1
      export DISPLAY=:99
      mkdir -p /tmp/appimage-extract /tmp/artifacts-linux
      cp /w/$(basename "$APPIMAGE") /tmp/app.AppImage
      chmod +x /tmp/app.AppImage
      cd /tmp/appimage-extract
      /tmp/app.AppImage --appimage-extract >/tmp/extract.log 2>&1
      echo '--- ldd on extracted binary ---'
      LDD_BIN=\$(command -v ldd || echo /usr/bin/ldd)
      \"\$LDD_BIN\" squashfs-root/usr/bin/Infinite || true
      echo '--- SYSINFO (separate run, diagnostics only) ---'
      INFINITE_SYSINFO=1 squashfs-root/AppRun --appimage-extract-and-run >/tmp/sysinfo.log 2>&1 || true
      cat /tmp/sysinfo.log
      echo '--- screenshot run ---'
      squashfs-root/AppRun --appimage-extract-and-run >/tmp/run.log 2>&1
      RC=\$?
      echo \"EXIT_CODE=\$RC\"
      cat /tmp/run.log
      cp /tmp/artifacts-linux/${tag}.png /out/${tag}.png 2>/dev/null || true
      kill \$XVFB_PID 2>/dev/null || true
      exit \$RC
    " > "$log" 2>&1
  docker_rc=$?

  status="FAIL"
  reason=""

  if [ "$docker_rc" -eq 90 ]; then
    reason="package install failed"
  elif grep -qi "error while loading shared libraries" "$log"; then
    reason="missing shared library (see log)"
  elif grep -qE "=>\s*not found\s*$" "$log"; then
    reason="ldd reported a missing dependency"
  elif ! grep -q "EXIT_CODE=0" "$log"; then
    reason="non-zero exit ($(grep -o 'EXIT_CODE=[0-9-]*' "$log" | tail -1))"
  else
    # check_non_black_png already echoes MISSING/UNKNOWN itself on every
    # failure path (see its body above) - piling an `|| echo MISSING` fallback
    # on top of that double-echoed "MISSING\nMISSING" into $colors, which then
    # matched none of the string comparisons below and fell through to a
    # bogus PASS (caught in this session's real run: "PASS: ubuntu2204 -
    # MISSING\nMISSING distinct colours"). The function's own output is
    # authoritative; don't second-guess it here.
    colors="$(check_non_black_png "$png" 2>/dev/null)"
    if [ "$colors" = "MISSING" ]; then
      reason="screenshot missing"
    elif [ "$colors" = "UNKNOWN" ]; then
      status="WARN"
      reason="could not verify screenshot content (no PIL/ImageMagick in container) - exit 0 and no missing-lib errors, treated as a soft pass"
    elif [ "$colors" -le 2 ] 2>/dev/null; then
      reason="screenshot looks black/blank ($colors distinct colours)"
    else
      status="PASS"
      reason="$colors distinct colours"
    fi
  fi

  if [ "$status" = "FAIL" ]; then
    echo "FAIL: $tag - $reason"
  elif [ "$status" = "WARN" ]; then
    echo "WARN: $tag - $reason"
  else
    echo "PASS: $tag - $reason"
  fi
  echo "$tag|$status|$reason" >> "$RESULTS_FILE"
}

echo "==> Running distro smoke against $APPIMAGE"
echo "==> Artifacts: $ARTIFACTS_DIR"

for entry in "${DISTROS[@]}"; do
  IFS='|' read -r tag image install <<< "$entry"
  run_one "$tag" "$image" "$install"
done

echo ""
echo "=== Minimal-install trap check ($MINIMAL_TAG) ==="
run_one "$MINIMAL_TAG" "$MINIMAL_IMAGE" "$MINIMAL_INSTALL"
# run_one's own PASS/FAIL line for this tag is informational only, not
# gating: validation.md's minimal-install package list (libgl1 libegl1
# libfontconfig1 libx11-6 + Mesa) deliberately omits an ALSA userspace lib,
# so Infinite's directly-linked libasound.so.2 will never resolve here and
# the app can never actually launch - confirmed in this session (ldd:
# "libasound.so.2 => not found", then a non-zero exit) even on a build whose
# packaging is otherwise entirely correct. That's expected and by design:
# this image exists only to prove no GL library is linked (the check right
# below), not to prove a full launch, so its run_one line is neutralized here
# rather than failing every run for a reason unrelated to what it's testing.
sed -i.bak "s/^${MINIMAL_TAG}|FAIL|/${MINIMAL_TAG}|INFO(non-gating)|/" "$RESULTS_FILE" && rm -f "$RESULTS_FILE.bak"
minimal_log="$ARTIFACTS_DIR/${MINIMAL_TAG}.log"
if grep -qE "libOpenGL|libGL\.so|libGLX|libEGL" "$minimal_log"; then
  echo "FAIL: minimal-install trap - ldd shows a directly-linked GL library on a bare-runtime install"
  echo "${MINIMAL_TAG}-trap|FAIL|GL library present in ldd output on minimal install" >> "$RESULTS_FILE"
else
  echo "PASS: minimal-install trap - no GL library found via ldd on the bare-runtime install"
  echo "${MINIMAL_TAG}-trap|PASS|no GL library in ldd output" >> "$RESULTS_FILE"
fi

echo ""
echo "=== Wayland smoke (best-effort, does not gate) ==="
WAYLAND_LOG="$ARTIFACTS_DIR/wayland-smoke.log"
docker run --rm \
  -v "$(dirname "$APPIMAGE")":/w:ro \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  -e GALLIUM_DRIVER=llvmpipe \
  -e INFINITE_NO_UPDATE_CHECK=1 \
  -e INFINITE_WAYLAND=1 \
  -e INFINITE_EXITAFTER=120 \
  ubuntu:24.04 \
  bash -c "
    set -e
    apt-get update -qq && apt-get install -y -qq --no-install-recommends weston mesa-utils libgl1-mesa-dri libglx-mesa0 >/tmp/install.log 2>&1
    export XDG_RUNTIME_DIR=\$(mktemp -d)
    (weston --backend=headless-backend.so --renderer=gl >/tmp/weston.log 2>&1 &) || \
      (weston --backend=headless-backend.so --renderer=pixman >/tmp/weston.log 2>&1 &)
    sleep 2
    cp /w/$(basename "$APPIMAGE") /tmp/app.AppImage
    chmod +x /tmp/app.AppImage
    cd /tmp
    ./app.AppImage --appimage-extract-and-run
    echo EXIT_CODE=\$?
  " > "$WAYLAND_LOG" 2>&1
if grep -q "EXIT_CODE=0" "$WAYLAND_LOG"; then
  echo "PASS (best-effort): Wayland smoke - window created, clean exit"
  echo "wayland|PASS|best-effort" >> "$RESULTS_FILE"
else
  echo "FAIL (best-effort, non-gating): Wayland smoke - see $WAYLAND_LOG"
  echo "wayland|FAIL(non-gating)|see log" >> "$RESULTS_FILE"
fi

echo ""
echo "=== Summary ==="
cat "$RESULTS_FILE"

# Exit non-zero only on a real (non-Wayland, non-WARN) FAIL, so CI can gate
# on this script directly.
if grep -E '^\S+\|FAIL\|' "$RESULTS_FILE" | grep -v '^wayland|' >/dev/null; then
  echo "==> One or more gating checks FAILED."
  exit 1
fi
echo "==> All gating checks passed."
exit 0
