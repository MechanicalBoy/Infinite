#!/usr/bin/env python3
"""re-survey project_bench: how projects behave as they grow, how old files open, and what the formats are.

  infinite  -> generated patches of N nodes (an image chain of Shape -> N-2 cheap effects -> Output, with an LFO
               modulating every tenth node): file size, gzip size, load time (`--validate --lenient`, median of 3)
               and load + write time (`--canonicalize`), per size. Headless, so no window or GL setup is counted.
  history   -> every .inf shipped in each release tag (assets/ in `git show <tag>:...`) opened by today's build:
               how many load, and the issue codes the ones that don't raise.
  formats   -> project and preset files the other apps keep on this machine (.als, .bwproject, .toe, .blend,
               .logicx, ...): size and container (gzip XML, zip, plain XML/text, binary), read from the first
               bytes only. Nothing is decoded past the container, nothing is copied.

Usage:
  python3 tools/re-survey/project_bench.py infinite [--sizes 10,100,1000,4000] [--out results.md]
  python3 tools/re-survey/project_bench.py history  [--out history.md]
  python3 tools/re-survey/project_bench.py formats  [--out formats.md]
  python3 tools/re-survey/project_bench.py --self-test
Big outputs go to ~/re-output/project-bench. Exit: 0 ok, 1 failed, 2 usage error.
"""

import argparse
import gzip
import json
import os
import re
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REPO, RE_OUTPUT, SelfTest, ensure_dir, infinite_bin, md_table, run, write_out  # noqa: E402

CHAIN = [("Compositing", "Null"), ("Compositing", "invert"), ("Compositing", "opacity"), ("Effects", "pixelate"),
         ("Compositing", "posterize"), ("Compositing", "exposure")]
# Where the other apps keep projects, templates and presets on macOS. Searched read-only, first bytes only.
FORMATS = {
    "Ableton Live": ([".als", ".alc", ".adg", ".adv"], ["/Applications/Ableton Live 12 Suite.app", "~/Music/Ableton"]),
    "Bitwig": ([".bwproject", ".bwpreset", ".bwdevice", ".bwmodule"], ["/Applications/Bitwig Studio.app", "~/Documents/Bitwig Studio"]),
    "Logic": ([".logicx", ".patch", ".pst", ".aupreset"], ["/Applications/Logic Pro.app", "/Applications/Logic Pro Creator Studio.app",
                                                         "~/Music/Logic", "~/Music/Audio Music Apps", "/Library/Application Support/Logic"]),
    "TouchDesigner": ([".toe", ".tox"], ["/Applications/TouchDesigner.app", "~/Documents/Derivative"]),
    "Blender": ([".blend"], ["/Applications/Blender.app"]),
    "Infinite": ([".inf"], [os.path.join(REPO, "assets")]),
}


