#!/usr/bin/env python3
"""Dimming audit: finds controls that are live but change nothing, and greyed controls that still
change the output, by driving a running Infinite over its control server.

    python3 scripts/audit_dimming.py [--types Blur,Bevel] [--category Effects] [--out report.json]

For every node type whose output is an image or geometry it:
  1. spawns the node on a fresh patch, wires plausible inputs, expands it;
  2. for the default state and for each alternative value of every mode / type / switch control
     (a "configuration"), reads how each control was drawn (live, greyed, hidden) from the
     param_ui_state RPC;
  3. changes each control to a few other values and compares a hash of the node's picture
     (geometry is hashed through a Render 3D node).
A control that was drawn live whose every change left the picture identical is "inert but live"
and should be greyed in that configuration. A control that was greyed or hidden whose change did
alter the picture is "dimmed but active". An animated node (the hash differs between two reads)
is reported and skipped. Audio, note and modulator nodes are listed as uncovered.

Triage the results by hand: a control that needs an input or time you did not provide can read as
inert. Exits 0 always; this is a finder, not a gate.
"""
import argparse, json, math, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import node_screenshot as ns

CAP_CONFIGS = 16
EXCITED = 3
FEEDERS = ["Ramp", "Circle", "Star", "Cross"]
SKIP_TYPES = {"Output", "Comment", "Group", "Null", "Viewport", "Syphon In", "NDI In", "Syphon Out", "NDI Out",
              "Video In", "Video", "Audio In", "Plugin", "Render 3D", "Model 3D", "Group 3D", "Null 3D", "Camera",
              "Light", "HDRI", "Projection", "Image Source", "Slideshow", "Texture"}


