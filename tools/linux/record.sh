#!/usr/bin/env bash
set -euo pipefail

ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts-linux}"
mkdir -p "$ARTIFACTS_DIR"

OUT_MP4="${ARTIFACTS_DIR}/showcase.mp4"
DURATION="${1:-20}"

echo "==> Recording display ${DISPLAY:-:99} for ${DURATION}s to ${OUT_MP4}..."
ffmpeg -y -f x11grab -video_size 1920x1080 -framerate 30 -i "${DISPLAY:-:99}" -t "$DURATION" -c:v libx264 -pix_fmt yuv420p "$OUT_MP4"