def gen_patch(n):
    """An n-node patch: Shape -> chain -> Output, plus one LFO per ten chain nodes modulating the latest opacity."""
    lfos = max(0, (n - 2) // 11)
    chain = n - 2 - lfos
    lines, last_opacity = ["infinite-patch 1", "node 1 Source Shape", "end"], None
    for k in range(chain):
        idx = 2 + k
        cat, typ = CHAIN[k % len(CHAIN)]
        lines += ["node %d %s %s" % (idx, cat, typ), "end", "cable %d 0 %d" % (idx, idx - 1)]
        if typ == "opacity":
            last_opacity = idx
    out = 2 + chain
    lines += ["node %d Utility Output" % out, "end", "cable %d 0 %d" % (out, out - 1)]
    for j in range(lfos):
        idx = out + 1 + j
        target = 4 + 6 * (j % max(1, (chain - 3) // 6 + 1)) if chain >= 3 else None
        lines += ["node %d Modulators LFO" % idx, "end"]
        if target is not None and target < out:
            lines.append("mod %d uOpacity %d 0 0 0.3 0.7" % (target, idx))
    return "\n".join(lines) + "\n"


def count_nodes(text):
    return sum(1 for ln in text.splitlines() if ln.startswith("node "))


def timed(cmd, reps=3, timeout=600):
    ts, last = [], None
    for _ in range(reps):
        t0 = time.perf_counter()
        last = run(cmd, timeout=timeout)
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts), last


def bench_infinite(sizes, d):
    binp = infinite_bin()
    if not binp:
        raise SystemExit("project_bench: no Infinite build (set INFINITE_BIN)")
    ensure_dir(d)
    rows = []
    for n in sizes:
        p = os.path.join(d, "n%d.inf" % n)
        text = gen_patch(n)
        with open(p, "w") as f:
            f.write(text)
        load_s, (rc, out, err) = timed([binp, "--validate", p, "--lenient"])
        ok = rc == 0
        w = os.path.join(d, "n%d.canonical.inf" % n)
        save_s, (rc2, _, _) = timed([binp, "--canonicalize", p, w])
        canon = os.path.getsize(w) if rc2 == 0 and os.path.exists(w) else 0
        with open(w, "rb") as f:
            gz = len(gzip.compress(f.read())) if canon else 0
        rows.append({"nodes": count_nodes(text), "bytes_min": len(text.encode()), "bytes_full": canon, "gzip_full": gz,
                     "load_s": load_s, "load_write_s": save_s, "load_ok": ok, "write_ok": rc2 == 0})
        print("Infinite %d nodes: load %.3f s, load+write %.3f s, %d bytes written" % (n, load_s, save_s, canon))
    # An empty patch is the start-up floor every load pays; the slope above it is the per-node cost.
    return rows


def report_infinite(rows):
    floor = rows[0]["load_s"] if rows else 0
    return "\n".join(["# Infinite project scaling", "",
                      "Load = `--validate --lenient` (parse, build every node, check), load + write = `--canonicalize`; "
                      "median of 3, headless, process start included (the smallest patch is the floor).", "",
                      md_table(["Nodes", "Minimal file KB", "Full file KB", "Full gzip KB", "Load s", "Load+write s", "ms per node over floor", "OK"],
                               [[r["nodes"], "%.1f" % (r["bytes_min"] / 1024), "%.1f" % (r["bytes_full"] / 1024), "%.1f" % (r["gzip_full"] / 1024),
                                 "%.3f" % r["load_s"], "%.3f" % r["load_write_s"],
                                 "%.2f" % ((r["load_s"] - floor) * 1000 / max(1, r["nodes"] - rows[0]["nodes"])) if r is not rows[0] else "-",
                                 "yes" if r["load_ok"] and r["write_ok"] else "NO"] for r in rows]), ""])


def tags():
    rc, out, _ = run(["git", "-C", REPO, "tag", "--list", "v*", "--sort=creatordate"])
    return [t for t in out.split() if t]


def history():
    binp = infinite_bin()
    if not binp:
        raise SystemExit("project_bench: no Infinite build (set INFINITE_BIN)")
    rows, failures = [], []
    with tempfile.TemporaryDirectory() as td:
        for tag in tags():
            rc, out, _ = run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", tag, "assets"])
            files = [f for f in out.split("\n") if f.endswith(".inf")]
            ok = 0
            for i, f in enumerate(files):
                rc, blob, _ = run(["git", "-C", REPO, "show", "%s:%s" % (tag, f)])
                p = os.path.join(td, "%d.inf" % i)
                with open(p, "w") as fh:
                    fh.write(blob)
                rc, so, _ = run([binp, "--validate", p, "--lenient"], timeout=120)
                if rc == 0:
                    ok += 1
                    continue
                codes = "?"
                try:
                    d = json.loads(so.strip().splitlines()[-1])
                    codes = " ".join(sorted({e["code"] for e in d.get("errors", [])})) or "exit %d" % rc
                except (ValueError, IndexError, KeyError):
                    codes = "exit %d" % rc
                failures.append((tag, f, codes))
            rows.append([tag, len(files), ok, len(files) - ok])
            print("%s: %d/%d load" % (tag, ok, len(files)))
    out = ["# Old Infinite patches opened by today's build", "",
           md_table(["Release", ".inf files shipped", "Load", "Fail"], rows), ""]
    if failures:
        out += ["## Failures", "", md_table(["Release", "File", "Codes"], [list(f) for f in failures]), ""]
    return "\n".join(out)


def classify(head):
    """Container from the first bytes: gzip (and what's inside), zip, XML, JSON, text or binary."""
    if head[:2] == b"\x1f\x8b":
        try:
            inner = gzip.decompress(head) if len(head) < 64 else None
        except OSError:
            inner = None
        return "gzip" if inner is None else "gzip " + classify(inner)
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:4] == b"\x28\xb5\x2f\xfd":
        return "zstd"
    if head[:7] == b"BLENDER":
        return "BLENDER block file"
    s = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if s[:5] == b"<?xml" or s[:1] == b"<":
        return "XML"
    if s[:1] in (b"{", b"["):
        return "JSON"
    if head[:8] == b"bplist00":
        return "binary plist"
    if head and all(32 <= c < 127 or c in (9, 10, 13) for c in head[:256]):
        return "text"
    return "binary"


def gzip_inner(path):
    try:
        with gzip.open(path, "rb") as f:
            return classify(f.read(256))
    except OSError:
        return "?"


def scan_formats(limit=6):
    rows = []
    for app, (exts, roots) in FORMATS.items():
        seen = {}
        for root in roots:
            root = os.path.expanduser(root)
            if not os.path.exists(root):
                continue
            for dp, dns, fns in os.walk(root):
                for name in list(dns) + fns:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in exts and len(seen.setdefault(ext, [])) < limit:
                        seen[ext].append(os.path.join(dp, name))
                if all(len(seen.get(e, [])) >= limit for e in exts):
                    break
        for ext in exts:
            paths = seen.get(ext, [])
            if not paths:
                rows.append([app, ext, 0, "", "", "not found here"])
                continue
            kinds, sizes = set(), []
            for p in paths:
                if os.path.isdir(p):  # a package (.logicx): name what is inside
                    kinds.add("package dir")
                    sizes.append(sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(p) for f in fs))
                    continue
                with open(p, "rb") as f:
                    head = f.read(256)
                k = classify(head)
                kinds.add("gzip " + gzip_inner(p) if k.startswith("gzip") else k)
                sizes.append(os.path.getsize(p))
            rows.append([app, ext, len(paths), "%.1f" % (statistics.median(sizes) / 1024), " / ".join(sorted(kinds)),
                         "open text" if any(x in " ".join(kinds) for x in ("XML", "JSON", "text")) else "closed"])
    return "\n".join(["# Project and preset formats on this machine", "",
                      "Container from the first 256 bytes of up to %d files per extension; median size." % limit, "",
                      md_table(["App", "Extension", "Files read", "Median KB", "Container", "Readable"], rows), ""])


