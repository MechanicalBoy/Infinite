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
            rnd = random.Random(f"{a.seed}:{i}")
            names = gen.chain(rnd, rnd.choice([2, 2, 3, 3, 4]))
            if len(names) >= 2:
                jobs.append((f"s{a.seed}-{i}", gen.spec(rnd, names)))

    counts, fails = {"pass": 0, "refused": 0, "fail": 0}, []
    for jid, spec in jobs:
        if jid in done:
            continue
        text, kind, ids = build(types, spec)
        status, detail = runner.execute(text, kind, spec["sets"], ids, jid, known)
        if status == "fail":  # shrink to the shortest failing prefix
            for k in range(2, len(spec["names"])):
                sub = dict(spec, names=spec["names"][:k], sets=[s for s in spec["sets"] if s[0] < k],
                           extras=spec["extras"], unc=spec["unc"])
                t2, k2, i2 = build(types, sub)
                s2, d2 = runner.execute(t2, k2, sub["sets"], i2, jid + "-min", known)
                if s2 == "fail":
                    spec, text, status, detail = sub, t2, s2, d2
                    break
            open(os.path.join(a.out, "fail", jid + ".inf"), "w").write(text)
            fails.append((jid, ">".join(spec["names"]), detail, spec))
        counts[status] += 1
        log.write("\t".join([jid, status, ">".join(spec["names"]), json.dumps(spec["extras"]), json.dumps(spec["sets"]), detail]) + "\n")
        log.flush()
        print(f"{jid:12s} {status:8s} {'>'.join(spec['names'])}  {detail}", flush=True)

    print(f"\nchains: {sum(counts.values())}  pass {counts['pass']}  refused {counts['refused']}  FAIL {counts['fail']}")
    for jid, chain, detail, spec in fails:
        print(f"  FAIL {jid}: {chain}  [{detail}] extras={spec['extras']} sets={spec['sets']}  -> {a.out}/fail/{jid}.inf")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
