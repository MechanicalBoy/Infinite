#!/bin/bash
# In-place update, end to end on a throwaway copy: an "old" copy stages a fake new release, exits, and the helper must
# swap the new one in where the old one was, leaving no staged or backup copy behind. Never touches build/ itself.
#
# Usage: scripts/selfupdate_swap_test.sh [build/Infinite.app]          macOS: copy of the app + a DMG of a re-versioned copy
#        scripts/selfupdate_swap_test.sh build-linux/Infinite          Linux: $APPIMAGE pointed at a scratch file
# Prints SELFUPDATESWAP OK and exits 0 on success.
set -u
S="$(mktemp -d)"
LS=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
fail() { echo "SELFUPDATESWAP FAIL: $*"; exit 1; }
waitfor() { for _ in $(seq 1 100); do eval "$1" && return 0; sleep 0.2; done; return 1; }

if [ "$(uname)" = Darwin ]; then
   SRC="${1:-build/Infinite.app}"
   [ -d "$SRC" ] || fail "no build at $SRC"
   # The helper registers the swapped copy with Launch Services; 0.0.1 can never outrank a real copy as the .inf
   # opener, and the trap unregisters it anyway.
   trap '"$LS" -u "$S/Infinite.app" 2>/dev/null; rm -rf "$S"' EXIT
   ditto "$SRC" "$S/Infinite.app"
   mkdir -p "$S/release" && ditto "$SRC" "$S/release/Infinite.app"
   /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 0.0.1" "$S/release/Infinite.app/Contents/Info.plist"
   : > "$S/release/Infinite.app/Contents/Resources/selfupdate-marker"
   codesign --force --deep -s - "$S/release/Infinite.app" 2>/dev/null || fail "could not re-sign the fake release"
   hdiutil create -quiet -srcfolder "$S/release" -volname Infinite -format UDZO "$S/Infinite.dmg" || fail "hdiutil create"
   out=$(INFINITE_SELFUPDATETEST="$S/Infinite.dmg|0.0.1" "$S/Infinite.app/Contents/MacOS/Infinite" 2>&1)
   echo "$out" | grep -q "SELFUPDATETEST STAGED" || fail "$(echo "$out" | grep SELFUPDATETEST)"
   waitfor '[ -e "$S/Infinite.app/Contents/Resources/selfupdate-marker" ]' || fail "new copy never landed"
   waitfor '[ ! -e "$S/.Infinite-old.app" ] && [ ! -e "$S/.Infinite-update.app" ]' || fail "staged/backup left behind"
   v=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$S/Infinite.app/Contents/Info.plist")
   [ "$v" = 0.0.1 ] || fail "version after swap is $v"
   codesign --verify --deep --strict "$S/Infinite.app" || fail "swapped copy does not verify"
else
   BIN="${1:-build-linux/Infinite}"
   [ -x "$BIN" ] || fail "no binary at $BIN"
   trap 'rm -rf "$S"' EXIT
   printf 'old' > "$S/Infinite-x86_64.AppImage"
   { printf '\177ELF\002\001\001\000AI\002'; printf 'new-release'; } > "$S/new.AppImage"
   # $APPIMAGE is what gets replaced; the binary itself runs in place (its libraries sit next to it).
   out=$(APPIMAGE="$S/Infinite-x86_64.AppImage" INFINITE_SELFUPDATETEST="$S/new.AppImage|0.0.1" "$BIN" 2>&1)
   echo "$out" | grep -q "SELFUPDATETEST STAGED" || fail "$(echo "$out" | grep SELFUPDATETEST)"
   waitfor 'grep -q new-release "$S/Infinite-x86_64.AppImage"' || fail "new copy never landed"
   [ ! -e "$S/.Infinite-update.AppImage" ] || fail "staged copy left behind"
   [ -x "$S/Infinite-x86_64.AppImage" ] || fail "swapped copy is not executable"
fi
echo "SELFUPDATESWAP OK"
