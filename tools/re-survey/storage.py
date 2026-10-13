#!/usr/bin/env python3
"""re-survey storage: keep ~/re-output small and the repo free of competitor artefacts.

  status        tree of ~/re-output with sizes (paste into a dossier's Storage section)
  compress      gzip every file in ~/re-output over 1 MB that is not already compressed
  clean-tmp     delete ~/re-output/tmp (render WAVs, expansions, sparse clones)
  check-repo    fail if tools/re-survey or docs/plans/re-survey hold a file over 1 MB or a
                competitor artefact type (.app .vst3 .component .dylib .asar .toe .tox .blend
                .als .amxd .fcpxml .wav .gz ...). Fixtures are generated in self-tests, never committed.

Usage:
  python3 tools/re-survey/storage.py status|compress|clean-tmp|check-repo
  python3 tools/re-survey/storage.py --self-test
Exit: 0 ok, 1 check-repo found something / self-test failed, 2 usage error.
"""

import argparse
import gzip
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, RE_TMP, REPO, SelfTest, human_bytes  # noqa: E402

COMPRESSED = (".gz", ".xz", ".zip", ".bz2", ".zst", ".7z", ".png", ".jpg", ".mp4", ".mov", ".dmg")
BANNED_EXT = (".app", ".vst3", ".component", ".clap", ".dylib", ".so", ".dll", ".asar", ".toe", ".tox", ".blend",
              ".als", ".amxd", ".fcpxml", ".fcpxmld", ".wav", ".aif", ".aiff", ".gz", ".zip", ".dmg", ".pkg", ".jar")
WATCHED = [os.path.join("tools", "re-survey"), os.path.join("docs", "plans", "re-survey")]
MAX_BYTES = 1024 * 1024


def du(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dp, _, fn in os.walk(path):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def status(root=RE_OUTPUT):
    if not os.path.isdir(root):
        return "%s does not exist (nothing stored)" % root
    lines = ["%s  %s" % (human_bytes(du(root)).rjust(9), root)]
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        lines.append("%s  %s%s" % (human_bytes(du(p)).rjust(9), name, "/" if os.path.isdir(p) else ""))
    return "\n".join(lines)


def compress(root=RE_OUTPUT):
    done = []
    for dp, _, fn in os.walk(root):
        if os.path.abspath(dp).startswith(os.path.abspath(RE_TMP)):
            continue
        for f in fn:
            p = os.path.join(dp, f)
            if f.lower().endswith(COMPRESSED) or os.path.getsize(p) <= MAX_BYTES:
                continue
            with open(p, "rb") as src, gzip.open(p + ".gz", "wb", 6) as dst:
                shutil.copyfileobj(src, dst)
            done.append((p, os.path.getsize(p), os.path.getsize(p + ".gz")))
            os.remove(p)
    return done


def check_repo(repo=REPO):
    problems = []
    for rel in WATCHED:
        base = os.path.join(repo, rel)
        for dp, dn, fn in os.walk(base):
            for d in list(dn):
                if d.lower().endswith(BANNED_EXT):
                    problems.append("%s/ (bundle type not allowed)" % os.path.relpath(os.path.join(dp, d), repo))
                if d == "__pycache__":
                    dn.remove(d)
            for f in fn:
                p = os.path.join(dp, f)
                if f.lower().endswith(BANNED_EXT):
                    problems.append("%s (artefact type not allowed)" % os.path.relpath(p, repo))
                elif os.path.getsize(p) > MAX_BYTES:
                    problems.append("%s (%s, over 1 MB)" % (os.path.relpath(p, repo), human_bytes(os.path.getsize(p))))
    return problems


def self_test():
    t = SelfTest("storage")
    tmp = tempfile.mkdtemp(prefix="re-storage-")
    try:
        os.makedirs(os.path.join(tmp, "tools", "re-survey"))
        os.makedirs(os.path.join(tmp, "docs", "plans", "re-survey", "x.vst3"))
        open(os.path.join(tmp, "tools", "re-survey", "ok.py"), "w").write("x")
        open(os.path.join(tmp, "tools", "re-survey", "dump.als"), "w").write("x")
        with open(os.path.join(tmp, "docs", "plans", "re-survey", "big.md"), "wb") as f:
            f.write(b"a" * (MAX_BYTES + 1))
        pr = check_repo(tmp)
        t.check(any("dump.als" in p for p in pr), "flags a committed .als")
        t.check(any("x.vst3/" in p for p in pr), "flags a plugin bundle dir")
        t.check(any("big.md" in p for p in pr), "flags a file over 1 MB")
        t.check(not any("ok.py" in p for p in pr), "leaves small source alone")
        out = os.path.join(tmp, "out")
        os.makedirs(out)
        with open(os.path.join(out, "dump.json"), "wb") as f:
            f.write(b"{}" * MAX_BYTES)
        done = compress(out)
        t.check(len(done) == 1 and os.path.exists(os.path.join(out, "dump.json.gz"))
                and not os.path.exists(os.path.join(out, "dump.json")), "compress gzips big files and removes originals")
        t.check("dump.json.gz" in status(out), "status lists entries")
        t.check(check_repo(REPO) == [], "this repo's re-survey dirs are clean")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", choices=["status", "compress", "clean-tmp", "check-repo"])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "status":
        print(status())
    elif a.cmd == "compress":
        for p, before, after in compress():
            print("%s: %s -> %s" % (p, human_bytes(before), human_bytes(after)))
    elif a.cmd == "clean-tmp":
        n = du(RE_TMP) if os.path.isdir(RE_TMP) else 0
        shutil.rmtree(RE_TMP, ignore_errors=True)
        print("removed %s (%s)" % (RE_TMP, human_bytes(n)))
    elif a.cmd == "check-repo":
        pr = check_repo()
        for p in pr:
            print("ERROR %s" % p)
        print("repo clean" if not pr else "%d problem(s)" % len(pr))
        return 1 if pr else 0
    else:
        ap.print_usage(sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