class Audit:
    def __init__(self, c):
        self.c = c

    audio = False

    def hash(self, idx):
        if self.audio:
            r = self.c.call("audio_hash", seconds=0.4)
            # Synth phases are not reset between renders, so compare coarse features (log buckets of
            # level, brightness, pitch, release tail) rather than the exact samples.
            def q(v):
                return -99 if v <= 1e-6 else round(math.log(v) * 10)
            return f"{q(r['rms'])}/{q(r['peak'])}/{q(r['lowRms'])}/{q(r['zcr'] + 1)}/{q(r['tailRms'])}"
        return self.c.call("output_hash", index=idx)["hash"]

    def state(self, idx):
        return self.c.call("param_ui_state", index=idx)

    def setp(self, idx, key, val):
        # The control server replays the value as text; bool/int loaders reject "1.0", so send whole numbers as ints.
        if isinstance(val, float) and val == int(val):
            val = int(val)
        self.c.call("set_param", index=idx, name=key, value=val)

    def params(self, idx):
        return self.c.call("get_params", index=idx)

    def resolve_keys(self, idx, st):
        """Give every control a saved key: by address when the node exposed one, otherwise by changing
        each unmatched key and seeing which control's value moved."""
        controls = st["controls"]
        for k in st["unmatchedKeys"]:
            if all("key" in c for c in controls):
                break
            raw = self.params(idx)
            cur = None
            for rk, rv in raw.items():
                if rk.split(" ", 1)[-1] == k:
                    cur = (rk, rv)
            if cur is None:
                continue
            try:
                before = {c["paramIndex"]: c.get("value") for c in controls}
                v = float(cur[1])
                for nv in (v + 1.0, v - 1.0, 1.0 - v, v + 0.37, v - 0.37):
                    self.setp(idx, k, nv)
                    st2 = self.state(idx)
                    moved = [c2 for c2 in st2["controls"]
                             if "key" not in c2 and c2.get("value") != before.get(c2["paramIndex"])]
                    self.setp(idx, k, v)
                    for c2 in moved:
                        for c in controls:
                            if c["paramIndex"] == c2["paramIndex"] and "key" not in c:
                                c["key"] = k
                                c["kind"] = cur[0][0]
                    if moved:
                        break
            except Exception:
                try:
                    self.setp(idx, k, cur[1])
                except Exception:
                    pass
        self.state(idx)
        return controls

    def candidates(self, c):
        cur = c.get("value", 0.0)
        out = []
        if c["isBool"]:
            out = [1.0 - round(cur)]
        elif c["isEnum"] and c.get("options", 0) > 1:
            n = c["options"]
            picks = sorted(set([0, n - 1, n // 2, (n - 1) // 3] if n > 4 else range(n)))
            out = [float(i) for i in picks if abs(i - cur) > 0.5][:4]
        else:
            lo, hi = c["min"], c["max"]
            if not hi > lo:
                return []
            for f in (0.2, 0.8):
                v = lo + f * (hi - lo)
                if c.get("kind") == "i" or c.get("step", 0) >= 1.0:
                    v = float(round(v))
                if abs(v - cur) > 1e-6 * max(1.0, abs(hi - lo)):
                    out.append(v)
        return out


def restore(a, idx, cfg):
    if cfg is None:
        return
    if cfg[0] == "excite":
        for kk, vv in cfg[2].items():
            a.setp(idx, kk, vv)
    else:
        a.setp(idx, cfg[0], cfg[2])


def run_node(a, typ, category, kind, report):
    c = a.c
    c.call("new_patch")
    idx = c.call("create_node", typeName=typ, category=category, x=0, y=0)["index"]
    a.audio = kind == "audio"
    if a.audio:
        # Notes -> a source oscillator -> the node (or notes -> the node, for a synth) -> Audio Out.
        d = c.call("describe", type=typ)
        kb = c.call("create_node", typeName="Keyboard", category=ns.find_category(c, "Keyboard"), x=-900, y=0)["index"]
        for inp in d["inputs"]:
            if inp["kind"] == "note":
                c.call("connect", srcIndex=kb, srcOutput=0, dstIndex=idx, dstSlot=inp["slot"])
            elif inp["kind"] == "audio":
                osc = c.call("create_node", typeName="Oscillator", category=ns.find_category(c, "Oscillator"),
                             x=-600, y=200 * inp["slot"])["index"]
                for oi in c.call("describe", type="Oscillator")["inputs"]:
                    if oi["kind"] == "note":
                        c.call("connect", srcIndex=kb, srcOutput=0, dstIndex=osc, dstSlot=oi["slot"])
                c.call("connect", srcIndex=osc, srcOutput=0, dstIndex=idx, dstSlot=inp["slot"])
        out = c.call("create_node", typeName="Audio Out", category=ns.find_category(c, "Audio Out"), x=600, y=0)["index"]
        c.call("connect", srcIndex=idx, srcOutput=0, dstIndex=out, dstSlot=0)
        c.call("expand_node", index=idx)
        c.call("fit_view_node", index=idx)
        time.sleep(0.8)
        probe = idx
        return audit_core(a, typ, idx, probe, report)
    c.call("auto_wire_inputs", index=idx)
    # One different, still picture per image input: with the same feeder on every slot a Blend or a
    # Displace sees identical inputs and most of its controls read as inert.
    try:
        d = c.call("describe", type=typ)
        n_img = 0
        for inp in d["inputs"]:
            if inp["kind"] != "image":
                continue
            ft = FEEDERS[n_img % len(FEEDERS)]
            n_img += 1
            f = c.call("create_node", typeName=ft, category=ns.find_category(c, ft), x=-600, y=200 * n_img)["index"]
            try:
                c.call("connect", srcIndex=f, srcOutput=0, dstIndex=idx, dstSlot=inp["slot"])
            except Exception:
                g = c.call("get_graph")
                for lk in g.get("links", []):
                    if lk.get("dstIndex") == idx and lk.get("dstSlot") == inp["slot"]:
                        c.call("disconnect", linkId=lk["id"])
                c.call("connect", srcIndex=f, srcOutput=0, dstIndex=idx, dstSlot=inp["slot"])
    except Exception as ex:
        print("   (feeder wiring:", ex, ")")
    # Geometry inputs: feed what the slot is for. Curves for profile/path/curve slots, a point cloud for
    # points slots, otherwise a mesh that already carries a half selection (so "selection only" and
    # friends have something to act on). Each slot gets a different shape so joins and booleans see
    # distinct inputs.
    try:
        gslots = [i for i in d["inputs"] if i["kind"] == "geometry"]
        for n_geo, inp in enumerate(gslots):
            label = inp["label"].lower()
            if any(w in label for w in ("curve", "profile", "path")):
                f = c.call("create_node", typeName="Curve", category="3D", x=-600, y=-200 * (n_geo + 1))["index"]
                if n_geo:
                    c.call("set_param", index=f, name="twist", value=0.5 * n_geo)
            elif "point" in label:
                f = c.call("create_node", typeName="Distribute Points in Grid", category="3D", x=-600, y=-200 * (n_geo + 1))["index"]
            else:
                shape = ["Cube", "Sphere", "Torus", "Cone"][n_geo % 4]
                g = c.call("create_node", typeName="Geometry", category="3D", x=-900, y=-200 * (n_geo + 1))["index"]
                a.setp(g, "shape", float({"Cube": 1, "Sphere": 2, "Torus": 4, "Cone": 6}[shape]))
                if typ == "Select":
                    f = g
                else:
                    f = c.call("create_node", typeName="Select", category="3D", x=-600, y=-200 * (n_geo + 1))["index"]
                    c.call("connect", srcIndex=g, srcOutput=0, dstIndex=f, dstSlot=0)
                    a.setp(f, "selectMode", 4.0)
                    a.setp(f, "selectA", 0.5)
            try:
                c.call("connect", srcIndex=f, srcOutput=0, dstIndex=idx, dstSlot=inp["slot"])
            except Exception:
                g2 = c.call("get_graph")
                for lk in g2.get("links", []):
                    if lk.get("dstIndex") == idx and lk.get("dstSlot") == inp["slot"]:
                        c.call("disconnect", linkId=lk["id"])
                c.call("connect", srcIndex=f, srcOutput=0, dstIndex=idx, dstSlot=inp["slot"])
    except Exception as ex:
        print("   (geometry feeder wiring:", ex, ")")
    probe = idx
    if kind == "geometry":
        r3 = c.call("create_node", typeName="Render 3D", category="3D", x=400, y=0)["index"]
        c.call("connect", srcIndex=idx, srcOutput=0, dstIndex=r3, dstSlot=0)
        probe = r3
        if typ == "Select":
            # A selection is invisible in a render; delete the selected faces so it shows.
            dl = c.call("create_node", typeName="Delete Selected", category="3D", x=200, y=0)["index"]
            c.call("disconnect", linkId=[lk["id"] for lk in c.call("get_graph")["links"]
                                          if lk.get("srcIndex") == idx and lk.get("dstIndex") == r3][0])
            c.call("connect", srcIndex=idx, srcOutput=0, dstIndex=dl, dstSlot=0)
            c.call("connect", srcIndex=dl, srcOutput=0, dstIndex=r3, dstSlot=0)
    c.call("expand_node", index=idx)
    c.call("fit_view_node", index=idx)
    time.sleep(0.8)
    return audit_core(a, typ, idx, probe, report)


def audit_core(a, typ, idx, probe, report):
    st = a.state(idx)
    controls = a.resolve_keys(idx, st)
    keyed = [x for x in controls if "key" in x]
    entry = {"type": typ, "controls": len(controls), "keyed": len(keyed), "inert_live": [], "dimmed_active": [],
             "hidden_active": [], "animated": False, "unkeyed": [x["name"] for x in controls if "key" not in x]}
    h1, h2 = a.hash(probe), a.hash(probe)
    if h1 != h2:
        entry["animated"] = True
        report.append(entry)
        return

    namekey = {}
    for x in keyed:
        namekey[x["name"]] = None if x["name"] in namekey else x["key"]
    modes = [x for x in keyed if (x["isEnum"] or x["isBool"]) and not x["momentary"]]
    configs = [None]
    for m in modes:
        for v in a.candidates(m):
            configs.append((m["key"], v, m.get("value", 0.0)))
    configs = configs[:CAP_CONFIGS]
    # "Excited" states: every plain numeric control moved off its default, so a control that only
    # matters once another is non-zero (pivot after a rotation, say) gets a fair test.
    rnd = random.Random(7)
    numeric = [x for x in keyed if not x["isEnum"] and not x["isBool"] and not x["momentary"] and x["max"] > x["min"]]
    for r in range(EXCITED):
        configs.append(("excite", {x["key"]: x["min"] + rnd.uniform(0.3, 0.7) * (x["max"] - x["min"]) for x in numeric},
                        {x["key"]: x.get("value", 0.0) for x in numeric}))

    live_seen, live_changed = {}, {}
    dimmed_changed = {}
    for cfg in configs:
        if cfg is not None and cfg[0] == "excite":
            for kk, vv in cfg[1].items():
                a.setp(idx, kk, vv)
        elif cfg is not None:
            a.setp(idx, cfg[0], cfg[1])
        st = a.state(idx)
        ctl = st["controls"]
        base = a.hash(probe)
        if base != a.hash(probe):
            restore(a, idx, cfg)
            continue
        cfgname = "default" if cfg is None else (f"excited{configs.index(cfg)}" if cfg[0] == "excite" else f"{cfg[0]}={cfg[1]:g}")
        for x in ctl:
            key = x.get("key") or namekey.get(x["name"])
            if key is None or x["momentary"]:
                continue
            k = {"key": key}
            if cfg is not None and cfg[0] != "excite" and key == cfg[0]:
                continue
            cands = a.candidates(x)
            if not cands:
                continue
            old = x.get("value", 0.0)
            changed = False
            for v in cands:
                a.setp(idx, k["key"], v)
                if a.hash(probe) != base:
                    changed = True
                    break
            a.setp(idx, k["key"], old)
            if changed and a.hash(probe) != base:
                continue   # the output drifts on its own (a free-running phase), so this change proves nothing
            label = f"{x['name']} [{k['key']}]"
            if not x["disabled"] and not x["hidden"]:
                if not changed:
                    live_seen.setdefault(label, []).append(cfgname)
                else:
                    live_changed[label] = True
            elif changed:
                dimmed_changed.setdefault((label, "dimmed" if x["disabled"] else "hidden"), []).append(cfgname)
        restore(a, idx, cfg)
    for label, cfgs in live_seen.items():
        entry["inert_live"].append({"control": label, "configs": cfgs, "ever_live_effect": label in live_changed})
    for (label, how), cfgs in dimmed_changed.items():
        (entry["dimmed_active"] if how == "dimmed" else entry["hidden_active"]).append({"control": label, "configs": cfgs})
    report.append(entry)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", default="")
    ap.add_argument("--category", default="")
    ap.add_argument("--out", default="dimming_audit.json")
    args = ap.parse_args()
    own = not ns.already_running(7777)
    proc = ns.launch_app("build/Infinite.app") if own else None
    ns.wait_for_token_and_port(7777)
    c = ns.RpcClient("127.0.0.1", 7777, open(ns.TOKEN_PATH).read().strip())
    a = Audit(c)
    cats = c.call("list_node_types")
    want = set(t for t in args.types.split(",") if t)
    report, uncovered = [], []
    try:
        for cat, names in cats.items():
            if args.category and cat != args.category:
                continue
            for typ in names:
                if want and typ not in want:
                    continue
                if typ in SKIP_TYPES:
                    continue
                try:
                    d = c.call("describe", type=typ)
                    outs = d["outputs"]
                    kind = outs[0]["kind"] if outs else ""
                    if d.get("hardwareDriven") or kind not in ("image", "geometry", "audio"):
                        uncovered.append(f"{typ} ({kind or 'no output'})")
                        continue
                    t0 = time.time()
                    run_node(a, typ, cat, kind, report)
                    e = report[-1]
                    print(f"{typ:28s} {e['keyed']:3d}/{e['controls']:3d} keyed | inert-live {len(e['inert_live'])} "
                          f"dimmed-active {len(e['dimmed_active'])} {'ANIMATED' if e['animated'] else ''} "
                          f"({time.time()-t0:.1f}s)", flush=True)
                except Exception as ex:
                    print(f"{typ:28s} ERROR {ex}", flush=True)
                    report.append({"type": typ, "error": str(ex)})
    finally:
        json.dump({"report": report, "uncovered": uncovered}, open(args.out, "w"), indent=1)
        if proc:
            proc.terminate()
    print(f"\nwrote {args.out}; uncovered (audio/notes/modulators/other): {len(uncovered)}")


if __name__ == "__main__":
    main()