def self_test():
    t = SelfTest("project_bench")
    for n in (10, 100, 1000):
        txt = gen_patch(n)
        t.check(count_nodes(txt) == n, "gen_patch(%d) has %d nodes" % (n, count_nodes(txt)))
    t.check(classify(gzip.compress(b"<?xml version='1.0'?><a/>")) == "gzip XML", "gzip XML recognised")
    t.check(classify(b"PK\x03\x04rest") == "zip", "zip recognised")
    t.check(classify(b"infinite-patch 1\nnode 1 Source Shape\n") == "text", "Infinite patch reads as text")
    t.check(classify(bytes(range(256))) == "binary", "random bytes read as binary")
    binp = infinite_bin()
    if not binp:
        t.skip("no Infinite build: patch load not checked")
        return t.done()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "p.inf")
        with open(p, "w") as f:
            f.write(gen_patch(30))
        rc, so, se = run([binp, "--validate", p, "--lenient"], timeout=120)
        t.check(rc == 0, "a generated 30-node patch loads (exit %d)" % rc)
        rc, _, _ = run([binp, "--canonicalize", p, os.path.join(td, "c.inf")], timeout=120)
        t.check(rc == 0 and count_nodes(open(os.path.join(td, "c.inf")).read()) == 30, "and writes back 30 nodes")
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["infinite", "history", "formats"])
    ap.add_argument("--sizes", default="10,100,1000,4000")
    ap.add_argument("--dir", default=os.path.join(RE_OUTPUT, "project-bench"))
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "infinite":
        d = os.path.expanduser(a.dir)
        rows = bench_infinite([int(x) for x in a.sizes.split(",")], d)
        with open(os.path.join(ensure_dir(d), "infinite.json"), "w") as f:
            json.dump(rows, f, indent=1)
        write_out(report_infinite(rows), a.out)
        return 0 if all(r["load_ok"] and r["write_ok"] for r in rows) else 1
    if a.cmd == "history":
        write_out(history(), a.out)
        return 0
    if a.cmd == "formats":
        write_out(scan_formats(), a.out)
        return 0
    ap.print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
