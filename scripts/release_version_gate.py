#!/usr/bin/env python3
"""Refuse a release whose version is not above every version already published.

Why: an OS that finds several copies of Infinite opens .inf files with the one carrying the highest version number.
v0.4.25 was published once by mistake; 0.4.25 > 0.4.7 numerically, so every user who had it kept double-clicking
into it through v0.4.3..v0.4.7 and saw fixed bugs as still there (v0.2.75/76 vs v0.2.7 did the same earlier).

Usage:
    scripts/release_version_gate.py              # CMakeLists.txt INFINITE_VERSION vs `gh release list`
    scripts/release_version_gate.py 0.5.1 v0.5.0 v0.4.25 ...   # explicit candidate and published tags
    scripts/release_version_gate.py --self-test
Exit: 0 ok, 1 candidate not above every published version, 2 cannot read the inputs.
Git tags that were never released are only warned about: no user downloaded them, but the next bump should
still clear them (v0.46.0..v0.50.0 exist as tags).
"""
import re
import subprocess
import sys

ROOT = __file__.rsplit("/scripts/", 1)[0]


def parse(tag):
    """'v0.4.25' -> (0, 4, 25); suffixes and non-version tags -> None."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", tag.strip())
    if not m:
        return None
    parts = [int(p) for p in m.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()   # 0.5 == 0.5.0
    return tuple(parts)


def blockers(candidate, published):
    c = parse(candidate)
    if c is None:
        raise ValueError("candidate %r is not a version" % candidate)
    return [t for t in published if parse(t) is not None and parse(t) >= c and parse(t) != c]


def cmake_version():
    text = open(ROOT + "/CMakeLists.txt").read()
    m = re.search(r'^set\(INFINITE_VERSION "([0-9.]+)"\)', text, re.M)
    return m.group(1) if m else None


def self_test():
    cases = [
        ("0.4.7", ["v0.4.25", "v0.4.6"], ["v0.4.25"]),       # the escape this gate exists for
        ("0.5.0", ["v0.4.25", "v0.4.7"], []),
        ("0.5.0", ["v0.5.0", "v0.4.7"], []),                  # re-running on its own tag is fine
        ("0.2.7", ["v0.2.75", "v0.2-preview"], ["v0.2.75"]),
        ("0.5.1", ["v0.47.0_fixed", "infinite_turbo_win"], []),
        ("0.5", ["v0.5.0"], []),
    ]
    bad = 0
    for cand, pub, want in cases:
        got = blockers(cand, pub)
        if got != want:
            print("FAIL %s vs %s: got %s want %s" % (cand, pub, got, want))
            bad += 1
    print("RELEASEGATE %s (%d cases)" % ("OK" if bad == 0 else "FAIL", len(cases)))
    return 0 if bad == 0 else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    if argv:
        candidate, published, tags = argv[0], argv[1:], []
    else:
        candidate = cmake_version()
        try:
            published = subprocess.run(["gh", "release", "list", "-L", "500", "--json", "tagName", "-q", ".[].tagName"],
                                       capture_output=True, text=True, check=True, cwd=ROOT).stdout.split()
            tags = subprocess.run(["git", "tag"], capture_output=True, text=True, check=True, cwd=ROOT).stdout.split()
        except (OSError, subprocess.CalledProcessError) as e:
            print("cannot list releases: %s" % e)
            return 2
    if candidate is None:
        print("no INFINITE_VERSION in CMakeLists.txt")
        return 2
    b = blockers(candidate, published)
    for t in blockers(candidate, [t for t in tags if t not in published]):
        print("warning: unreleased git tag %s is above %s" % (t, candidate))
    if b:
        print("BLOCKED: %s is not above published %s. A user with that copy keeps opening patches in it."
              % (candidate, ", ".join(sorted(b, key=parse))))
        return 1
    print("ok: %s is above every published release" % candidate)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
