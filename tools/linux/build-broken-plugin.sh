#!/usr/bin/env bash
# Builds a deliberately broken .vst3 bundle whose ModuleEntry calls abort(),
# for INFINITE_VST3BLOCKLISTTEST (docs/plans/linux/phase-04-vst3.md, task
# 4.4's "Scanner crash path"). This proves the out-of-process
# scan/crash-sentinel/blocklist mechanism (ported in this branch's 4.2
# commit, see Platform::VST3Blocklist / VST3BlocklistPath) survives a
# plugin whose module entry point crashes the scan child outright, rather
# than merely failing to load cleanly.
#
# ModuleEntry (not GetPluginFactory) is where the abort() goes: confirmed
# against src/platform/linux/PluginVST3Linux.cpp's real load sequence
# (~line 2557 onward) - dlopen() succeeds first, then ModuleEntry is
# resolved and called, and only a true return from it leads to
# GetPluginFactory. Aborting inside ModuleEntry means the crash happens as
# early as a real broken plugin's module init could realistically abort,
# before any factory/class enumeration is attempted.
#
# Usage: tools/linux/build-broken-plugin.sh <output-dir>
#   Produces <output-dir>/Broken.vst3/Contents/<arch>-linux/Broken.so
set -euo pipefail

OUT_DIR="${1:?Usage: $0 <output-dir>}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) BUNDLE_ARCH="x86_64-linux" ;;
  aarch64|arm64) BUNDLE_ARCH="aarch64-linux" ;;
  *) echo "ERROR: unsupported arch '$ARCH' for a VST3 Linux bundle" >&2; exit 1 ;;
esac

BUNDLE="$OUT_DIR/Broken.vst3"
CONTENTS="$BUNDLE/Contents/$BUNDLE_ARCH"
mkdir -p "$CONTENTS"

SRC="$(mktemp -d)/broken.c"
mkdir -p "$(dirname "$SRC")"
cat > "$SRC" <<'EOF'
// Deliberately broken VST3 module: aborts as soon as the host calls
// ModuleEntry, before ever returning a plugin factory. See
// tools/linux/build-broken-plugin.sh for why this is the entry point that
// aborts, not GetPluginFactory.
#include <stdlib.h>

int ModuleEntry(void* ctx)
{
   (void)ctx;
   abort();
   return 1;
}

int ModuleExit(void)
{
   return 1;
}

void* GetPluginFactory(void)
{
   return 0;
}
EOF

gcc -shared -fPIC -o "$CONTENTS/Broken.so" "$SRC"
rm -rf "$(dirname "$SRC")"

echo "==> Built $CONTENTS/Broken.so (aborts in ModuleEntry)"
echo "==> Bundle: $BUNDLE"
