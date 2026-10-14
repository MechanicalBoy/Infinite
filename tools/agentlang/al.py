#!/usr/bin/env python3
"""The B1 tool: the language on top of a working patch (work.inf in the current directory).

    al.py apply FILE   decode a paragraph of sentences onto work.inf; keep it only if it also --validates
    al.py ask TYPE     keys, slots and outputs of a node type
    al.py show         the current patch as sentences
    al.py check        validate + graph + probe, one JSON line (same code as ./check)
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import codec, check  # noqa: E402

WORK = "work.inf"
LOG = ".al_log.jsonl"


def log(ok):
    """One line per apply, so the harness can score first-try validity (T4)."""
    open(LOG, "a").write(json.dumps({"ok": bool(ok)}) + "\n")


def main(argv):
    cmd = argv[0] if argv else ""
    cur = open(WORK).read() if os.path.exists(WORK) else codec.EMPTY
    if cmd == "apply":
        r = codec.decode(open(argv[1]).read(), cur)
        if not r.get("ok"):
            log(False)
            print(json.dumps({"ok": False, "errors": r["errors"][:1]}))
            return 1
        tmp = WORK + ".try"
        open(tmp, "w").write(r["patch_text"])
        ok, errs, warns = check.validate(tmp)
        hard = [e for e in errs] or [w for w in warns if w.get("code") != "W_UNUSED_NODE"]
        if hard:
            log(False)
            os.remove(tmp)
            print(json.dumps({"ok": False, "errors": [dict(hard[0], level=4, code="E_FIELD" if "field" in json.dumps(hard[0]).lower() else hard[0].get("code"))]}))
            return 1
        log(True)
        os.replace(tmp, WORK)
        print(json.dumps({"ok": True, "checked_by": "--validate", "warnings": [w.get("code") for w in warns][:3]}))
        return 0
    if cmd == "ask":
        print(json.dumps(codec.ask(" ".join(argv[1:]))))
        return 0
    if cmd == "show":
        r = codec.encode(cur)
        print(r if isinstance(r, str) else json.dumps(r))
        return 0
    if cmd == "check":
        return check.main([WORK])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
