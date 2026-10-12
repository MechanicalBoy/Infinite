"""Shared helpers for tools/re-survey.

Every re-survey tool imports this: where big outputs go (~/re-output, never the
repo), how to find the Infinite binary, how to print a markdown table, and the
clean-room denylist (GPL/AGPL projects whose source we never read).

Not a CLI. See tools/re-survey/README.md for the tools themselves.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# Big outputs live outside the repo, compressed, never committed (re-survey rule 3).
RE_OUTPUT = os.path.expanduser(os.environ.get("RE_OUTPUT", "~/re-output"))
RE_TMP = os.path.join(RE_OUTPUT, "tmp")

PILLARS = {
    "P1": "Live AV workstation",
    "P2": "Global modulation",
    "P3": "Learns with you",
    "P4": "Field",
    "P5": "Audio quality and hosting",
    "P6": "Timeline and arrangement",
    "P7": "3D, compositing, output",
    "P8": "Performance",
}

# Projects whose SOURCE is off limits (AGENTS.md rule 1). Behaviour, docs and
# public discussions only. Lower-case substrings matched against URLs/paths.
COPYLEFT_SOURCE_PATTERNS = [
    r"github\.com/bespokesynth/",
    r"github\.com/vcvrack/",
    r"github\.com/mtytel/vital",
    r"github\.com/obsproject/",
    r"(github\.com|code)\.videolan\.org|github\.com/videolan/",
    r"github\.com/supercollider/",
    r"github\.com/kronoslang/|github\.com/vmilea/kronos",
    r"github\.com/cmajor-lang/|github\.com/soul-lang/",
    r"github\.com/blender/blender|projects\.blender\.org/blender/blender/src",
    r"github\.com/hydra-synth/",
    r"github\.com/tidalcycles/strudel|codeberg\.org/uzu/strudel",
    r"github\.com/grame-cncm/faust/(blob|tree)/[^ ]*/compiler",
]
# Paths that point inside a copyleft app's own code (bundled scripts count).
COPYLEFT_LOCAL_PATTERNS = [
    r"blender\.app/contents/resources/[^ ]*/scripts/",
    r"bespokesynth[^ ]*/source/",
    r"vcv rack[^ ]*\.app/",
]


def copyleft_hits(text):
    """Return [(pattern, matched text)] for every copyleft-source reference in text."""
    hits = []
    low = text.lower()
    for pat in COPYLEFT_SOURCE_PATTERNS + COPYLEFT_LOCAL_PATTERNS:
        for m in re.finditer(pat, low):
            hits.append((pat, text[m.start():m.end() + 40].split("\n")[0]))
    return hits


def run(cmd, timeout=120, cwd=None, input_bytes=None):
    """Run a command, never raise. Returns (rc, stdout str, stderr str)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, input=input_bytes, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except FileNotFoundError:
        return 127, "", "not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after %ss: %s" % (timeout, " ".join(cmd))


def infinite_bin():
    """The Infinite executable: $INFINITE_BIN, this checkout's build, or the main checkout's build.

    A worktree usually has no build of its own, so fall back to the common git dir's checkout.
    """
    env = os.environ.get("INFINITE_BIN")
    if env:
        return env if os.access(env, os.X_OK) else None
    rel = "build/Infinite.app/Contents/MacOS/Infinite" if sys.platform == "darwin" else "build/Infinite"
    roots = [REPO]
    rc, out, _ = run(["git", "-C", REPO, "rev-parse", "--git-common-dir"], timeout=10)
    if rc == 0:
        common = os.path.abspath(os.path.join(REPO, out.strip()))
        roots.append(os.path.dirname(common))
    for r in roots:
        p = os.path.join(r, rel)
        if os.access(p, os.X_OK):
            return p
    return None


def md_table(headers, rows):
    def cell(v):
        s = "" if v is None else str(v)
        return s.replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(cell(v) for v in r) + " |")
    return "\n".join(out)


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f GB" % n


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p


def write_out(text, path):
    """Write text to path ('-' or None = stdout)."""
    if not path or path == "-":
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w") as f:
        f.write(text if text.endswith("\n") else text + "\n")


class SelfTest:
    """Tiny assertion collector: every tool's --self-test prints PASS/FAIL lines and exits 0/1."""

    def __init__(self, name):
        self.name = name
        self.fails = 0
        self.skips = 0

    def check(self, cond, what):
        print("%s  %s: %s" % ("PASS" if cond else "FAIL", self.name, what))
        if not cond:
            self.fails += 1
        return cond

    def skip(self, what):
        print("SKIP  %s: %s" % (self.name, what))
        self.skips += 1

    def done(self):
        print("%s: %s (%d skipped)" % (self.name, "FAILED %d" % self.fails if self.fails else "ok", self.skips))
        return 1 if self.fails else 0
