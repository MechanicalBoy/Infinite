#!/usr/bin/env python3
"""Node-chain fuzzer: random chains of 2-4 node types, wired by kind, run headless.

node_census.py tests one node at a time; patch_variants.py mutates existing patches but never adds cables.
This builds new patches: a seeded chain A > B > C > ... where each node's output feeds a matching input of
the next, the other inputs are fed by a canonical source or deliberately left unconnected, and now and then
the chain gets an awkward extra (a fan-out, a feedback cable, a wrong-kind cable) and a couple of extreme
parameter values. Each patch goes through the headless CLI, serial, never touching the app UI.

Hard checks: process exit 0 (3 = rejected as invalid and 4 = hardware refused are clean refusals, logged), no
signal, no timeout, a final JSON line, no NaN pixels, no NaN/inf in the audio summary, peak bounded, and two
runs of the same patch agree (nondeterminism in a chain that contains a node the census already marks
nondeterministic is reported as "known", not a failure). A failing chain is shrunk to its shortest failing prefix.

Usage:
  scripts/chain_fuzz.py [--bin PATH] [--out DIR] [--n 300] [--seed 1] [--timeout 60] [--replay "Type>Type>Type"]
Output: DIR/results.tsv (resumable by id), DIR/fail/<id>.inf for each failure, summary on stdout.
Exit 0 no hard failures, 1 at least one.
"""
import argparse, hashlib, json, math, os, random, subprocess, sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import node_census as nc  # FEED, TAG, RENDER_SLOT, SHAPE_POS_X

CHAIN_KINDS = ("image", "geometry", "audio", "note")
SKIP_TYPES = {"Output", "Comment", "Group", "Null", "Viewport", "Render 3D", "Model 3D", "Group 3D", "Null 3D"}
OK_EXIT = (0,)
REFUSED_EXIT = {3: "invalid", 4: "hardware"}


def load_types(binary, out):
    schema = os.path.join(out, "describe.json")
    if not os.path.exists(schema):
        subprocess.run([binary, "--describe", "--json", schema], capture_output=True)
    types = json.load(open(schema))["types"]
    return {t["type"]: t for t in types if not t.get("hardware_driven") and t["type"] not in SKIP_TYPES}


def known_nondeterministic():
    p = os.path.join(ROOT, "tests", "headless", "census_baseline.json")
    try:
        return {r["type"] for r in json.load(open(p)) if "nondeterministic" in r.get("issues", [])}
    except Exception:
        return set()


