#!/usr/bin/env python3
"""Evaluate a task's oracle (a predicate list) against a .inf file. Never a hash.

  oracle.py TASK_ID patch.inf [--stats stats.json] [--tasks tasks.json]

Predicates (tasks.json `oracle`):
  types_present {types}            every type appears at least once
  types_absent  {types}            none of the types appears
  type_count    {type, op, n}      op is == >= <=
  edges         {edges:[[tag, dstType, slot, srcType]...], absent?}  each wire exists (or none exists)
  params        {type, key, value+tol | text | contains:[regex]}     some node of the type has it
  no_errors     a static stand-in for `--validate` (see static_errors): load, types, slots, kinds,
                slot taken, unreachable nodes. The CLI's own check is Phase 2.
  frame_stats   {t, seed, stat, min?, max?}   read from --stats (the CLI status line, or its
                frame_stats list); without --stats the predicate is `pending`, not failed.
Exit: 0 every static predicate passes (pending allowed), 1 a predicate failed, 2 usage error.
The last stdout line is one JSON object.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import facts, inf  # noqa: E402

SINKS = {"Output", "Audio Out"}


def resolve(g, F):
    """-> (wires, errors). wires: dict(tag, dst, slot, src) with Node objects and slot index."""
    errors, wires = [], []
    for e in g.extras:
        if e["tag"] == "bad":
            errors.append(f"unreadable line: {e['line']}")
    seen_idx, seen_id = set(), set()
    for n in g.nodes:
        if n.index in seen_idx:
            errors.append(f"duplicate node index {n.index}")
        seen_idx.add(n.index)
        if n.id:
            if n.id in seen_id:
                errors.append(f"duplicate id {n.id}")
            seen_id.add(n.id)
        tf = F.type(n.type)
        if not tf:
            errors.append(f"unknown node type {n.type}")
            continue
        if n.type in F.complete:
            for tag, key, _ in n.params:
                if key not in tf.keys:
                    errors.append(f"{n.type} has no key {key}")
    taken = set()
    for w in g.wires:
        d, s = g.resolve(w["dst"]), g.resolve(w["src"])
        if not d or not s:
            errors.append(f"wire refers to a missing node: {w['dst']} <- {w['src']}")
            continue
        dt, st = F.type(d.type), F.type(s.type)
        if not dt or not st:
            continue
        si = F.slot_index(d.type, w["slot"])
        if si is None:
            errors.append(f"{d.type} has no input slot {w['slot']}")
            continue
        kind = dt.inputs[si][1]
        if not st.outputs or st.outputs[0][1] != kind:
            errors.append(f"cannot wire {s.type} into {d.type}.{w['slot']} ({kind})")
            continue
        if facts.wire_tag(kind) != w["tag"]:
            errors.append(f"record {w['tag']} for a {kind} slot")
        if (d.index, si) in taken:
            errors.append(f"{d.type} input {w['slot']} is wired twice")
        taken.add((d.index, si))
        wires.append({"tag": w["tag"], "dst": d, "slot": si, "src": s})
    # reachability
    feeds = {}
    for w in wires:
        feeds.setdefault(w["dst"].index, []).append(w["src"].index)
    live, stack = set(), [n.index for n in g.nodes if n.type in SINKS]
    while stack:
        i = stack.pop()
        if i in live:
            continue
        live.add(i)
        stack += feeds.get(i, [])
    for n in g.nodes:
        if n.index not in live and n.type != "Comment":
            errors.append(f"{n.type} {n.id or n.index} reaches no Output or Audio Out")
    return wires, errors


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def stat_for(stats, t):
    if isinstance(stats, dict):
        stats = stats.get("frame_stats", [stats])
    for e in stats:
        if num(e.get("t", e.get("time"))) == num(t):
            return e
    return stats[0] if len(stats) == 1 else None


def check(pred, g, wires, errors, F, stats):
    k = pred["kind"]
    types = [n.type for n in g.nodes]
    if k == "types_present":
        miss = [t for t in pred["types"] if t not in types]
        return (not miss), f"missing {miss}" if miss else "ok"
    if k == "types_absent":
        bad = [t for t in pred["types"] if t in types]
        return (not bad), f"still present {bad}" if bad else "ok"
    if k == "type_count":
        c = types.count(pred["type"])
        ok = {"==": c == pred["n"], ">=": c >= pred["n"], "<=": c <= pred["n"]}[pred["op"]]
        return ok, f"{pred['type']} x{c}"
    if k == "edges":
        miss = []
        for tag, dt, slot, st in pred["edges"]:
            si = F.slot_index(dt, slot)
            hit = any(w["tag"] == tag and w["dst"].type == dt and w["slot"] == si and w["src"].type == st
                      for w in wires)
            if hit == bool(pred.get("absent")):
                miss.append(f"{tag} {dt}.{slot}<-{st}")
        return (not miss), (("present: " if pred.get("absent") else "missing: ") + ", ".join(miss)) if miss else "ok"
    if k == "params":
        why = f"no {pred['type']} node"
        for n in g.nodes:
            if n.type != pred["type"]:
                continue
            p = n.get(pred["key"])
            if not p:
                why = f"{pred['key']} not set"
                continue
            val = p[2]
            if "value" in pred:
                v = num(val)
                if v is not None and abs(v - pred["value"]) <= pred.get("tol", 0) + 1e-9:
                    return True, "ok"
                why = f"{pred['key']} = {val}, want {pred['value']} +- {pred.get('tol', 0)}"
            elif "text" in pred:
                if val.strip().lower() == pred["text"].lower():
                    return True, "ok"
                why = f"{pred['key']} = {val}, want {pred['text']}"
            elif all(re.search(c, val) for c in pred["contains"]):
                return True, "ok"
            else:
                why = f"{pred['key']} does not match {pred['contains']}"
        return False, why
    if k == "no_errors":
        return (not errors), (errors[0] if errors else "ok")
    if k == "frame_stats":
        if stats is None:
            return None, "pending: needs --stats"
        e = stat_for(stats, pred["t"])
        v = num(e.get(pred["stat"])) if e else None
        if v is None:
            return False, f"no {pred['stat']} at t={pred['t']}"
        ok = (pred.get("min") is None or v >= pred["min"]) and (pred.get("max") is None or v <= pred["max"])
        return ok, f"{pred['stat']} = {v}"
    raise ValueError(f"unknown predicate {k}")


def evaluate(task, patch_text, stats=None, F=None):
    F = F or facts.load()
    g = inf.parse(patch_text)
    wires, errors = resolve(g, F)
    res = []
    for p in task["oracle"]:
        ok, why = check(p, g, wires, errors, F, stats)
        res.append({"kind": p["kind"], "pass": ok, "detail": why})
    failed = [r for r in res if r["pass"] is False]
    pending = [r for r in res if r["pass"] is None]
    return {"ok": not failed, "failed": len(failed), "pending": len(pending), "results": res}


def load_tasks(path=None):
    path = path or os.path.join(HERE, "tasks", "tasks.json")
    return {t["id"]: t for t in json.load(open(path))["tasks"]}


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    tid, patch = argv[0], argv[1]
    stats = tasks_path = None
    if "--stats" in argv:
        stats = json.load(open(argv[argv.index("--stats") + 1]))
    if "--tasks" in argv:
        tasks_path = argv[argv.index("--tasks") + 1]
    tasks = load_tasks(tasks_path)
    if tid not in tasks:
        print(json.dumps({"ok": False, "error": f"unknown task {tid}"}))
        return 2
    out = evaluate(tasks[tid], open(patch).read(), stats)
    out["task"] = tid
    print(json.dumps(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
