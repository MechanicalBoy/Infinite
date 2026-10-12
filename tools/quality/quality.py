#!/usr/bin/env python3
"""quality: one registry, one row format, one scoreboard for every measurement of Infinite.

Node audits, the benchmark suite, re-survey probes and driver checks each print rows like
    QUALITY id=synth.alias_db subject="node:Analog" value=-66.2000
docs/quality/registry.tsv owns what each id means, its target, whether a miss blocks a release,
and the accepted exceptions. This tool reads the rows; it never measures anything itself.

Subjects: Infinite's own nodes are "node:<Name>"; anything else (a competitor plugin or app) is
named as its tool labels it. A metric can be measured on both, which is what makes rows compare.

Usage:
  quality.py check LOG... [--source SYNTHAUDIT]   release gate: misses, unknown ids, missing metrics -> exit 1
  quality.py ingest LOG... [--note TEXT]          append the worst value per (id, subject) to results.jsonl
  quality.py board [--out PATH]                   write docs/quality/SCOREBOARD.md from registry + results
  quality.py --self-test
Exit: 0 ok, 1 gate failed / self-test failed, 2 usage error.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
QDIR = os.path.join(REPO, "docs", "quality")
REGISTRY = os.path.join(QDIR, "registry.tsv")
RESULTS = os.path.join(QDIR, "results.jsonl")
BOARD = os.path.join(QDIR, "SCOREBOARD.md")
COLS = ["id", "pillar", "area", "unit", "better", "target", "gate", "source", "exceptions", "what"]
ROW = re.compile(r'^QUALITY id=(\S+) subject="([^"]*)" value=(\S+)\s*$')
PILLARS = {"P1": "Live AV workstation", "P2": "Global modulation", "P3": "Learns with you", "P4": "Field",
           "P5": "Audio quality and hosting", "P6": "Timeline and arrangement", "P7": "3D, compositing, output",
           "P8": "Performance"}


def load_registry(path=REGISTRY):
    reg = {}
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != len(COLS):
                raise ValueError("%s:%d: %d columns, want %d" % (path, n, len(parts), len(COLS)))
            m = dict(zip(COLS, parts))
            if m["better"] not in ("lower", "higher", "none") or m["gate"] not in ("release", "report"):
                raise ValueError("%s:%d: better must be lower/higher/none, gate release/report" % (path, n))
            m["target"] = float(m["target"]) if m["target"] else None
            m["exceptions"] = dict(e.split("=", 1) for e in m["exceptions"].split(",") if e)
            if m["id"] in reg:
                raise ValueError("%s:%d: duplicate id %s" % (path, n, m["id"]))
            reg[m["id"]] = m
    return reg


def read_rows(paths):
    rows = []
    for p in paths:
        with open(p, errors="replace") as f:
            for line in f:
                m = ROW.match(line.strip())
                if m:
                    rows.append((m.group(1), m.group(2), float(m.group(3))))
    return rows


def worse(m, a, b):
    """The worse of two values for metric m (none: the larger magnitude)."""
    if m is None or m["better"] == "none":
        return a if abs(a) >= abs(b) else b
    return max(a, b) if m["better"] == "lower" else min(a, b)


def aggregate(rows, reg):
    out = {}
    for mid, subj, v in rows:
        k = (mid, subj)
        out[k] = v if k not in out else worse(reg.get(mid), out[k], v)
    return out


def meets(m, v):
    if m["target"] is None or m["better"] == "none":
        return None
    return v <= m["target"] if m["better"] == "lower" else v >= m["target"]


def fmt(v):
    return "%.0f" % v if abs(v) >= 100 else "%.2f" % v if abs(v) >= 1 else "%.3g" % v


def check(paths, reg, source=None, log=print):
    agg = aggregate(read_rows(paths), reg)
    bad, exc = [], 0
    for (mid, subj), v in sorted(agg.items()):
        m = reg.get(mid)
        if m is None:
            bad.append("unknown metric %s (from %s): add it to docs/quality/registry.tsv" % (mid, subj))
            continue
        if m["gate"] != "release" or meets(m, v) is not False:
            continue
        if subj in m["exceptions"]:
            exc += 1
            log("QUALITY CHECK exception %-28s %-22s %s (target %s, %s)" % (mid, subj, fmt(v), fmt(m["target"]), m["exceptions"][subj]))
        else:
            bad.append("%s %s = %s misses target %s %s" % (mid, subj, fmt(v), "<=" if m["better"] == "lower" else ">=", fmt(m["target"])))
    if source:
        seen = {mid for mid, _ in agg}
        for mid, m in sorted(reg.items()):
            if m["source"] == source and m["gate"] == "release" and mid not in seen:
                bad.append("%s measured nothing for %s (the audit stopped emitting it)" % (source, mid))
    for b in bad:
        log("QUALITY CHECK FAIL %s" % b)
    n_ids = len({mid for mid, _ in agg})
    if bad:
        log("QUALITY CHECK FAILED (%d problems, %d metrics, %d rows)" % (len(bad), n_ids, len(agg)))
        return False
    log("QUALITY CHECK PASS (%d metrics, %d rows, %d exceptions)" % (n_ids, len(agg), exc))
    return True


def git_head():
    try:
        return subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def host():
    try:
        r = subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    return sys.platform


def ingest(paths, reg, results=RESULTS, note=""):
    agg = aggregate(read_rows(paths), reg)
    unknown = sorted({mid for mid, _ in agg if mid not in reg})
    if unknown:
        raise ValueError("unknown metric ids, add them to the registry first: %s" % ", ".join(unknown))
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    base = dict(ts=stamp, commit=git_head(), host=host())
    if note:
        base["note"] = note
    with open(results, "a") as f:
        for (mid, subj), v in sorted(agg.items()):
            f.write(json.dumps(dict(base, id=mid, subject=subj, value=round(v, 4))) + "\n")
    return len(agg)


def latest(results=RESULTS):
    out = {}
    if os.path.exists(results):
        with open(results) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    out[(r["id"], r["subject"])] = r  # later lines win
    return out


def board(reg, results=RESULTS):
    lat = latest(results)
    by_id = {}
    for (mid, subj), r in lat.items():
        by_id.setdefault(mid, []).append(r)
    L = ["# Quality scoreboard", "",
         "Generated by `tools/quality/quality.py board` from `registry.tsv` and `results.jsonl`; do not edit by hand. "
         "How the system works: `README.md`.", "",
         "Status: **met** every Infinite subject meets the target · **MISS** a release-gated miss · "
         "**behind** a report-only miss · **exc** met apart from recorded exceptions · **info** no direction · "
         "**unmeasured** no rows yet.", "",
         "| Pillar | Metrics | Met | Behind / miss | Info | Unmeasured |", "|---|---|---|---|---|---|"]
    detail, summary = [], {}
    for pk in sorted({m["pillar"] for m in reg.values()}):
        for area in sorted({m["area"] for m in reg.values() if m["pillar"] == pk}):
            rows = []
            for mid, m in reg.items():
                if m["pillar"] != pk or m["area"] != area:
                    continue
                s = summary.setdefault(pk, [0, 0, 0, 0, 0])
                s[0] += 1
                rs = by_id.get(mid, [])
                ours = [r for r in rs if r["subject"].startswith("node:") or r["subject"].startswith("Infinite")]
                theirs = [r for r in rs if r not in ours]
                if not rs:
                    status = "unmeasured"
                    s[3] += 1
                elif m["better"] == "none" or m["target"] is None:
                    status = "info"
                    s[4] += 1
                else:
                    miss = [r for r in ours if meets(m, r["value"]) is False]
                    real = [r for r in miss if r["subject"] not in m["exceptions"]]
                    status = ("MISS" if m["gate"] == "release" else "behind") if real else "exc" if miss else "met"
                    s[1 if status in ("met", "exc") else 2] += 1
                key = (lambda r: r["value"]) if m["better"] != "higher" else (lambda r: -r["value"])
                w = max(ours, key=key) if ours and m["better"] != "none" else None
                b = min(theirs, key=key) if theirs and m["better"] != "none" else None
                tgt = "" if m["target"] is None else ("<= " if m["better"] == "lower" else ">= ") + fmt(m["target"])
                rows.append("| `%s` | %s | %s | %s | %s | %s | %s |" % (
                    mid, m["what"], tgt + (" " + m["unit"] if tgt else ""), m["gate"], status,
                    "%s (%s)" % (fmt(w["value"]), w["subject"]) if w else "-",
                    "%s (%s)" % (fmt(b["value"]), b["subject"]) if b else "-"))
                if rs and (status in ("MISS", "behind", "exc", "info") or theirs):
                    detail.append((mid, m, sorted(rs, key=lambda r: (not r["subject"].startswith("node:"), key(r)))))
            detail_area = "%s · %s" % (pk, area)
            rows = ["", "## %s %s: %s" % (pk, PILLARS.get(pk, ""), area), "",
                    "| Metric | What | Target | Gate | Status | Infinite worst | Best other |", "|---|---|---|---|---|---|---|"] + rows
            summary.setdefault("_sections", []).append((detail_area, rows))
    for pk in sorted(k for k in summary if k != "_sections"):
        n, ok, bad, un, info = summary[pk]
        L.append("| %s %s | %d | %d | %d | %d | %d |" % (pk, PILLARS.get(pk, ""), n, ok, bad, info, un))
    for _, rows in summary.get("_sections", []):
        L += rows
    if detail:
        L += ["", "## Per subject", "", "Every subject for metrics that miss, carry exceptions, have no direction, or compare against other apps.", ""]
        for mid, m, rs in detail:
            cells = []
            for r in rs:
                tag = ""
                if r["subject"] in m["exceptions"]:
                    tag = " (exc %s)" % m["exceptions"][r["subject"]]
                elif r["subject"].startswith("node:") and meets(m, r["value"]) is False:
                    tag = " (miss)"
                cells.append("%s %s%s" % (r["subject"], fmt(r["value"]), tag))
            L.append("- `%s` (%s): %s" % (mid, m["unit"], " · ".join(cells)))
    stamps = sorted({r["ts"][:10] + " " + r.get("commit", "") for r in lat.values()})
    L += ["", "Rows from (UTC date, commit): %s." % ("; ".join(stamps) if stamps else "none yet"), ""]
    return "\n".join(L)


def self_test():
    fails = []

    def ok(c, msg):
        print(("  ok   " if c else "  FAIL ") + msg)
        if not c:
            fails.append(msg)

    with tempfile.TemporaryDirectory() as d:
        regp = os.path.join(d, "r.tsv")
        with open(regp, "w") as f:
            f.write("# c\n")
            f.write("a.low\tP5\tX\tdB\tlower\t-60\trelease\tAUD\tnode:Bad=F9\tlow is good\n")
            f.write("a.high\tP5\tX\tx\thigher\t1\treport\tAUD\t\thigh is good\n")
            f.write("a.info\tP5\tX\tms\tnone\t\treport\tprobe\t\tno direction\n")
        reg = load_registry(regp)
        logp = os.path.join(d, "l.txt")
        with open(logp, "w") as f:
            f.write('noise\nQUALITY id=a.low subject="node:A" value=-70\nQUALITY id=a.low subject="node:A" value=-65\n')
            f.write('QUALITY id=a.low subject="node:Bad" value=-10\nQUALITY id=a.high subject="node:A" value=0.5\n')
            f.write('QUALITY id=a.info subject="Other" value=3\n')
        agg = aggregate(read_rows([logp]), reg)
        ok(agg[("a.low", "node:A")] == -65, "worst of two lower-is-better rows is the larger")
        ok(check([logp], reg, log=lambda *_: None), "exception and report-only miss do not fail the gate")
        with open(logp, "a") as f:
            f.write('QUALITY id=a.low subject="node:C" value=-1\n')
        ok(not check([logp], reg, log=lambda *_: None), "a release miss without exception fails")
        with open(logp, "w") as f:
            f.write('QUALITY id=a.high subject="node:A" value=2\n')
        ok(not check([logp], reg, source="AUD", log=lambda *_: None), "a release metric missing from its source fails")
        with open(logp, "w") as f:
            f.write('QUALITY id=nope subject="node:A" value=2\n')
        ok(not check([logp], reg, log=lambda *_: None), "an id outside the registry fails")
        try:
            ingest([logp], reg, results=os.path.join(d, "x.jsonl"))
            ok(False, "ingest refuses unknown ids")
        except ValueError:
            ok(True, "ingest refuses unknown ids")
        res = os.path.join(d, "res.jsonl")
        with open(logp, "w") as f:
            f.write('QUALITY id=a.low subject="node:A" value=-70\nQUALITY id=a.low subject="Rival" value=-90\n'
                    'QUALITY id=a.high subject="node:A" value=0.5\n')
        ok(ingest([logp], reg, results=res) == 3, "ingest writes one row per (id, subject)")
        md = board(reg, results=res)
        ok("| `a.low` |" in md and "| met |" in md and "-90.00 (Rival)" in md, "board: met status and best other subject")
        ok("| behind |" in md and "| unmeasured |" in md, "board: report-only miss is behind, no rows is unmeasured")
        with open(regp, "a") as f:
            f.write("bad\tP5\tX\n")
        try:
            load_registry(regp)
            ok(False, "registry rejects a short row")
        except ValueError:
            ok(True, "registry rejects a short row")
    load_registry()  # the real registry must parse
    print("self-test %s (%d failed)" % ("PASS" if not fails else "FAILED", len(fails)))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="release gate over QUALITY rows")
    c.add_argument("logs", nargs="+")
    c.add_argument("--source", help="also fail when a release metric this source owns has no rows")
    i = sub.add_parser("ingest", help="record QUALITY rows in results.jsonl")
    i.add_argument("logs", nargs="+")
    i.add_argument("--note", default="")
    b = sub.add_parser("board", help="write the scoreboard")
    b.add_argument("--out", default=BOARD)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    try:
        reg = load_registry()
        if a.cmd == "check":
            return 0 if check(a.logs, reg, a.source) else 1
        if a.cmd == "ingest":
            print("ingested %d rows into %s" % (ingest(a.logs, reg, note=a.note), os.path.relpath(RESULTS, REPO)))
            return 0
        if a.cmd == "board":
            with open(a.out, "w") as f:
                f.write(board(reg))
            print("wrote %s" % os.path.relpath(a.out, REPO))
            return 0
    except (OSError, ValueError) as e:
        print("quality: %s" % e, file=sys.stderr)
        return 2
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
