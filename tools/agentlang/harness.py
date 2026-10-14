#!/usr/bin/env python3
"""Benchmark harness: one `claude -p` session per (task, arm, model), scored by the oracle.

  harness.py --arm B0|B0p|B1 --split dev|held-out|all [--tasks b01,t02] --model MODEL
             [--cap-usd 0.6] [--max-turns 15] [--out out/runs.jsonl] [--dry]

Arms (same oracle, same CLI, same cap; only the language and the check loop differ):
  B0   today's loop: patch-authoring skill as context; the agent edits work.inf and calls ./inf itself
  B0p  control: B0 plus ./check (validate + graph + probe in one call)
  B1   the new language: SPEC.md as context; the agent writes sentences and calls ./al apply|ask|show|check
Run it where `claude -p` is logged in. Needs the Infinite build (env INFINITE_APP).
Each run appends one JSON line to --out: tokens (in, cache, out), turns, usd, seconds, oracle result.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check, codec, oracle  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILL = os.path.join(REPO, ".claude/skills/infinite-patch-authoring/SKILL.md")
SPEC = os.path.join(HERE, "SPEC.md")
APP = check.APP

NOTES = {
    "B0": "Work only in the current directory. The patch is work.inf (edit it with Write/Read). Run the Infinite CLI as ./inf (for example `./inf --validate work.inf`). Skip layout and Comment nodes. Stop when the patch does what the task says and validates.",
    "B0p": "Work only in the current directory. The patch is work.inf (edit it with Write/Read). Run `./check work.inf` for validate + graph + probe in one call, or the CLI as ./inf. Skip layout and Comment nodes. Stop when the patch does what the task says and validates.",
    "B1": "Work only in the current directory. The patch is work.inf; you never edit it by hand. Write sentences to a file and run `./al apply FILE`; `./al ask TYPE` looks up a node; `./al show` prints the patch as sentences; `./al check` validates and probes. Stop when the patch does what the task says and validates.",
}


def wrappers(d, arm):
    def w(name, body):
        p = os.path.join(d, name)
        open(p, "w").write("#!/bin/sh\n" + body + "\n")
        os.chmod(p, 0o755)
    w("inf", f'exec "{APP}" "$@"')
    if arm in ("B0p",):
        w("check", f'exec python3 "{HERE}/check.py" "$@"')
    if arm == "B1":
        w("al", f'exec python3 "{HERE}/al.py" "$@"')
    open(os.path.join(d, "empty-mcp.json"), "w").write('{"mcpServers":{}}')


def context(arm):
    if arm == "B1":
        return open(SPEC).read() + "\n\n" + NOTES["B1"]
    return open(SKILL).read() + "\n\n" + NOTES[arm]


def stats_for(task, path):
    out = []
    for p in task["oracle"]:
        if p["kind"] == "frame_stats":
            d = tempfile.mkdtemp()
            _, j, _ = check.run(["--frame", path, str(p["t"]), d + "/"])
            for s in j.get("frame_stats") or []:
                s = dict(s)
                for k in [k for k in s if k.endswith('_percent')]:
                    s[k] = s[k] / 100.0  # frozen tasks state percent stats as fractions; the CLI reports 0-100
                s["t"] = p["t"]
                out.append(s)
    return out


def score(task, path):
    if not os.path.exists(path):
        return {"ok": False, "reason": "no work.inf"}
    text = open(path).read()
    ok_v, errs, warns = check.validate(path)
    r = oracle.evaluate(task, text, stats_for(task, path) or None)
    # the real CLI replaces the static no_errors stand-in
    for x in r["results"]:
        if x["kind"] == "no_errors":
            x["pass"], x["detail"] = ok_v, "CLI --validate"
    failed = [x for x in r["results"] if x["pass"] is False]
    pending = [x for x in r["results"] if x["pass"] is None]
    return {"ok": not failed and not pending, "failed": len(failed), "pending": len(pending),
            "results": r["results"], "valid": ok_v}


def run_one(task, arm, model, cap, turns, claude):
    d = tempfile.mkdtemp(prefix=f"al-{task['id']}-{arm}-")
    wrappers(d, arm)
    work = os.path.join(d, "work.inf")
    if task.get("start_patch"):
        shutil.copy(os.path.join(HERE, "tasks", os.path.basename(task["start_patch"])), work)
    elif arm == "B1":
        open(work, "w").write(codec.EMPTY)
    ctx = os.path.join(d, "context.md")
    open(ctx, "w").write(context(arm))
    tools = "Bash,Read,Write"
    allowed = ["Bash(./inf:*)", "Bash(./check:*)", "Bash(./al:*)", "Read", "Write"]
    cmd = [claude, "-p", task["goal_text"], "--model", model, "--output-format", "json",
           "--system-prompt", open(ctx).read(), "--tools", tools, "--allowedTools", *allowed,
           "--permission-mode", "acceptEdits", "--max-turns", str(turns), "--max-budget-usd", str(cap),
           "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
           "--mcp-config", os.path.join(d, "empty-mcp.json"), "--disable-slash-commands"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
    secs = round(time.time() - t0, 1)
    try:
        j = json.loads(r.stdout)
    except ValueError:
        j = {"error": (r.stdout + r.stderr)[-300:]}
    u = j.get("usage") or {}
    rec = {"task": task["id"], "split": task["split"], "arm": arm, "model": model, "secs": secs,
           "in": u.get("input_tokens"), "cache_create": u.get("cache_creation_input_tokens"),
           "cache_read": u.get("cache_read_input_tokens"), "out": u.get("output_tokens"),
           "turns": j.get("num_turns"), "usd": j.get("total_cost_usd"), "is_error": j.get("is_error"),
           "error": j.get("error"), "dir": d, "oracle": score(task, work)}
    rec["tokens_total"] = sum(v or 0 for v in (rec["in"], rec["cache_create"], rec["cache_read"], rec["out"]))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["B0", "B0p", "B1"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--tasks")
    ap.add_argument("--model", required=True)
    ap.add_argument("--cap-usd", type=float, default=0.6)
    ap.add_argument("--max-turns", type=int, default=15)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "runs.jsonl"))
    ap.add_argument("--claude", default=shutil.which("claude") or "claude")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    T = oracle.load_tasks()
    ids = a.tasks.split(",") if a.tasks else [i for i, t in T.items() if a.split in ("all", t["split"])]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    n = ok = 0
    for i in ids:
        if a.dry:
            print(i, a.arm, a.model)
            continue
        rec = run_one(T[i], a.arm, a.model, a.cap_usd, a.max_turns, a.claude)
        open(a.out, "a").write(json.dumps(rec) + "\n")
        n += 1
        ok += bool(rec["oracle"]["ok"])
        print(json.dumps({k: rec[k] for k in ("task", "arm", "tokens_total", "turns", "usd", "secs")} | {"pass": rec["oracle"]["ok"], "err": rec["error"]}), flush=True)
    print(json.dumps({"ok": True, "runs": n, "passed": ok, "out": a.out}))


if __name__ == "__main__":
    main()
