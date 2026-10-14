#!/usr/bin/env python3
"""Codec tests T1, T2, T3, T6. Run: python3 tools/agentlang/test_codec.py   (exit 0 / 1, last line JSON)

T1  .inf -> sentences -> .inf equal (parsed graphs) for every corpus patch the grammar can express;
    encode(decode(x)) == x for canonical x (the encoding of every reference solution and start patch).
T2  200 random valid sentence sequences decode, ok, with no wiring error.
T3  one negative case per error code, with the expected hint; E_FIELD is the CLI's (marked, not run).
T6  Field is frozen: git diff --quiet main -- src/core/field tests/field.
"""
import glob, json, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import codec, facts, inf, oracle  # noqa: E402

ROOT = facts.ROOT
F = facts.load()
EMPTY = codec.EMPTY
bad = []
out = {}


def fail(msg):
    bad.append(msg)
    print("FAIL", msg)


def corpus():
    files = []
    for pat in ("assets/examples/**/*.inf", "assets/templates/**/*.inf", "tests/**/*.inf"):
        files += glob.glob(os.path.join(ROOT, pat), recursive=True)
    return sorted(set(files))


# ---------------------------------------------------------------- T1
def t1():
    files = corpus()
    ok = excl = 0
    reasons = {}
    for p in files:
        rel = os.path.relpath(p, ROOT)
        text = open(p, errors="replace").read()
        e = codec.encode(text, F)
        if not e["complete"]:
            excl += 1
            r = e["excluded"][0].split(":")[0].split(" (")[0]
            reasons[r] = reasons.get(r, 0) + 1
            continue
        r = codec.decode(e["sentences"], EMPTY, F)
        if not r["ok"]:
            fail(f"T1 {rel}: decode failed {r['errors']}")
            continue
        if codec.canon(r["patch_text"], F) != codec.canon(text, F):
            fail(f"T1 {rel}: graph differs after the round trip")
            continue
        e2 = codec.encode(r["patch_text"], F)
        if e2["sentences"] != e["sentences"]:
            fail(f"T1 {rel}: encode(decode(x)) != x")
            continue
        ok += 1
    # canonical sentences from the task patches
    canon_n = 0
    tdir = os.path.join(HERE, "tasks")
    for p in sorted(glob.glob(os.path.join(tdir, "*.inf"))):
        text = open(p).read()
        e = codec.encode(text, F)
        if not e["complete"]:
            fail(f"T1 task patch {os.path.basename(p)} excluded: {e['excluded']}")
            continue
        r = codec.decode(e["sentences"], EMPTY, F)
        if not r["ok"] or codec.encode(r["patch_text"], F)["sentences"] != e["sentences"]:
            fail(f"T1 canonical {os.path.basename(p)}")
        elif codec.canon(r["patch_text"], F) != codec.canon(text, F):
            fail(f"T1 canonical graph {os.path.basename(p)}")
        else:
            canon_n += 1
    out["T1"] = {"patches": len(files), "round_trip_equal": ok, "excluded": excl,
                 "excluded_by": dict(sorted(reasons.items(), key=lambda kv: -kv[1])), "canonical_ok": canon_n}


# ---------------------------------------------------------------- T3
def first_error(text, patch=EMPTY, FF=None):
    r = codec.decode(text, patch, FF or F)
    return None if r["ok"] else r["errors"][0]


def t3():
    cases = []

    def want(name, text, code, level, needle, patch=EMPTY, FF=None):
        e = first_error(text, patch, FF)
        if not e or e["code"] != code or e["level"] != level or needle not in e["hint"]:
            fail(f"T3 {name}: got {e}")
        else:
            cases.append(name)

    want("lex verb", "blurr b\n", "E_LEX", 1, "nearest:")
    want("lex verb suggests", "wyre a b\n", "E_LEX", 1, "wire")
    want("lex type", "add gaussianblurr as b\n", "E_LEX", 1, "gaussianblur")
    want("syn set", "add Shape as s\nset s.sizeX\n", "E_SYN", 2, "set <name>.<key> <value>")
    want("syn add", "add Shape\n", "E_SYN", 2, "add <type> as <name>")
    want("syn field hash", "add FieldPixel as p\nfield p col = vec3(1.0); # c\n", "E_SYN", 2, "no #")
    want("sem name", "set ghost.sizeX 1\n", "E_SEM", 3, "no node named ghost")
    want("sem kind", "add Shape as s\nadd Audio Out as a\nwire s a\n", "E_SEM", 3, "takes audio")
    want("sem slot", "add Blend as b\nadd Shape as s\nwire s b\n", "E_SEM", 3, "write dst.slot")
    want("sem taken", "add Shape as s\nadd Shape as t\nadd Output as o\nwire s o.in\nwire t o.in\n", "E_SEM", 3, "already takes s")
    want("sem not field", "add Shape as s\nfield s col = 1;\n", "E_SEM", 3, "not a Field node")
    want("sem value", "add Shape as s\nset s.sizeX big\n", "E_SEM", 3, "needs a number")
    want("sem dup", "add Shape as s\nadd Circle as s\n", "E_SEM", 3, "taken")
    # range check: the same code path with a facts table that has ranges (nodefacts.json needs the app)
    rf = facts.load(nodefacts=None)
    rf.has_ranges = True
    rf.types["Blend"].keys["mix"] = {"tag": "f", "min": 0.0, "max": 1.0, "options": [], "default": 0.5}
    rf.complete.add("Blend")
    want("sem range", "add Blend as b\nset b.mix 9\n", "E_SEM", 3, "min 0.0 max 1.0 current 0.5", FF=rf)
    want("sem key", "add Blend as b\nset b.mixx 1\n", "E_SEM", 3, "has no key mixx", FF=rf)
    # a paragraph is all or nothing
    r = codec.decode("add Shape as s\nset s.sizeX 0.5\n\nadd Shape as t\nwire t s\n", EMPTY, F)
    if r["ok"] or r["applied"] != 1 or "t" in r["patch_text"].split("id t")[0:0] or "id t" in r["patch_text"]:
        fail("T3 paragraph not atomic")
    else:
        cases.append("paragraph atomic")
    r = codec.decode("add Shape as s\n", EMPTY, F)
    if not r["ok"] or "--validate" not in r["checked_by"]:
        fail("T3 E_FIELD marker missing from an ok reply")
    else:
        cases.append("E_FIELD marked as checked by --validate")
    out["T3"] = {"cases": len(cases), "codes": ["E_LEX", "E_SYN", "E_SEM", "E_FIELD(marked)"]}


