#!/usr/bin/env python3
"""re-survey dossiers: scaffold, lint (clean room + outcomes), and the capability-diff report.

  new <ID> "<Name>"     create docs/plans/re-survey/dossiers/<ID>.md from TEMPLATE.md
  lint [dossier.md...]  every section present; comparison rows use a real pillar, status and
                        outcome-with-reason; Infinite paths exist in the repo; no copyleft source
                        links/paths; no long code blocks (findings are behaviour notes, not code);
                        no template placeholders left. Default: every dossier.
  claims [doc.md...]    every `XxxNode` class a doc names must exist in src/ (default: every
                        re-survey mapping/gaps doc and dossier): catches invented Infinite nodes.
  report [--out MD] [--json FILE]
                        aggregate every dossier's comparison table into the capability diff
                        (default docs/plans/re-survey/capability-diff.md, generated) and fail if
                        the dossiers propose more than 5 quests in total.

Usage:
  python3 tools/re-survey/diff.py new C8 "Bitwig Studio"
  python3 tools/re-survey/diff.py lint
  python3 tools/re-survey/diff.py claims docs/plans/re-survey/LOGIC-ALL-MODELS-MAPPING.md
  python3 tools/re-survey/diff.py report --json ~/re-output/capability-diff.json
  python3 tools/re-survey/diff.py --self-test
Exit: 0 clean, 1 lint errors / quest cap exceeded / self-test failed, 2 usage error.
"""

import argparse
import collections
import datetime
import glob
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PILLARS, REPO, SelfTest, copyleft_hits, md_table, write_out  # noqa: E402

DOSSIER_DIR = os.path.join(REPO, "docs", "plans", "re-survey", "dossiers")
TEMPLATE = os.path.join(DOSSIER_DIR, "TEMPLATE.md")
REPORT = os.path.join(REPO, "docs", "plans", "re-survey", "capability-diff.md")
SECTIONS = ["What it is", "Method", "Pillar map", "Comparison", "Measurements", "Outcomes", "Storage"]
STATUSES = ("gap", "lead", "parity")
OUTCOMES = ("quest", "perf-target", "quality-gap", "ignore")
COMPARE_HEAD = ["Pillar", "Their feature", "Infinite equivalent", "Status", "Outcome", "Evidence"]
QUEST_CAP = 5
CODE_FENCE_MAX = 15


def split_row(line):
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [c.strip().replace("\\|", "|") for c in cells]