class Gen:
    def __init__(self, types):
        self.types = types
        self.by_out = {k: [] for k in CHAIN_KINDS}
        self.by_in = {k: [] for k in CHAIN_KINDS}
        for name, t in sorted(types.items()):
            if t["outputs"] and t["outputs"][0]["kind"] in self.by_out:
                self.by_out[t["outputs"][0]["kind"]].append(name)
            for k in {i["kind"] for i in t["inputs"]}:
                if k in self.by_in:
                    self.by_in[k].append(name)

    def chain(self, rnd, length):
        """List of type names; each (after the first) has an input of the previous node's output kind."""
        start = rnd.choice([n for n, t in sorted(self.types.items()) if t["outputs"] and t["outputs"][0]["kind"] in CHAIN_KINDS])
        names = [start]
        for _ in range(length - 1):
            kind = self.types[names[-1]]["outputs"][0]["kind"]
            nxt = [n for n in self.by_in.get(kind, []) if self.types[n]["outputs"] and self.types[n]["outputs"][0]["kind"] in CHAIN_KINDS]
            if not nxt:
                break
            names.append(rnd.choice(nxt))
        return names

    def spec(self, rnd, names):
        """Everything random about one patch, as plain data, so a shrink can rebuild a prefix from it."""
        extras = []
        if rnd.random() < 0.12:
            extras.append(("feedback",))
        if rnd.random() < 0.12:
            extras.append(("fanout",))
        if rnd.random() < 0.10:
            extras.append(("wrongkind",))
        sets = []
        for idx in rnd.sample(range(len(names)), k=min(len(names), rnd.choice([0, 1, 2]))):
            rows = [r for r in self.types[names[idx]].get("rows", [])
                    if r.get("kind") == "float" and r.get("min") is not None and r.get("max") is not None and r.get("ui")]
            if rows:
                r = rnd.choice(rows)
                sets.append((idx, r["key"], r["min"] if rnd.random() < 0.5 else r["max"]))
        unconnected = {i: rnd.random() < 0.3 for i in range(len(names))}
        return {"names": names, "extras": extras, "sets": sets, "unc": unconnected}

    # ---- branching topologies: split one output into parallel paths and merge them again --------------------
    MAX_NODES = 12

    def merges(self, kind):
        """Types whose output is `kind` and that take two or more inputs of `kind` (a mixer, a join, a blend)."""
        return [n for n, t in sorted(self.types.items())
                if t["outputs"] and t["outputs"][0]["kind"] == kind and sum(1 for i in t["inputs"] if i["kind"] == kind) >= 2]

    def preserving(self, kind):
        return [n for n, t in sorted(self.types.items())
                if t["outputs"] and t["outputs"][0]["kind"] == kind and any(i["kind"] == kind for i in t["inputs"])]

    def split(self, rnd, kind, depth, budget):
        """("split", branches, merge type, open): 2-4 parallel paths of 0-2 same-kind nodes, joined by a merge node."""
        m = rnd.choice(self.merges(kind))
        slots = sum(1 for i in self.types[m]["inputs"] if i["kind"] == kind)
        branches = []
        for _ in range(min(rnd.choice([2, 2, 3, 4]), slots)):
            b = []
            for _ in range(rnd.choice([0, 1, 1, 2, 2])):
                if budget[0] <= 1:
                    break
                if depth > 0 and budget[0] >= 6 and rnd.random() < 0.2:
                    b.append(self.split(rnd, kind, depth - 1, budget))
                else:
                    b.append(("node", rnd.choice(self.preserving(kind))))
                    budget[0] -= 1
            branches.append(b)
        budget[0] -= 1  # the merge node
        return ("split", branches, m, rnd.random() < 0.10)  # open: the last path is left dangling

    def plan(self, rnd):
        budget = [self.MAX_NODES - 1]
        head = rnd.choice([n for n, t in sorted(self.types.items()) if t["outputs"] and t["outputs"][0]["kind"] in CHAIN_KINDS])
        stages, kind = [("node", head)], self.types[head]["outputs"][0]["kind"]
        for _ in range(rnd.choice([1, 2, 2, 3])):
            if budget[0] <= 1:
                break
            if kind in CHAIN_KINDS and self.merges(kind) and budget[0] >= 4 and rnd.random() < 0.6:
                stages.append(self.split(rnd, kind, 1, budget))
                continue
            nxt = [n for n in self.by_in.get(kind, []) if self.types[n]["outputs"] and self.types[n]["outputs"][0]["kind"] in CHAIN_KINDS]
            if not nxt:
                break
            n = rnd.choice(nxt)
            stages.append(("node", n))
            budget[0] -= 1
            kind = self.types[n]["outputs"][0]["kind"]
        return stages

    def mods(self, rnd, names):
        """0-3 modulators, each bound to a float parameter of a chain node or of an earlier modulator."""
        srcs = [n for n, t in sorted(self.types.items())
                if t["category"] == "Modulators" and t["outputs"] and t["outputs"][0]["kind"] == "modulator"]
        out = []
        for _ in range(rnd.choice([0, 1, 1, 2, 3])):
            m = rnd.choice(srcs)
            pool = [("n", i, names[i]) for i in range(len(names))] + [("m", j, o["type"]) for j, o in enumerate(out)]
            kind, idx, tname = rnd.choice(pool if rnd.random() < 0.25 else pool[:len(names)])
            rows = [r for r in self.types[tname].get("rows", [])
                    if r.get("kind") == "float" and r.get("modulatable_index") is not None and r.get("min") is not None and r.get("max") is not None]
            if not rows:
                continue
            r = rnd.choice(rows)
            out.append({"type": m, "on": [kind, idx], "key": r["key"], "lo": r["min"], "hi": r["max"],
                        "pol": rnd.choice([0, 1]), "depth": round(rnd.uniform(0.2, 1.0), 3), "centre": rnd.choice([0.0, 0.5])})
        return out

    def graph_spec(self, rnd):
        stages = self.plan(rnd)
        names = flatten(stages)
        sp = self.spec(rnd, names)
        sp.update({"plan": stages, "mods": self.mods(rnd, names), "label": plan_str(stages)})
        return sp