# ---------------------------------------------------------------- T2
def t2(n=200):
    rnd = random.Random(7)
    producers = [t for t in F.types.values() if t.outputs and wire_ok(t)]
    consumers = [t for t in F.types.values() if t.inputs and any(facts.wire_tag(k) for _, k in t.inputs)]
    keyed = [t for t in F.types.values() if t.name in json.load(open(facts.KEYS_SEEN))]
    seen = json.load(open(facts.KEYS_SEEN))
    done = 0
    for case in range(n):
        lines, nodes, wired = [], {}, set()
        for i in range(rnd.randint(2, 8)):
            tf = rnd.choice(producers + consumers + keyed)
            name = f"n{i}"
            lines.append(f"add {tf.name} as {name}")
            nodes[name] = tf
            if seen.get(tf.name) and rnd.random() < 0.7 and tf.name not in facts.FIELD_TYPES:
                key, tag = rnd.choice(sorted(seen[tf.name].items()))
                kf = facts.load().type(tf.name).keys.get(key, {}) if hasattr(facts, "load") else {}
                lo = kf.get("min") if kf.get("min") is not None else 0
                hi = kf.get("max") if kf.get("max") is not None else 5
                if hi < lo:
                    lo, hi = hi, lo
                nopt = len(kf.get("options") or []) or 4
                val = {"f": str(round(rnd.uniform(lo, hi), 2)), "i": str(rnd.randint(0, nopt - 1) if kf.get("options") else rnd.randint(int(lo), int(min(hi, lo + 3)))),
                       "b": rnd.choice("01"), "c": "0.5 0.5 0.5", "s": "text"}[tag]
                lines.append(f"set {name}.{key} {val}")
            if tf.name in facts.FIELD_TYPES:
                lines.append(f"field {name} out = in * {rnd.randint(1, 9)};")
        for _ in range(rnd.randint(0, 6)):
            s, d = rnd.choice(list(nodes)), rnd.choice(list(nodes))
            stf, dtf = nodes[s], nodes[d]
            if s == d or not stf.outputs:
                continue
            for si, (slot, kind) in enumerate(dtf.inputs):
                if facts.wire_tag(kind) and kind == stf.outputs[0][1] and (d, si) not in wired:
                    wired.add((d, si))
                    lines.append(f"wire {s} {d}.{slot}")
                    break
        if len(lines) > 3 and rnd.random() < 0.3:
            lines.append(f"del {rnd.choice(list(nodes))}")
        text = "\n".join(lines) + "\n"
        try:
            r = codec.decode(text, EMPTY, F)
        except Exception as e:  # noqa: BLE001
            fail(f"T2 case {case}: exception {e!r}\n{text}")
            continue
        if not r["ok"]:
            fail(f"T2 case {case}: {r['errors']}\n{text}")
            continue
        g = inf.parse(r["patch_text"])
        _, errs = oracle.resolve(g, F)
        hard = [x for x in errs if "reaches no" not in x]
        if hard:
            fail(f"T2 case {case}: {hard[0]}")
            continue
        done += 1
    out["T2"] = {"cases": n, "decoded": done}


def wire_ok(tf):
    return facts.wire_tag(tf.outputs[0][1]) is not None


# ---------------------------------------------------------------- T6
def t6():
    r = subprocess.run(["git", "diff", "--quiet", "main", "--", "src/core/field", "tests/field"], cwd=ROOT)
    if r.returncode != 0:
        fail("T6 Field changed against main")
    out["T6"] = {"clean": r.returncode == 0}


def main():
    t1()
    t3()
    t2()
    t6()
    out["ok"] = not bad
    out["problems"] = len(bad)
    print(json.dumps(out))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
