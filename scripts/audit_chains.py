#!/usr/bin/env python3
"""Chain audit for the geometry nodes.

audit_dimming.py and GEOAUDIT KINDS test one node at a time. This builds real graphs of 2 to 4
geometry nodes through the control server and reads what each stage hands downstream
(`geometry_stats`): a mesh, points, a curve. It looks for the awkward cases that appear because
geometry can change kind mid-graph (mesh to points, curve to points, instance on points, join, ...).

Modes
  --pairs     every (source, A, B) with sources of three different kinds (mesh, points, curve)
  --random N  N seeded random chains of length 2..4 (the seed is printed; a failing chain replays with --replay)
  --replay "Sphere>Join>Delete Selected"   run one chain by node type names

Failures (hard):  app crash or hang, non-finite numbers, indices out of range, a selection mask that
                  does not match the triangle count, non-finite points or curve data.
Drops (reported): a stage that had content in and has none out and gives no cook warning.

Output: JSON with every failing chain, shortened to the first failing prefix.
"""
import argparse, itertools, json, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import node_screenshot as ns

SKIP = {"Output", "Comment", "Group", "Null", "Viewport", "Render 3D", "Model 3D", "Group 3D", "Null 3D", "Camera",
        "Light", "HDRI", "Projection", "Cloth", "Particle System"}
BAD_KEYS = ("nonFinite", "badIndex", "maskMismatch", "pointsBad", "curveBad")


class Fuzz:
    def __init__(self, own=True):
        self.proc = ns.launch_app("build/Infinite.app") if own else None
        ns.wait_for_token_and_port(7777)
        self.connect()
        self.cats = self.c.call("list_node_types")
        self.cat = {t: cat for cat, ts in self.cats.items() for t in ts}
        self.desc = {}
        self.sources, self.ops = [], []
        for t in sorted(self.cat):
            if t in SKIP:
                continue
            d = self.c.call("describe", type=t)
            if d.get("hardwareDriven") or not d["outputs"] or d["outputs"][0]["kind"] != "geometry":
                continue
            self.desc[t] = d
            slots = [i["slot"] for i in d["inputs"] if i["kind"] == "geometry"]
            (self.ops if slots else self.sources).append(t)

    def connect(self):
        self.c = ns.RpcClient("127.0.0.1", 7777, open(ns.TOKEN_PATH).read().strip())
        self.c.sock.settimeout(40)

    def restart(self):
        try:
            self.c.close()
        except Exception:
            pass
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            time.sleep(1.0)
            self.proc = ns.launch_app("build/Infinite.app")
            ns.wait_for_token_and_port(7777)
            time.sleep(2.0)
            self.connect()

    def make(self, typ, x):
        return self.c.call("create_node", typeName=typ, category=self.cat[typ], x=x, y=0)["index"]

    def run_chain(self, names, rnd=None):
        """Returns None when clean, else a dict describing the first failure."""
        c = self.c
        stage = "build"
        try:
            c.call("new_patch")
            prev = None
            last_kind = None
            for depth, typ in enumerate(names):
                stage = typ
                idx = self.make(typ, depth * 250)
                if prev is not None:
                    slots = [i["slot"] for i in self.desc[typ]["inputs"] if i["kind"] == "geometry"]
                    if not slots:
                        return None
                    main = slots[0] if rnd is None else rnd.choice(slots)
                    try:
                        c.call("connect", srcIndex=prev, srcOutput=0, dstIndex=idx, dstSlot=main)
                    except RuntimeError:
                        return None
                    for s in slots:
                        if s != main:
                            src = self.make(self.sources[0] if rnd is None else rnd.choice(self.sources), depth * 250 - 120)
                            try:
                                c.call("connect", srcIndex=src, srcOutput=0, dstIndex=idx, dstSlot=s)
                            except RuntimeError:
                                pass
                st = c.call("geometry_stats", index=idx)
                for k in BAD_KEYS:
                    if st.get(k, 0) > 0:
                        return {"stage": depth, "type": typ, "failure": k, "count": st[k]}
                kind = (st["verts"] > 0 and st["tris"] > 0, st["points"] > 0, st["curvePoints"] > 0)
                if last_kind is not None and any(last_kind) and not any(kind) and not st["warning"]:
                    return {"stage": depth, "type": typ, "failure": "drop", "count": 1, "soft": True}
                last_kind = kind
                prev = idx
        except (RuntimeError, OSError) as ex:
            msg = str(ex)
            hang = "timed out" in msg
            crashed = hang or "closed" in msg or "Broken pipe" in msg or isinstance(ex, (ConnectionError, BrokenPipeError))
            if crashed:
                self.restart()
                return {"stage": stage, "type": stage, "failure": "hang" if hang else "crash", "count": 1}
            return {"stage": stage, "type": stage, "failure": "rpc: " + msg[:120], "count": 1, "soft": True}
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", action="store_true")
    ap.add_argument("--random", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--replay", default="")
    ap.add_argument("--max-sources", type=int, default=3)
    ap.add_argument("--out", default="chain_audit.json")
    args = ap.parse_args()
    fz = Fuzz()
    print(f"{len(fz.sources)} sources, {len(fz.ops)} ops", flush=True)
    print("sources:", ", ".join(fz.sources), flush=True)
    print("ops:", ", ".join(fz.ops), flush=True)
    results, n = [], 0
    t0 = time.time()

    def record(chain, res):
        res["chain"] = " > ".join(chain)
        results.append(res)
        print(("SOFT " if res.get("soft") else "FAIL ") + res["chain"], "|", res["failure"], res["count"], flush=True)

    try:
        if args.replay:
            chain = [s.strip() for s in args.replay.split(">")]
            res = fz.run_chain(chain)
            print("clean" if res is None else res)
        if args.pairs:
            srcs = [s for s in ("Geometry", "Distribute Points", "Curve") if s in fz.sources][:args.max_sources]
            for src in srcs:
                for a in fz.ops:
                    for b in [None] + fz.ops:
                        chain = [src, a] + ([b] if b else [])
                        res = fz.run_chain(chain)
                        n += 1
                        if res:
                            record(chain, res)
                        if n % 200 == 0:
                            print(f"  {n} chains, {len(results)} failures, {time.time()-t0:.0f}s", flush=True)
        if args.random:
            rnd = random.Random(args.seed)
            print("random seed", args.seed, flush=True)
            for _ in range(args.random):
                chain = [rnd.choice(fz.sources)] + [rnd.choice(fz.ops) for _ in range(rnd.randint(1, 3))]
                cs = rnd.randrange(1 << 30)
                res = fz.run_chain(chain, rnd=random.Random(cs))
                n += 1
                if res:
                    res["chainSeed"] = cs
                    record(chain, res)
                if n % 200 == 0:
                    print(f"  {n} chains, {len(results)} failures, {time.time()-t0:.0f}s", flush=True)
    finally:
        json.dump({"chains": n, "failures": results}, open(args.out, "w"), indent=1)
        if fz.proc:
            fz.proc.terminate()
    hard = [r for r in results if not r.get("soft")]
    print(f"\n{n} chains run, {len(hard)} hard failures, {len(results) - len(hard)} drops/soft. wrote {args.out}")


if __name__ == "__main__":
    main()
