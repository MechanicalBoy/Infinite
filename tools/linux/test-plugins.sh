#!/usr/bin/env bash
# Downloads pinned open-source Linux VST3 plugins into $HOME/.vst3 for
# INFINITE_VST3SCANTEST / INFINITE_VST3EDITORSHOTTEST (see
# docs/plans/linux/phase-04-vst3.md, task 4.4).
#
# Two tiers, selected by the first argument:
#   --small   (default, every CI run) - DISTRHO's "Parameters" example
#             plugin, built from source straight out of the DPF (DISTRHO
#             Plugin Framework) repo itself. Not a JUCE plugin, so this is
#             fast even from source and deliberately does NOT exercise the
#             JUCE-specific IRunLoop threading requirements phase-04-vst3.md
#             4.3 calls out - that is what --full is for.
#
#             NOTE ON THE SOURCE REPO: phase-04-vst3.md's own text names a
#             plugin at "github.com/DISTRHO/DPF-Examples". That repo does
#             not exist under that name (checked via the GitHub API on
#             2026-09-15: 404). Its apparent successor,
#             github.com/DISTRHO/plugin-examples, exists but is a stale 2018
#             snapshot whose pinned `dpf` submodule commit predates VST3
#             support in DPF entirely (verified in this session: that
#             checkout's Makefile.plugins.mk has no "vst3" target at all) -
#             so it cannot actually produce a .vst3. DPF's own repo
#             (github.com/DISTRHO/DPF) stays in sync with VST3 support by
#             construction and is what this script actually builds against.
#
#             NOTE ON WHICH EXAMPLE: this originally built examples/Info, but
#             that plugin's parameters are all tagged kParameterIsOutput (it
#             exists purely to report host state back, not to be controlled)
#             and its setParameterValue() is a no-op - discovered when
#             INFINITE_VST3SCANTEST's real parameter-set/state-restore
#             assertions genuinely failed against it. examples/Parameters is
#             DPF's own dedicated example with real, automatable,
#             non-output parameters and a real 2-in/2-out audio effect class,
#             and was confirmed in this session to build and round-trip
#             state correctly.
#
#   --full    (phase-tip / manual-dispatch runs only, per 4.4's cost/size
#             guidance) - Surge XT, a real JUCE synth, from
#             surge-synthesizer/releases-xt. ~330MB, cached by the caller
#             (CI wires this through actions/cache keyed on the pinned
#             version below - see .github/workflows/build.yml). This is the
#             meaningful screenshot/threading proof per 4.3's JUCE note.
#
# Usage: tools/linux/test-plugins.sh [--small|--full]
set -euo pipefail

TIER="${1:---small}"
DEST="${HOME}/.vst3"
mkdir -p "$DEST"

sha_check() {
  local file="$1" expected="$2"
  local actual
  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$file" | awk '{print $1}')
  else
    actual=$(shasum -a 256 "$file" | awk '{print $1}')
  fi
  if [ "$actual" != "$expected" ]; then
    echo "ERROR: $file SHA256 mismatch: expected $expected, got $actual" >&2
    exit 1
  fi
  echo "==> $file SHA256 OK ($expected)"
}