def comparison_rows(text):
    """Rows of the first table whose header is COMPARE_HEAD, as dicts, with line numbers."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and split_row(line) == COMPARE_HEAD:
            rows = []
            for j in range(i + 2, len(lines)):
                if not lines[j].startswith("|"):
                    break
                cells = split_row(lines[j])
                cells += [""] * (len(COMPARE_HEAD) - len(cells))
                rows.append((j + 1, dict(zip(COMPARE_HEAD, cells))))
            return rows
    return None


_CLASS_CACHE = {}


def src_classes(repo=REPO):
    """Every `class X` / `struct X` name declared under repo/src (cached per repo)."""
    if repo not in _CLASS_CACHE:
        names = set()
        for root, _, files in os.walk(os.path.join(repo, "src")):
            for fn in files:
                if fn.endswith((".h", ".hpp", ".cpp", ".mm")):
                    with open(os.path.join(root, fn), encoding="utf-8", errors="replace") as f:
                        names.update(re.findall(r"\b(?:class|struct)\s+([A-Za-z_]\w*)", f.read()))
        _CLASS_CACHE[repo] = names
    return _CLASS_CACHE[repo]


def unknown_node_classes(text, repo=REPO):
    """[(line, name)] for `...Node` class names in text that src/ never declares."""
    known = src_classes(repo)
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"\b([A-Z][A-Za-z0-9]*Node)\b", line):
            n = m.group(1)
            # "Build/Add a new `XNode`" is a proposal, not a claim that it exists.
            if re.search(r"\b(build|add|new|proposed)\b", line[:m.start()], re.I):
                continue
            if n not in known and n != "INode":
                out.append((i, n))
    return out


def unknown_census_names(text, repo=REPO):
    """[(line, name)] for `Backticked Node Names` on lines that talk about Infinite but are
    neither a census node type nor a src/ class. Paths, code and lower-case tokens are skipped."""
    from common import census_types, load_census, norm_node
    census = load_census() if repo == REPO else load_census(os.path.join(repo, "build", "census", "census.json"))
    if not census:
        return []
    types = census_types(census)
    known = {norm_node(c) for c in src_classes(repo)}
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        at = line.lower().find("infinite")
        if at < 0:
            continue
        # Only the Infinite clause: names after the word "Infinite" (before it they are the competitor's).
        for m in re.finditer(r"`([A-Z][A-Za-z0-9 ]{2,40})`", line):
            n = m.group(1).strip()
            if m.start() < at or n.isupper():
                continue
            if re.search(r"\b(build|add|new|proposed)\b", line[:m.start()], re.I):
                continue
            k = norm_node(n)
            if k in types or k in known or k.endswith("node") and k[:-4] in types:
                continue
            out.append((i, n))
    return out


def lint_text(text, name, repo=REPO):
    errs, warns = [], []
    heads = re.findall(r"^## (?:\d+\.\s*)?(.+)$", text, re.M)
    for s in SECTIONS:
        if not any(h.strip().startswith(s) for h in heads):
            errs.append("missing section '## %s'" % s)
    for pat, hit in copyleft_hits(text):
        errs.append("copyleft source reference (behaviour/docs only): %s" % hit)
    if re.search(r"\{\{[A-Z]+\}\}|^- P2: finding\. Evidence: \.\.\.$|example feature", text, re.M):
        errs.append("template placeholders left")
    for m in re.finditer(r"^```(\w*)\n(.*?)^```", text, re.M | re.S):
        n = m.group(2).count("\n")
        if n > CODE_FENCE_MAX and m.group(1) not in ("bash", "sh", "text", "console"):
            errs.append("code block of %d lines (line %d): findings are behaviour notes, never code"
                        % (n, text[:m.start()].count("\n") + 1))
    rows = comparison_rows(text)
    if rows is None:
        errs.append("no comparison table with header: | %s |" % " | ".join(COMPARE_HEAD))
        rows = []
    elif not rows:
        errs.append("comparison table is empty")
    for ln, r in rows:
        if r["Pillar"] not in PILLARS:
            errs.append("line %d: pillar '%s' is not P1-P8 (drop findings that map to no pillar)" % (ln, r["Pillar"]))
        if r["Status"].lower() not in STATUSES:
            errs.append("line %d: status '%s' not in %s" % (ln, r["Status"], "/".join(STATUSES)))
        kind, _, reason = r["Outcome"].partition(":")
        if kind.strip().lower() not in OUTCOMES or not reason.strip():
            errs.append("line %d: outcome '%s' must be '<%s>: reason'" % (ln, r["Outcome"], "|".join(OUTCOMES)))
        eq = r["Infinite equivalent"]
        if eq.lower() not in ("none", "-"):
            paths = re.findall(r"`([^`]+)`", eq)
            if not paths:
                errs.append("line %d: Infinite equivalent must be `path` or none" % ln)
            for p in paths:
                p = p.split(":")[0]
                full = os.path.join(repo, p)
                if not os.path.exists(full):
                    errs.append("line %d: Infinite path does not exist: %s" % (ln, p))
                elif os.path.isdir(full) and r["Status"].lower() in ("parity", "lead"):
                    # A folder proves nothing: a parity/lead claim names the file that does the thing.
                    errs.append("line %d: %s claim needs a file, not the folder %s" % (ln, r["Status"].lower(), p))
        if not r["Evidence"]:
            warns.append("line %d: no evidence" % ln)
    for ln, n in unknown_node_classes(text, repo):
        errs.append("line %d: %s is not a class in src/ (invented node?)" % (ln, n))
    return errs, warns, rows


def dossier_files(paths=None):
    if paths:
        return paths
    return sorted(p for p in glob.glob(os.path.join(DOSSIER_DIR, "*.md")) if os.path.basename(p) != "TEMPLATE.md")


def cmd_lint(paths):
    files = dossier_files(paths)
    bad = 0
    for p in files:
        errs, warns, rows = lint_text(open(p).read(), os.path.basename(p))
        for e in errs:
            print("ERROR %s: %s" % (os.path.relpath(p, REPO), e))
        for w in warns:
            print("warn  %s: %s" % (os.path.relpath(p, REPO), w))
        bad += bool(errs)
        if not errs:
            print("ok    %s (%d comparison rows)" % (os.path.relpath(p, REPO), len(rows)))
    if not files:
        print("no dossiers yet in %s" % os.path.relpath(DOSSIER_DIR, REPO))
    return 1 if bad else 0


def claim_docs(paths=None):
    if paths:
        return paths
    base = os.path.join(REPO, "docs", "plans")
    docs = glob.glob(os.path.join(base, "re-survey", "*-MAPPING.md")) + glob.glob(os.path.join(base, "re-survey", "*-GAPS-AND-OUTPACE.md"))
    docs += glob.glob(os.path.join(base, "modulation", "*-GAPS-AND-OUTPACE.md"))
    return sorted(docs) + dossier_files()


def cmd_claims(paths):
    bad = 0
    for p in claim_docs(paths):
        text = open(p).read()
        hits = unknown_node_classes(text) + unknown_census_names(text)
        for ln, n in hits:
            print("ERROR %s:%d: %s is not a census node or a class in src/" % (os.path.relpath(p, REPO), ln, n))
        if not hits:
            print("ok    %s" % os.path.relpath(p, REPO))
        bad += bool(hits)
    return 1 if bad else 0


def collect(files):
    items = []
    for p in files:
        text = open(p).read()
        did = os.path.splitext(os.path.basename(p))[0]
        title = (re.findall(r"^# (.+)$", text, re.M) or [did])[0]
        for _, r in comparison_rows(text) or []:
            kind, _, reason = r["Outcome"].partition(":")
            items.append({"dossier": did, "title": title, "pillar": r["Pillar"], "feature": r["Their feature"],
                          "infinite": r["Infinite equivalent"], "status": r["Status"].lower(),
                          "outcome": kind.strip().lower(), "reason": reason.strip(), "evidence": r["Evidence"]})
    return items


def report_md(items):
    L = ["# re-survey capability diff", "",
         "Generated by `python3 tools/re-survey/diff.py report` from every dossier's comparison table. Do not edit by hand.", ""]
    per = collections.defaultdict(collections.Counter)
    for it in items:
        per[it["pillar"]][it["status"]] += 1
    L += ["## By pillar", "", md_table(["Pillar", "Name", "Gaps", "Leads", "Parity"],
          [(p, n, per[p]["gap"], per[p]["lead"], per[p]["parity"]) for p, n in PILLARS.items()]), ""]
    for kind, title in (("quest", "Proposed quests (cap %d)" % QUEST_CAP), ("perf-target", "Perf targets"),
                        ("quality-gap", "Quality gaps"), ("ignore", "Ignored")):
        sel = [it for it in items if it["outcome"] == kind]
        if sel:
            L += ["## %s" % title, "", md_table(["Pillar", "From", "Their feature", "Infinite", "Status", "Why"],
                  [(it["pillar"], it["dossier"], it["feature"], it["infinite"], it["status"], it["reason"]) for it in sel]), ""]
    if not items:
        L.append("No dossiers with comparison rows yet.")
    return "\n".join(L)


def cmd_report(out, js):
    files = dossier_files()
    items = collect(files)
    write_out(report_md(items), out or REPORT)
    if js:
        write_out(json.dumps(items, indent=1), js)
    quests = [it for it in items if it["outcome"] == "quest"]
    print("%d dossiers, %d rows, %d quests proposed" % (len(files), len(items), len(quests)), file=sys.stderr)
    if len(quests) > QUEST_CAP:
        print("ERROR: %d quests proposed, cap is %d: pick, demote the rest to ignore/perf-target" % (len(quests), QUEST_CAP), file=sys.stderr)
        return 1
    return 0


def cmd_new(did, name):
    dest = os.path.join(DOSSIER_DIR, did + ".md")
    if os.path.exists(dest):
        print("exists: %s" % os.path.relpath(dest, REPO), file=sys.stderr)
        return 2
    text = open(TEMPLATE).read().replace("{{ID}}", did).replace("{{NAME}}", name)
    text = text.replace("{{DATE}}", datetime.date.today().isoformat())
    write_out(text, dest)
    print("created %s" % os.path.relpath(dest, REPO))
    return 0


def self_test():
    t = SelfTest("diff")
    tmp = tempfile.mkdtemp(prefix="re-diff-")
    try:
        os.makedirs(os.path.join(tmp, "src"))
        open(os.path.join(tmp, "src", "Mod.cpp"), "w").write("")
        good = "\n".join(["# C9 Thing: dossier", ""] + ["## %d. %s\n\ntext\n" % (i + 1, s) for i, s in enumerate(SECTIONS)])
        good += "\n| " + " | ".join(COMPARE_HEAD) + " |\n|---|---|---|---|---|---|\n"
        good += "| P2 | per-voice mod | `src/Mod.cpp` | gap | quest: users ask for it | docs |\n"
        good += "| P6 | ripple trim | none | gap | ignore: not live-relevant | docs |\n"
        open(os.path.join(tmp, "src", "Lfo.h"), "w").write("class LFONode : public INode {};\n")
        good += "| P2 | lfo | `src/Lfo.h` | parity | ignore: have it (LFONode) | docs |\n"
        errs, _, rows = lint_text(good, "good", repo=tmp)
        t.check(not errs and len(rows) == 3, "good dossier passes (%s)" % errs)
        bad = good.replace("| P2 |", "| P9 |").replace("quest: users ask for it", "quest").replace("`src/Mod.cpp`", "`src/Nope.cpp`")
        bad = bad.replace("## 7. Storage", "## 7. Elsewhere")
        bad += "\nSee https://github.com/VCVRack/Rack/blob/v2/src/engine/Engine.cpp\n"
        bad += "```cpp\n" + "x;\n" * 20 + "```\n"
        bad = bad.replace("`src/Lfo.h` | parity", "`src` | parity").replace("(LFONode)", "(ConvolveReverbNode)")
        t.check(unknown_node_classes("Action: build a new `LatheNode`.", tmp) == [], "proposed node is not a claim")
        if os.path.exists(os.path.join(REPO, "build", "census", "census.json")):
            t.check([n for _, n in unknown_census_names("Infinite's `Color Grade` node", REPO)] == ["Color Grade"], "invented node name flagged")
            t.check(unknown_census_names("Their `Alchemy`; Infinite's `Granular`", REPO) == [], "competitor name and real node pass")
        errs, _, _ = lint_text(bad, "bad", repo=tmp)
        joined = " ".join(errs)
        for needle, what in (("P1-P8", "unknown pillar"), ("must be '<", "outcome without reason"),
                             ("does not exist", "missing Infinite path"), ("Storage", "missing section"),
                             ("copyleft", "VCV Rack source link"), ("code block", "long code block"),
                             ("not the folder", "folder as parity evidence"), ("ConvolveReverbNode", "invented node class")):
            t.check(needle in joined, "bad dossier flags %s" % what)
        items = collect([_write(tmp, "C9.md", good)])
        md = report_md(items)
        t.check(len(items) == 3 and "per-voice mod" in md and "| P2 | Global modulation | 1 |" in md, "report aggregates by pillar")
        t.check(lint_text(open(TEMPLATE).read(), "TEMPLATE")[0] != [], "untouched template fails lint (placeholders)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return t.done()


def _write(d, name, text):
    p = os.path.join(d, name)
    open(p, "w").write(text)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("new")
    n.add_argument("id")
    n.add_argument("name")
    li = sub.add_parser("lint")
    li.add_argument("paths", nargs="*")
    cl = sub.add_parser("claims")
    cl.add_argument("paths", nargs="*")
    rp = sub.add_parser("report")
    rp.add_argument("--out")
    rp.add_argument("--json")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "new":
        return cmd_new(a.id, a.name)
    if a.cmd == "lint":
        return cmd_lint(a.paths)
    if a.cmd == "claims":
        return cmd_claims(a.paths)
    if a.cmd == "report":
        return cmd_report(a.out, a.json)
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