def flatten(stages):
    out = []
    for st in stages:
        if st[0] == "node":
            out.append(st[1])
        else:
            for b in st[1]:
                out += flatten(b)
            out.append(st[2])
    return out


def plan_str(stages):
    parts = []
    for st in stages:
        if st[0] == "node":
            parts.append(st[1])
        else:
            paths = [plan_str(b) or "(direct)" for b in st[1]]
            if st[3]:
                paths[-1] += " (open)"
            parts.append("{" + " | ".join(paths) + "} > " + st[2])
    return " > ".join(parts)


def respec(types, sp, plan=None, mods=None):
    """The same patch with a different plan or modulator list; names, sets and the label follow from it."""
    plan = sp["plan"] if plan is None else plan
    names = flatten(plan)
    return dict(sp, plan=plan, names=names, label=plan_str(plan), mods=sp["mods"] if mods is None else mods,
                sets=[x for x in sp["sets"] if x[0] < len(names)])


def build(types, spec):
    """(patch text, sink kind, node ids of the chain nodes in order)."""
    names = spec["names"]
    lines, links, nid = ["infinite-patch 1"], [], [0]

    def add(node_spec, extra=""):
        nid[0] += 1
        lines.append(f"node {nid[0]} {node_spec}\n{extra}end")
        return nid[0]

    ids = []
    for i, n in enumerate(names):
        t = types[n]
        me = add(f"{t['category']} {n}")
        ids.append(me)
        used_slot = None
        if i > 0:
            prev_kind = types[names[i - 1]]["outputs"][0]["kind"]
            slots = [s["slot"] for s in t["inputs"] if s["kind"] == prev_kind]
            used_slot = slots[0]
            links.append(link(prev_kind, me, used_slot, ids[i - 1]))
        for s in t["inputs"]:
            if s["slot"] == used_slot or s["kind"] not in nc.FEED:
                continue
            if spec["unc"].get(i) and i > 0:
                continue  # left unconnected on purpose
            src = add(nc.FEED[s["kind"]])
            links.append(link(s["kind"], me, s["slot"], src))
    last = types[names[-1]]["outputs"][0]["kind"]
    for ex in spec["extras"]:
        if ex[0] == "feedback" and len(ids) > 1:
            k0 = types[names[0]]["inputs"]
            m = [s for s in k0 if s["kind"] == last]
            if m:
                links.append(link(last, ids[0], m[0]["slot"], ids[-1]))
        elif ex[0] == "fanout" and len(ids) > 1:
            kind = types[names[0]]["outputs"][0]["kind"]
            slots = [s["slot"] for s in types[names[-1]]["inputs"] if s["kind"] == kind]
            if slots:
                links.append(link(kind, ids[-1], slots[-1], ids[0]))
        elif ex[0] == "wrongkind" and len(ids) > 1:
            links.append(f"cable {ids[-1]} 0 {ids[0]}" if last != "image" else f"aud {ids[-1]} 0 {ids[0]}")
    sink = add_sink(add, links, last, ids[-1])
    return "\n".join(lines + links) + "\n", last, ids


