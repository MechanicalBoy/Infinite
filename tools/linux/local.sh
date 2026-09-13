#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_NAME="infinite-linux-dev"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker / OrbStack is not running." >&2
  echo "Please install OrbStack (brew install --cask orbstack) and open it once." >&2
  exit 1
fi

cmd="${1:-shell}"
shift || true

build_image_if_needed() {
  if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "==> Building local container image ${IMAGE_NAME}..."
    docker build -t "$IMAGE_NAME" -f "$REPO_ROOT/tools/linux/Dockerfile" "$REPO_ROOT"
  fi
}

build_image_if_needed

case "$cmd" in
  build)
    docker run --rm -v "$REPO_ROOT":/src -v infinite-ccache:/root/.ccache -w /src "$IMAGE_NAME" tools/linux/build.sh "$@"
    ;;
  test)
    docker run --rm -v "$REPO_ROOT":/src -v infinite-ccache:/root/.ccache -w /src "$IMAGE_NAME" tools/linux/xvfb-harness.sh "$@"
    ;;
  shell)
    docker run --rm -it -v "$REPO_ROOT":/src -v infinite-ccache:/root/.ccache -w /src "$IMAGE_NAME" bash
    ;;
  *)
    docker run --rm -v "$REPO_ROOT":/src -v infinite-ccache:/root/.ccache -w /src "$IMAGE_NAME" "$cmd" "$@"
    ;;
esac
