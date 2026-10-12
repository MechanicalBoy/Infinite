#!/usr/bin/env python3
"""Regenerate the facts block of docs/NOW.md (the one page every session reads first).

Only the text between the FACTS markers is rewritten. Everything else in NOW.md (release goal,
claims, waiting on owner, decisions) is hand-kept and left alone. Facts come from git, the quest ledger
(tools/roadmap), metrics.jsonl and `gh release` when gh is available.

    python3 tools/lifecycle/now.py           # rewrite the block
    python3 tools/lifecycle/now.py --print   # print the block only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOW = ROOT / "docs" / "NOW.md"
BEGIN, END = "<!-- FACTS:BEGIN (tools/lifecycle/now.py) -->", "<!-- FACTS:END -->"
QUEST_CAP = 5

sys.path.insert(0, str(ROOT / "tools" / "roadmap"))


def sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def open_quests() -> list[dict]:
    try:
        import roadmap  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - the board is optional input, never a hard failure
        return []
    return [q for q in roadmap.board() if q.get("status") == "open"]


def last_metric(kind: str) -> dict:
    path = ROOT / "tools" / "roadmap" / "metrics.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    rows = [r for r in rows if r.get("kind") == kind]
    return rows[-1] if rows else {}


def releases(n: int = 4) -> list[tuple[str, str, int]]:
    out = sh("gh", "release", "list", "--limit", str(n), "--json", "tagName,publishedAt")
    if not out:
        return []
    rows = []
    for r in json.loads(out):
        assets = sh("gh", "release", "view", r["tagName"], "--json", "assets", "--jq", "[.assets[].downloadCount]|add")
        rows.append((r["tagName"], r["publishedAt"][:10], int(assets or 0)))
    return rows


FIX = r"^(fix|bugfix)|: fix|\bfix(es|ed)?\b|regression|crash"


def quality(tag: str, prev: str) -> list[str]:
    """How right the last release was, from git alone. Escaped = a fix after the tag that touches a src file
    the release window changed: the bug shipped. Reverts after the tag count the same way."""
    window = set(sh("git", "diff", "--name-only", f"{prev}..{tag}", "--", "src").splitlines())
    fixes = sh("git", "log", "main", "--no-merges", "-i", "-E", f"--grep={FIX}", "--format=%h", f"{tag}..main").split()
    escaped = [h for h in fixes if window & set(sh("git", "show", "--name-only", "--format=", h).splitlines())]
    reverts = sh("git", "log", "main", "--no-merges", "--format=%h", "--grep=^Revert", f"{tag}..main").split()
    known = {}
    for name in ("known-test-failures.txt", "known-test-failures-linux.txt"):
        p = ROOT / ".claude" / "skills" / "run-infinite-hygiene" / name
        if p.exists():
            known[name] = sum(1 for line in p.read_text().splitlines() if line.strip() and not line.startswith("#"))
    bugs = sh("gh", "issue", "list", "--state", "open", "--label", "bug", "--limit", "200", "--json", "number", "--jq", "length")
    tag_date = sh("git", "log", "-1", "--format=%cs", tag)
    crashes = [p for p in (ROOT / "docs" / "crash-reports").glob("*.ips")
               if tag_date and p.name.split("-", 1)[-1][:10] >= tag_date] if (ROOT / "docs" / "crash-reports").exists() else []
    return [
        f"### Quality of {tag} (since {prev}; the release measure)",
        "",
        "| Measure | Value | Want |",
        "|---|---|---|",
        f"| Escaped fixes: fixes after {tag} touching src it changed | {len(escaped)} {' '.join(escaped[:8])} | 0, falling release to release |",
        f"| Reverts after {tag} | {len(reverts)} | 0 |",
        f"| Fix-shaped commits after {tag} (all) | {len(fixes)} | context |",
        f"| Known test failures (macOS / Linux) | {known.get('known-test-failures.txt', '?')} / {known.get('known-test-failures-linux.txt', '?')} | never grows |",
        f"| Open GitHub issues labelled bug | {bugs or '?'} | 0 |",
        f"| Crash reports filed since {tag} | {len(crashes)} | 0 |",
        "",
    ]


def facts() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [BEGIN, "", f"_Generated {now}. Do not edit inside this block; rerun the tool._", ""]

    quests = open_quests()
    flag = f" **over the cap of {QUEST_CAP}: park or close before adding**" if len(quests) > QUEST_CAP else ""
    lines += [f"### Open quests ({len(quests)}){flag}", ""]
    lines += [f"- {q['id']} [{q.get('horizon', '')}] {q.get('title', '')}" for q in quests] or ["- none"]
    lines.append("")

    rel = releases()
    milestone = {}
    mpath = ROOT / "tools" / "roadmap" / "milestone.json"
    if mpath.exists():
        milestone = json.loads(mpath.read_text())
    lines += ["### Releases", ""]
    if rel:
        lines += ["| Tag | Date | Downloads (context) |", "|---|---|---|"]
        lines += [f"| {t} | {d} | {n} |" for t, d, n in rel]
        if milestone.get("since") and rel[0][0] != milestone.get("since") and milestone.get("version") <= rel[0][0]:
            lines += ["", f"**`milestone.json` is stale**: targets {milestone.get('version')} but {rel[0][0]} is out."]
    else:
        lines.append("- gh unavailable; run `gh release list`")
    lines.append("")
    if len(rel) >= 2:
        lines += quality(rel[0][0], rel[1][0])

    gh, ga = last_metric("github"), last_metric("ga")
    lines += ["### Reach (context only: moves with outreach, not with release quality)", ""]
    if gh:
        lines.append(f"- GitHub ({gh['ts'][:10]}): {gh.get('stars')} stars, {gh.get('forks')} forks, {gh.get('downloads')} downloads all-time")
    if ga:
        lines.append(f"- Website ({ga['ts'][:10]}, last {ga.get('days')} days): {ga.get('sessions')} sessions, {ga.get('users')} users")
    if not (gh or ga):
        lines.append("- no metrics yet (`tools/roadmap/roadmap.py ga-pull`)")
    lines.append("")

    merges = sh("git", "log", "main", "--merges", "--first-parent", "-5", "--format=- %ad %s", "--date=short")
    lines += ["### Last merges to main", "", merges or "- none", "", END]
    return "\n".join(lines)


TEMPLATE = """# NOW

The one page every session reads first. Hand-kept sections are owned by the owner and the agent
together; the facts block is generated by `python3 tools/lifecycle/now.py`.
Map of the process: `.claude/skills/infinite-lifecycle/SKILL.md`.

## Release goal (owner sets; judged by the quality table below, not downloads)

| Field | Value |
|---|---|
| Next release | _not set_ |
| Makes right | |
| Done when | Fewer escaped fixes than the last release; known failures don't grow |

## Claims (add a row before touching anything; remove it when done)

| Session | Branch / worktree | Quest | Uses | Since |
|---|---|---|---|---|

## Waiting on owner (one at a time, recommended answer first)

## Decisions (newest first, keep the last 10)

## Rule conflicts noticed (settled by the monthly rule audit)

{facts}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", action="store_true", help="print the facts block instead of writing NOW.md")
    args = ap.parse_args()
    block = facts()
    if args.print:
        print(block)
        return
    if not NOW.exists():
        NOW.write_text(TEMPLATE.format(facts=block))
    else:
        text = NOW.read_text()
        if BEGIN in text and END in text:
            head, rest = text.split(BEGIN, 1)
            text = head + block + rest.split(END, 1)[1]
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
        NOW.write_text(text)
    print(f"wrote {NOW.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