def build_graph(types, spec):
    """Like build(), for a branching plan: (patch text, sink kind, node ids of the chain nodes in emission order)."""
    lines, links, nid, ids = ["infinite-patch 1"], [], [0], []

    def add(node_spec, extra=""):
        nid[0] += 1
        lines.append(f"node {nid[0]} {node_spec}\n{extra}end")
        return nid[0]

    def feed_rest(me, t, used, fed):
        for sl in t["inputs"]:
            if sl["slot"] in used or sl["kind"] not in nc.FEED:
                continue
            if fed:
                continue  # left unconnected on purpose
            links.append(link(sl["kind"], me, sl["slot"], add(nc.FEED[sl["kind"]])))

    def new_node(name, src, kind):
        t = types[name]
        me = add(f"{t['category']} {name}")
        ids.append(me)
        used = set()
        if src is not None:
            slot = [x["slot"] for x in t["inputs"] if x["kind"] == kind][0]
            links.append(link(kind, me, slot, src))
            used.add(slot)
        feed_rest(me, t, used, src is not None and spec["unc"].get(len(ids) - 1))
        return me

    def emit(stages, src, kind):
        for st in stages:
            if st[0] == "node":
                src, kind = new_node(st[1], src, kind), types[st[1]]["outputs"][0]["kind"]
                continue
            _, branches, mname, open_ = st
            ends = [emit(b, src, kind)[0] for b in branches]
            t = types[mname]
            me = add(f"{t['category']} {mname}")
            ids.append(me)
            slots = [x["slot"] for x in t["inputs"] if x["kind"] == kind]
            used = set()
            for bi, e in enumerate(ends):
                if bi < len(slots) and not (open_ and bi == len(ends) - 1):
                    links.append(link(kind, me, slots[bi], e))
                    used.add(slots[bi])
            feed_rest(me, t, used, False)
            src = me
        return src, kind

    end, last = emit(spec["plan"], None, None)
    mod_ids = []
    for m in spec["mods"]:
        t = types[m["type"]]
        mid = add(f"Modulators {m['type']}")
        for sl in t["inputs"]:
            if sl["kind"] in nc.FEED:
                links.append(link(sl["kind"], mid, sl["slot"], add(nc.FEED[sl["kind"]])))
        mod_ids.append(mid)
        which, idx = m["on"]
        dst = ids[idx] if which == "n" else mod_ids[idx]
        links.append(f"mod {dst} {m['key']} {mid} 0 {m['pol']} {m['depth']} {m['centre']} {m['lo']} {m['hi']}")
    for ex in spec["extras"]:
        if ex[0] == "feedback" and len(ids) > 1:
            m = [x for x in types[spec["names"][0]]["inputs"] if x["kind"] == last]
            if m:
                links.append(link(last, ids[0], m[0]["slot"], ids[-1]))
        elif ex[0] == "fanout" and len(ids) > 1:
            kind0 = types[spec["names"][0]]["outputs"][0]["kind"]
            slots = [x["slot"] for x in types[spec["names"][-1]]["inputs"] if x["kind"] == kind0]
            if slots:
                links.append(link(kind0, ids[-1], slots[-1], ids[0]))
        elif ex[0] == "wrongkind" and len(ids) > 1:
            links.append(f"cable {end} 0 {ids[0]}" if last != "image" else f"aud {end} 0 {ids[0]}")
    add_sink(add, links, last, end)
    return "\n".join(lines + links) + "\n", last, ids


def link(kind, dst, slot, src):
    return f"{nc.TAG[kind]} {dst} {slot} {src}" + (" 0" if kind == "note" else "")


def add_sink(add, links, kind, src):
    out = add("Utility Output")
    if kind == "image":
        links.append(f"cable {out} 0 {src}")
    elif kind == "geometry":
        r = add("3D Render 3D", "  f width 512\n  f height 512\n")
        links += [f"geo {r} 0 {src}", f"cable {out} 0 {r}"]
    elif kind == "audio":
        sh = add("Source Shape")
        links += [f"cable {out} 0 {sh}", f"aud {out} 1 {src}"]
    else:  # note: sound it with an oscillator
        osc, sh = add("Synths Oscillator"), add("Source Shape")
        links += [f"note {osc} 0 {src} 0", f"cable {out} 0 {sh}", f"aud {out} 1 {osc}"]
    return out