install_small_dpf() {
  # Pinned commit of github.com/DISTRHO/DPF, read for real from
  # https://api.github.com/repos/DISTRHO/DPF/commits/main on 2026-09-15.
  # DPF names the built bundle after the example's Makefile's NAME variable,
  # not the source directory name - confirmed by reading the actual pinned
  # Makefile in this session.
  #
  # NOTE ON WHICH EXAMPLE: originally built examples/Info ("d_info"), but
  # real testing against it in this session found every one of its
  # parameters is tagged kParameterIsOutput (see
  # examples/Info/InfoExamplePlugin.cpp - it exists purely to report host
  # transport/buffer state back to the host, not to be controlled), and its
  # setParameterValue() override is a no-op. INFINITE_VST3SCANTEST's
  # parameter set/read-back and save/restore-state assertions need a
  # genuinely settable, persisted parameter to be meaningful, so an
  # all-output-parameters plugin makes those assertions fail for a reason
  # that has nothing to do with our host code. examples/Parameters
  # (DISTRHO_PLUGIN_NUM_INPUTS=2, DISTRHO_PLUGIN_NUM_OUTPUTS=2, real
  # kParameterIsAutomatable params, no kParameterIsOutput) is DPF's own
  # dedicated example for exactly this and was confirmed in this session to
  # build cleanly the same way.
  local PIN_SHA="4238e1c7f0351bbe488d79f0899c540543ac7583"
  local WORK="/tmp/infinite-dpf-build"

  if compgen -G "$DEST"/d_parameters*.vst3 > /dev/null 2>&1; then
    echo "==> d_parameters*.vst3 already installed in $DEST, skipping rebuild"
    return 0
  fi

  rm -rf "$WORK"
  git clone --no-checkout https://github.com/DISTRHO/DPF.git "$WORK"
  git -C "$WORK" checkout "$PIN_SHA"
  # Verify we actually landed on the pinned commit - a moved/rewritten ref
  # must fail loudly here, not silently build something else.
  ACTUAL_SHA=$(git -C "$WORK" rev-parse HEAD)
  if [ "$ACTUAL_SHA" != "$PIN_SHA" ]; then
    echo "ERROR: DPF checkout landed on $ACTUAL_SHA, expected $PIN_SHA" >&2
    exit 1
  fi
  # Only submodule DPF needs for a VST3-only headless-ish build: pugl, for
  # the editor window. No JUCE, no other third-party deps.
  git -C "$WORK" submodule update --init --recursive dgl/src/pugl-upstream

  # Build only the Parameters example's VST3 target, not the whole examples/ tree.
  make -C "$WORK/examples/Parameters" -j"$(nproc)"

  local built
  built=$(find "$WORK/examples/Parameters/../../bin" -maxdepth 1 -iname "*.vst3" | head -1)
  if [ -z "$built" ]; then
    echo "ERROR: DPF build did not produce a .vst3 bundle under $WORK/bin" >&2
    exit 1
  fi
  rm -rf "${DEST:?}/$(basename "$built")"
  cp -r "$built" "$DEST/"
  echo "==> Installed $(basename "$built") into $DEST"
}

install_full_surge() {
  # Pinned to Surge XT 1.3.4 (surge-synthesizer/releases-xt tag "1.3.4").
  # SHA256 below was computed directly against the real downloaded asset in
  # this session (not copied from a webpage) and cross-checked against the
  # release's own md5sum.txt (7f8bfce8a6131ec2c1bcbcfef3ba2038 for this
  # exact file), both of which matched.
  local VERSION="1.3.4"
  local URL="https://github.com/surge-synthesizer/releases-xt/releases/download/${VERSION}/surge-xt-linux-x86_64-${VERSION}.tar.gz"
  local SHA256="fdd578eea384f5ec1b40cd26936b213dc75438a18a787b21227f941d2a680ecd"
  local ARCHIVE="/tmp/surge-xt-linux-x86_64-${VERSION}.tar.gz"

  if [ -d "$DEST/Surge XT.vst3" ]; then
    echo "==> Surge XT.vst3 already installed in $DEST, skipping download"
    return 0
  fi

  if [ ! -f "$ARCHIVE" ]; then
    curl -fSL -o "$ARCHIVE" "$URL"
  fi
  sha_check "$ARCHIVE" "$SHA256"

  local EXTRACT_DIR="/tmp/surge-xt-extract-${VERSION}"
  rm -rf "$EXTRACT_DIR"
  mkdir -p "$EXTRACT_DIR"
  # Real archive layout (confirmed by listing the actual downloaded tarball
  # in this session): "./lib/vst3/Surge XT.vst3/..." and
  # "./lib/vst3/Surge XT Effects.vst3/...". Extract only those two bundles,
  # not the whole ~350MB payload (standalone app, presets, etc.).
  tar xzf "$ARCHIVE" -C "$EXTRACT_DIR" "./lib/vst3/Surge XT.vst3" "./lib/vst3/Surge XT Effects.vst3"

  rm -rf "$DEST/Surge XT.vst3" "$DEST/Surge XT Effects.vst3"
  cp -r "$EXTRACT_DIR/lib/vst3/Surge XT.vst3" "$DEST/"
  cp -r "$EXTRACT_DIR/lib/vst3/Surge XT Effects.vst3" "$DEST/"
  echo "==> Installed Surge XT.vst3 and Surge XT Effects.vst3 into $DEST"
}

case "$TIER" in
  --small) install_small_dpf ;;
  --full)  install_small_dpf; install_full_surge ;;
  *) echo "Usage: $0 [--small|--full]" >&2; exit 1 ;;
esac

echo "==> $DEST now contains:"
ls -1 "$DEST"
