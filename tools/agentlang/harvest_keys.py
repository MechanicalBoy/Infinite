#!/usr/bin/env python3
"""Harvest key kinds (f/i/b/c/s) per node type from the repo's own .inf files into keys_seen.json.

Why: the codec must write `f` or `i` for a key without the built app. This is the offline source;
nodefacts.json (dump_facts.py, from `Infinite --describe --json`) overrides it where present.
Usage: python3 tools/agentlang/harvest_keys.py        exit 0; last line is JSON.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inf, facts  # noqa: E402


def corpus():
    out = []
    for pat in ("assets/examples/**/*.inf", "assets/templates/**/*.inf", "tests/**/*.inf"):
        out += glob.glob(os.path.join(facts.ROOT, pat), recursive=True)
    return sorted(out)


def main():
    seen, clash = {}, []
    for p in corpus():
        for n in inf.parse(open(p, errors="replace").read()).nodes:
            d = seen.setdefault(n.type, {})
            for tag, key, _ in n.params:
                if key in d and d[key] != tag:
                    clash.append(f"{n.type}.{key}")
                d.setdefault(key, tag)
    json.dump(seen, open(facts.KEYS_SEEN, "w"), indent=0, sort_keys=True)
    print(json.dumps({"ok": True, "types": len(seen), "keys": sum(map(len, seen.values())), "clashes": sorted(set(clash))}))


if __name__ == "__main__":
    main()