class Runner:
    def __init__(self, binary, out, timeout):
        self.bin, self.out, self.timeout = binary, out, timeout

    def run(self, args):
        try:
            p = subprocess.run([self.bin] + args, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return "timeout", {}
        last = (p.stdout.strip().splitlines() or [""])[-1]
        try:
            j = json.loads(last)
        except ValueError:
            j = None
        return p.returncode, j if j is not None else {"errors": [{"code": "NOJSON", "message": (p.stderr or p.stdout)[-160:]}]}

    def execute(self, patch_text, kind, sets, ids, tag, known):
        """-> (status, detail). status: pass | refused | fail."""
        d = os.path.join(self.out, "work", tag)
        os.makedirs(d, exist_ok=True)
        pf = os.path.join(d, "p.inf")
        open(pf, "w").write(patch_text)
        setargs = []
        for idx, key, val in sets:
            setargs += ["--set", f"{ids[idx]}.{key}={val}"]
        rc, j = self.run(["--validate", pf])
        if rc == 3 or (rc == 0 and not j.get("ok", True)):
            return "refused", "invalid:" + codes(j)
        if rc != 0:
            return "fail", f"validate rc={rc} {codes(j)}"
        res = []
        for rep in range(2):
            if kind in ("audio", "note"):
                of = os.path.join(d, f"a{rep}.json")
                rc, j = self.run(["--audio-summary", pf, of, "--duration", "1"] + setargs)
            else:
                rc, j = self.run(["--frame", pf, "0.5", os.path.join(d, f"f{rep}") + "/"] + setargs)
            if rc in REFUSED_EXIT:
                return "refused", REFUSED_EXIT[rc] + ":" + codes(j)
            # An Output fed by a node with no image says so with E_RENDER; that is the right answer, not a bug.
            if rc == 5 and "produced no image" in json.dumps(j):
                return "refused", "no-image:" + codes(j)
            if rc != 0:
                why = "TIMEOUT" if rc == "timeout" else (f"signal {-rc}" if isinstance(rc, int) and rc < 0 else f"exit {rc}")
                return "fail", f"{why} {codes(j)}"
            if kind in ("audio", "note"):
                s = json.load(open(of))
                silent = s.get("sample_peak") == 0  # silence reads as null loudness; that is not a NaN
                rms = s.get("rms_dbfs")
                # One silent channel (mono source) reads as null rms for that channel only; that is not a NaN.
                rms_ok = isinstance(rms, list) and any(isinstance(x, float) and math.isfinite(x) for x in rms) \
                    and all(x is None or (isinstance(x, float) and math.isfinite(x)) for x in rms)
                bad = [k for k in ("sample_peak", "dc_offset") + (() if silent or rms_ok else ("rms_dbfs",)) if has_bad(s.get(k))]
                if s.get("frames") and (s.get("sample_peak") is None or bad):
                    return "fail", "audio non-finite " + ",".join(bad or ["sample_peak"])
                if (s.get("sample_peak") or 0) > 1000:
                    return "fail", f"audio peak {s['sample_peak']:.0f}"
                res.append(json.dumps({k: s.get(k) for k in ("sample_peak", "rms_dbfs", "dc_offset")}))
            else:
                fr = os.path.join(d, f"f{rep}", "frame_00015.png")
                if not os.path.exists(fr):
                    return "fail", "no frame written"
                a = np.asarray(Image.open(fr).convert("RGBA"), dtype=np.float32)
                if np.isnan(a).any():
                    return "fail", "nan pixels"
                res.append(hashlib.md5(a.tobytes()).hexdigest())
        if res[0] != res[1]:
            names = [n for n in re_names(patch_text)]
            if any(n in known for n in names):
                return "pass", "known-nondeterministic"
            return "fail", "nondeterministic"
        return "pass", ""


def label_of(spec):
    return spec.get("label") or ">".join(spec["names"])


def shrink_candidates(types, spec):
    """Simpler versions of a failing patch, simplest first. Linear specs: the shortest prefixes, as before."""
    if "plan" not in spec:
        for k in range(2, len(spec["names"])):
            yield dict(spec, names=spec["names"][:k], sets=[x for x in spec["sets"] if x[0] < k])
        return
    plan = spec["plan"]
    if spec["mods"]:
        yield respec(types, spec, mods=[])
    if any(st[0] == "split" for st in plan):
        lin = []
        for st in plan:
            lin += [("node", n) for n in flatten(st[1][0])] if st[0] == "split" else [st]
        if len(flatten(lin)) >= 2:
            yield respec(types, spec, plan=lin, mods=[])
    for k in range(2, len(plan)):
        yield respec(types, spec, plan=plan[:k], mods=[])


def re_names(text):
    return [ln.split(" ", 3)[3] for ln in text.splitlines() if ln.startswith("node ") and len(ln.split(" ", 3)) == 4]


def has_bad(v):
    if v is None:
        return True
    if isinstance(v, (list, tuple)):
        return any(has_bad(x) for x in v)
    return isinstance(v, float) and not math.isfinite(v)


def codes(j):
    return ",".join(e.get("code", "?") for e in (j or {}).get("errors", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=os.path.join(ROOT, "build/Infinite.app/Contents/MacOS/Infinite"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build/chainfuzz"))
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--replay")
    ap.add_argument("--shape", choices=["linear", "graph"], default="graph",
                    help="linear: the original A>B>C chains (seed 7 reproduces the old set); graph: split, merge, modulators")
    ap.add_argument("--dry", action="store_true", help="only generate and --validate; print each chain")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "fail"), exist_ok=True)

    types = load_types(a.bin, a.out)
    gen, runner, known = Gen(types), Runner(a.bin, a.out, a.timeout), known_nondeterministic()
    tsv = os.path.join(a.out, "results.tsv")
    done = {ln.split("\t")[0] for ln in open(tsv)} if os.path.exists(tsv) else set()
    log = open(tsv, "a")

    jobs = []
    if a.replay:
        names = [n.strip() for n in a.replay.split(">")]
        jobs.append(("replay", gen.spec(random.Random(a.seed), names)))
    else:
        for i in range(a.n):
            if a.shape == "graph":
                rnd = random.Random(f"g{a.seed}:{i}")
                sp = gen.graph_spec(rnd)
                if len(sp["names"]) >= 2:
                    jobs.append((f"g{a.seed}-{i}", sp))
                continue
            rnd = random.Random(f"{a.seed}:{i}")
            names = gen.chain(rnd, rnd.choice([2, 2, 3, 3, 4]))
            if len(names) >= 2:
                jobs.append((f"s{a.seed}-{i}", gen.spec(rnd, names)))

    counts, fails = {"pass": 0, "refused": 0, "fail": 0}, []
    for jid, spec in jobs:
        if jid in done:
            continue
        builder = build_graph if "plan" in spec else build
        text, kind, ids = builder(types, spec)
        if a.dry:
            pf = os.path.join(a.out, "dry.inf")
            open(pf, "w").write(text)
            rc, j = runner.run(["--validate", pf])
            status, detail = ("pass", "") if rc == 0 else ("refused" if rc == 3 else "fail", f"rc={rc} {codes(j)}")
            print(f"{jid:12s} {status:8s} {spec.get('label') or '>'.join(spec['names'])}  mods={len(spec.get('mods', []))} {detail}", flush=True)
            counts[status] += 1
            continue
        status, detail = runner.execute(text, kind, spec["sets"], ids, jid, known)
        if status == "fail":  # shrink: drop modulators, collapse splits, then the shortest failing prefix
            for sub in shrink_candidates(types, spec):
                t2, k2, i2 = builder(types, sub)
                s2, d2 = runner.execute(t2, k2, sub["sets"], i2, jid + "-min", known)
                if s2 == "fail":
                    spec, text, status, detail = sub, t2, s2, d2
                    break
            open(os.path.join(a.out, "fail", jid + ".inf"), "w").write(text)
            fails.append((jid, label_of(spec), detail, spec))
        counts[status] += 1
        log.write("\t".join([jid, status, label_of(spec), json.dumps(spec["extras"]), json.dumps(spec["sets"]), detail]) + "\n")
        log.flush()
        print(f"{jid:12s} {status:8s} {label_of(spec)}  {detail}", flush=True)

    print(f"\nchains: {sum(counts.values())}  pass {counts['pass']}  refused {counts['refused']}  FAIL {counts['fail']}")
    for jid, chain, detail, spec in fails:
        print(f"  FAIL {jid}: {chain}  [{detail}] extras={spec['extras']} sets={spec['sets']}  -> {a.out}/fail/{jid}.inf")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
