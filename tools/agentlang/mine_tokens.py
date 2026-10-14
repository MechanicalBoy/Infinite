#!/usr/bin/env python3
"""Where do the tokens of a kind of work go? Mines Claude transcripts (~/.claude/projects/*/*.jsonl).

  mine_tokens.py --match REGEX [--min-turns 20] [--top 12]     last stdout line is JSON
A session is counted when its text matches REGEX. Per session: assistant turns, billed-equivalent tokens
(in + cache_create + out, and cache_read reported separately), and a split of the tool results by what produced
them: skill/reference reads, other file reads, shell/script output, images, searches, and the model's own output.
Read-only; nothing leaves the machine.
"""
import glob, json, os, re, sys
from collections import Counter

args = sys.argv[1:]
def opt(n, d=None): return args[args.index(n) + 1] if n in args else d
rx = re.compile(opt("--match"))
min_turns, top = int(opt("--min-turns", 20)), int(opt("--top", 12))
BASE = os.path.expanduser("~/.claude/projects")
sess = []
for f in glob.glob(BASE + "/*/*.jsonl"):
    try:
        raw = open(f, errors="ignore").read()
    except OSError:
        continue
    if not rx.search(raw):
        continue
    turns = fresh = cread = out = 0
    split, uses, iters = Counter(), {}, 0
    for line in raw.splitlines():
        try: r = json.loads(line)
        except ValueError: continue
        m = r.get("message") or {}
        u = m.get("usage")
        if r.get("type") == "assistant" and u:
            turns += 1
            fresh += (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
            cread += u.get("cache_read_input_tokens") or 0
            out += u.get("output_tokens") or 0
        c = m.get("content")
        if not isinstance(c, list): continue
        for b in c:
            if b.get("type") == "tool_use":
                inp = b.get("input") or {}
                p = inp.get("file_path") or inp.get("command") or ""
                if b["name"] == "Skill": kind = "skill"
                elif b["name"] == "Read" and re.search(r"/skills/|SKILL\.md|references/", p): kind = "skill_ref"
                elif b["name"] == "Read": kind = "file_read"
                elif b["name"] == "Bash": kind = "render" if re.search(r"render|ffmpeg|blender|assemble|cut\.py", p, re.I) else "shell"
                else: kind = b["name"].lower()
                uses[b["id"]] = kind
                iters += kind == "render"
            elif b.get("type") == "tool_result":
                body = b.get("content")
                if isinstance(body, list):
                    n = sum(len(x.get("text", "")) if x.get("type") == "text" else 1500 for x in body if isinstance(x, dict))
                    if any(isinstance(x, dict) and x.get("type") == "image" for x in body): split["image"] += n
                else:
                    n = len(body or "")
                split[uses.get(b.get("tool_use_id"), "other")] += n
    if turns >= min_turns:
        sess.append({"file": os.path.basename(f)[:8], "turns": turns, "fresh": fresh, "cache_read": cread, "out": out,
                     "render_runs": iters, "tool_result_chars": dict(split.most_common())})
sess.sort(key=lambda s: -(s["fresh"] + s["out"]))
tot = Counter()
for s in sess:
    tot.update(s["tool_result_chars"])
for s in sess[:top]:
    print(f"{s['file']} turns {s['turns']:4} fresh {s['fresh']:>9,} out {s['out']:>8,} cache_read {s['cache_read']:>12,} renders {s['render_runs']:3}  top: {list(s['tool_result_chars'].items())[:3]}")
n = len(sess)
print(json.dumps({"sessions": n, "turns": sum(s["turns"] for s in sess), "fresh": sum(s["fresh"] for s in sess),
                  "out": sum(s["out"] for s in sess), "cache_read": sum(s["cache_read"] for s in sess),
                  "render_runs": sum(s["render_runs"] for s in sess), "tool_result_chars_total": dict(tot.most_common())}))
