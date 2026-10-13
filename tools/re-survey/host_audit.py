#!/usr/bin/env python3
"""re-survey host_audit: does every installed plugin load, run and stay sane in Infinite's host?

Block A of docs/plans/re-survey/coverage.md (plugin hosting + stability). For every AU and VST3 on the
machine, one short headless render through Infinite's own host, each in its own process:
  effects      1 kHz sine at -12 dBFS in, 2 s
  instruments  a C major chord (notes in), 2 s
  MIDI effects load only (no audio of their own)
Graded per plugin: crash (signal; the .ips culprit image is named), hang (timeout), fail (host error),
not-ready (never instantiated), then output checks: NaN/inf, silent, clipped, DC. Load time = wall time
minus the dry rig's wall time. Also, per format:
  VST3  Infinite's out-of-process scanner (`--vst3-scan-bundle`) per bundle: classes, time, crash/hang
  AU    Apple's own validator (`auval -v`, ships with macOS): pass/fail, time
and the AU vs VST3 build of the same product side by side, since an asymmetry there has always been a
host bug, not the format (plugin-host-hardening rule 4).

Usage:
  python3 tools/re-survey/host_audit.py run [--filter fabfilter] [--formats au,vst3] [--no-auval] [--timeout 90] [--out t.md]
  python3 tools/re-survey/host_audit.py --self-test
Results JSON in ~/re-output/host-audit/<stamp>/. Render WAVs are deleted. Nothing outside Infinite's own
host and macOS's auval touches the plugins; no plugin binary is read.
Exit: 0 every plugin ok, 1 a plugin failed / self-test failed, 2 usage error or no Infinite binary.
"""

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, RE_TMP, SelfTest, ensure_dir, infinite_bin, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402
import synth_probe as sp  # noqa: E402

SR = 48000
DUR = 2.0
CHORD = [(0.1, 48), (0.1, 60), (0.1, 64), (0.1, 67)]
EFFECT_TYPES = ("aufx", "aumf")
REPORTS = os.path.expanduser("~/Library/Logs/DiagnosticReports")


# ---------------------------------------------------------------- inventory

def vst3_bundles(roots=("/Library/Audio/Plug-Ins/VST3", os.path.expanduser("~/Library/Audio/Plug-Ins/VST3"))):
    """Every .vst3 bundle, including vendor subfolders (Kilohearts/...), as Infinite's scanner walks them."""
    out = []
    for r in roots:
        for dirpath, dirs, _files in os.walk(r):
            for d in list(dirs):
                if d.endswith(".vst3"):
                    out.append(os.path.join(dirpath, d))
                    dirs.remove(d)  # never walk inside a bundle
    return sorted(out)


def scan_vst3(binp, bundle, timeout):
    t0 = time.time()
    try:
        r = subprocess.run([binp, "--vst3-scan-bundle", bundle], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"bundle": bundle, "scan": "hang", "scan_s": timeout, "classes": []}
    rows = [l.split("\t") for l in r.stdout.splitlines() if l.startswith("vst3\t")]
    cls = [{"id": x[3], "name": x[1], "vendor": x[2], "instrument": x[5] == "1"} for x in rows if len(x) == 6]
    state = "crash" if r.returncode < 0 else ("ok" if cls else "no-classes")
    return {"bundle": bundle, "scan": state, "scan_s": time.time() - t0, "classes": cls, "rc": r.returncode}


def auval(t, timeout):
    _, typ, sub, manu = t.split(":")
    t0 = time.time()
    try:
        r = subprocess.run(["auval", "-v", typ, sub, manu], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"auval": "hang", "auval_s": timeout}
    ok = "AU VALIDATION SUCCEEDED" in r.stdout
    why = ""
    if r.returncode < 0:  # the validator itself died inside the plugin
        return {"auval": "crash", "auval_s": time.time() - t0, "auval_why": "auval killed by signal %d" % -r.returncode}
    if not ok:
        errs = [l.strip() for l in r.stdout.splitlines() if "ERROR" in l or "FATAL" in l]
        why = (errs[0] if errs else (r.stdout.strip().splitlines() or ["rc %d" % r.returncode])[-1])[:160]
    return {"auval": "pass" if ok else "fail", "auval_s": time.time() - t0, "auval_why": why}


def product_key(name):
    """'FabFilter: Pro-Q 4' and 'Pro-Q 4' -> 'proq4' (pairs an AU with its VST3 twin)."""
    n = name.split(":", 1)[-1].lower()
    return re.sub(r"[^a-z0-9]", "", n)


# ---------------------------------------------------------------- one load

def read_ips(p):
    """(pid, faulting-thread frames as (image, symbol), exception) from one .ips, or None."""
    try:
        d = json.loads(open(p).read().split("\n", 1)[1])
    except (OSError, ValueError, IndexError):
        return None
    th = d.get("threads", [{}])[d.get("faultingThread", 0)]
    imgs = d.get("usedImages", [])
    frames = [(imgs[f["imageIndex"]].get("name") if 0 <= f.get("imageIndex", -1) < len(imgs) else None, f.get("symbol"))
              for f in th.get("frames", [])]
    exc = d.get("exception", {})
    return d.get("pid"), frames, "%s %s" % (exc.get("type", ""), exc.get("signal", ""))


_SEEN_IPS = set()


def crash_culprit(since, pid, wait=8.0):
    """The .ips of this crash: written after `since`, never handed out before, and naming `pid`.
    ReportCrash writes it a moment after the process dies, so poll a few seconds. Matching on time alone gave the
    previous plugin's late report to the next crash (RC-20's report was blamed on ShaperBox).
    Returns (file, image of the top named frame, exception) or (None, None, None)."""
    t_end = time.time() + wait
    while True:
        for p in glob.glob(os.path.join(REPORTS, "Infinite*.ips")):
            if p in _SEEN_IPS or os.path.getmtime(p) < since - 1:
                continue
            r = read_ips(p)
            if r and r[0] == pid:
                _SEEN_IPS.add(p)
                img = next((n for n, _s in r[1] if n), None)
                return os.path.basename(p), img, r[2]
        if time.time() >= t_end:
            return None, None, None
        time.sleep(0.5)


def code_signature(bundle):
    """macOS's own verdict on the bundle's signature: valid, invalid (code modified after signing), unsigned."""
    if not bundle or bundle == "(system)" or not os.path.exists(bundle):
        return None
    r = subprocess.run(["codesign", "--verify", "--deep", "--strict", bundle], capture_output=True, text=True)
    if r.returncode != 0:
        return "unsigned" if "not signed" in r.stderr.lower() else "invalid"
    d = subprocess.run(["codesign", "-dv", "--verbose=2", bundle], capture_output=True, text=True).stderr
    who = re.search(r"^Authority=Developer ID Application: (.+)$", d, re.M)
    return "valid: " + who.group(1) if who else "valid"


def load_patch(target, wav):
    if target["instrument"]:
        return sp.patch_text(dict(target, settings={}))
    return pp.patch_text(dict(target, settings={}), wav, True)


def load_one(binp, target, wav, tmp, timeout):
    p = os.path.join(tmp, "audit.inf")
    with open(p, "w") as f:
        f.write(load_patch(target, wav))
    j, w = os.path.join(tmp, "summary.json"), os.path.join(tmp, "out.wav")
    cmd = [binp, "--audio-summary", p, j, "--duration", "%g" % DUR, "--sample-rate", str(SR), "--wav", w,
           "--plugin-params", "--lenient", "--timeout", str(timeout)]
    if target["instrument"]:
        ep, mp = sp.write_notes([(t, m, 0.8, 1.2, "chord") for t, m in CHORD], tmp)
        cmd += ["--notes", ep, "--note-map", mp]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=timeout + 30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return {"state": "hang", "wall_s": timeout + 30}
    r = subprocess.CompletedProcess(cmd, proc.returncode, out, err)
    wall = time.time() - t0
    res = {"wall_s": wall, "rc": r.returncode}
    if r.returncode < 0 or r.returncode > 128:
        ips, img, exc = crash_culprit(t0, proc.pid)
        res.update(state="crash", signal=-r.returncode if r.returncode < 0 else r.returncode - 128, ips=ips, culprit=img, exception=exc)
        return res
    st = {}
    for line in reversed(r.stdout.strip().splitlines()):
        try:
            st = json.loads(re.sub(r":(-?)(inf|nan)\b", ":null", line))
            break
        except ValueError:
            continue
    if not st.get("ok"):
        errs = st.get("errors") or [{"message": (r.stderr.strip().splitlines() or ["rc %d" % r.returncode])[-1]}]
        res.update(state="fail", why=str(errs[0].get("message"))[:160])
        return res
    plug = (st.get("plugins") or [{}])[0]
    res["params"] = plug.get("param_count")
    if not plug.get("ready"):
        res.update(state="not-ready", why=str(plug.get("error", ""))[:160])
        return res
    res.update(state="ok", **grade_audio(w, st.get("audio_summary") or {}, target))
    if os.path.exists(w):
        os.remove(w)
    return res


def grade_audio(wav, summ, target):
    flags = []
    try:
        x, _sr = pp.read_wav(wav)
    except Exception:
        x = None
    if x is not None and not np.all(np.isfinite(x)):
        flags.append("nan")
    peak = summ.get("sample_peak") or 0.0
    if target.get("midi_fx"):
        pass
    elif peak < 1e-5:
        flags.append("silent")
    if (summ.get("clipped_frames") or 0) > 0:
        flags.append("clipped")
    if max(abs(v) for v in (summ.get("dc_offset") or [0])) > 0.05:
        flags.append("dc")
    return {"peak_dbfs": 20 * math.log10(peak) if peak > 0 else None, "flags": flags}


# ---------------------------------------------------------------- run

def targets(binp, formats, flt, timeout, log):
    out, scans = [], []
    if "au" in formats:
        for a in pp.list_aus():
            if a["bundle"] == "(system)" or a["type"] not in ("aufx", "aumf", "aumu", "aumi"):
                continue
            short = a["name"].split(":", 1)[-1].strip()
            out.append({"kind": "au", "id": a["id"], "name": short, "vendor": a["name"].split(":", 1)[0] if ":" in a["name"] else "", "label": short + " (AU)", "bundle": a["bundle"],
                        "instrument": a["type"] in ("aumu", "aumi"), "midi_fx": a["type"] == "aumi", "type": a["type"]})
    if "vst3" in formats:
        for b in vst3_bundles():
            if flt and flt.lower() not in b.lower():
                continue
            s = scan_vst3(binp, b, timeout)
            scans.append(s)
            log("  scan %-40s %-10s %4.1f s  %d classes" % (os.path.basename(b)[:40], s["scan"], s["scan_s"], len(s["classes"])))
            for c in s["classes"]:
                out.append({"kind": "vst3", "id": c["id"], "name": c["name"], "label": c["name"] + " (VST3)", "bundle": b,
                            "instrument": c["instrument"], "midi_fx": False, "vendor": c["vendor"]})
    if flt:
        out = [t for t in out if flt.lower() in (t["name"] + t["bundle"]).lower()]
    return out, scans


def audit(formats=("au", "vst3"), flt=None, do_auval=True, timeout=90, log=print):
    binp = infinite_bin()
    if not binp:
        raise SystemExit(2)
    tmp = ensure_dir(os.path.join(RE_TMP, "host-audit"))
    wav = os.path.join(tmp, "sine.wav")
    n = int(SR * DUR)
    pp.write_wav24(wav, 10 ** (-12 / 20) * np.sin(2 * np.pi * 1000 * np.arange(n) / SR), SR)
    walls = []
    for _ in range(4):  # the first is cold (disk, dyld); the fastest warm run is the rig's own cost
        t0 = time.time()
        pp.render(binp, pp.patch_text({"kind": "dry"}, wav, True), os.path.join(tmp, "dry.wav"), SR, DUR, tmp)
        walls.append(time.time() - t0)
    base = min(walls[1:])
    log("dry rig: %.2f s wall (cold %.2f s)" % (base, walls[0]))
    tg, scans = targets(binp, formats, flt, timeout, log)
    rows = []
    for i, t in enumerate(tg):
        r = load_one(binp, t, wav, tmp, timeout)
        r["load_s"] = max(0.0, r.get("wall_s", 0) - base)
        if do_auval and t["kind"] == "au":
            r.update(auval(t["id"], timeout))
        r["signature"] = code_signature(t.get("bundle"))
        row = dict(t, **r)
        rows.append(row)
        log("  [%d/%d] %-34s %-9s %5.1f s %s%s" % (i + 1, len(tg), t["label"][:34], r["state"], r["load_s"],
                                                ",".join(r.get("flags", [])), ("  auval " + r["auval"]) if "auval" in r else ""))
    return {"base_s": base, "rows": mark_whose(rows), "scans": scans}


def mark_whose(rows):
    """Whose fault a crash is. It is the plugin's when there is evidence from outside Infinite: macOS rejects the
    bundle's signature, or Apple's own validator dies in the same product (the VST3 inherits its AU's verdict).
    Anything else stays ours until shown otherwise."""
    av = {product_key(r["name"]): r["auval"] for r in rows if r.get("auval")}
    for r in rows:
        if r["state"] != "crash":
            continue
        if r.get("signature") in ("invalid", "unsigned"):
            r["whose"] = "plugin: signature " + r["signature"]
        elif av.get(product_key(r["name"])) == "crash":
            r["whose"] = "plugin: auval crashes too"
        else:
            r["whose"] = "host?"
    return rows


def bad(r):
    if r.get("whose", "").startswith("plugin"):
        return False
    return r["state"] != "ok" or bool(set(r.get("flags", [])) - {"silent"} if r["instrument"] else r.get("flags"))


def to_markdown(res):
    rows = res["rows"]
    L = ["# Plugin host audit (Infinite's host, headless)", "",
         "Generated by `tools/re-survey/host_audit.py`. One process per plugin; effects get a 1 kHz sine, instruments a "
         "chord. Load = wall time minus the dry rig (%.2f s). VST3 loads include a full VST3 rescan (~0.7 s warm): a "
         "headless render never seeds the bundle-path cache from the saved plugin index, the app does at launch." % res["base_s"], ""]
    summ = []
    for kind in ("au", "vst3"):
        k = [r for r in rows if r["kind"] == kind]
        if not k:
            continue
        cnt = {s: sum(1 for r in k if r["state"] == s) for s in ("ok", "fail", "not-ready", "crash", "hang")}
        loads = sorted(r["load_s"] for r in k if r["state"] == "ok")
        summ.append((kind.upper(), len(k), cnt["ok"], cnt["fail"] + cnt["not-ready"], cnt["crash"], cnt["hang"],
                     sum(1 for r in k if "silent" in r.get("flags", []) and not r["midi_fx"]),
                     sum(1 for r in k if "nan" in r.get("flags", [])),
                     "%.2f / %.2f" % (loads[len(loads) // 2], loads[-1]) if loads else "-"))
    L += [md_table(["Format", "Plugins", "OK", "Failed", "Crashed", "Hung", "Silent", "NaN", "Load s median / max"], summ), ""]
    if res["scans"]:
        sc = res["scans"]
        L += ["VST3 scan (out of process, per bundle): %d bundles, %d ok, %d crashed, %d hung, %d with no classes; "
              "median %.2f s, slowest %s %.1f s." % (
                  len(sc), sum(s["scan"] == "ok" for s in sc), sum(s["scan"] == "crash" for s in sc),
                  sum(s["scan"] == "hang" for s in sc), sum(s["scan"] == "no-classes" for s in sc),
                  sorted(s["scan_s"] for s in sc)[len(sc) // 2],
                  os.path.basename(max(sc, key=lambda s: s["scan_s"])["bundle"]), max(s["scan_s"] for s in sc)), ""]
    probs = [r for r in rows if r["state"] != "ok" or r.get("flags")]
    if probs:
        L += ["## Problems", "", md_table(["Plugin", "Format", "State", "Flags", "Why / culprit", "Whose", "Signature", "Load s"],
                                          [(r["name"], r["kind"].upper(), r["state"], ",".join(r.get("flags", [])) or "-",
                                            (r.get("why") or " ".join(x for x in (r.get("culprit"), r.get("exception")) if x))[:90],
                                            r.get("whose") or "-", r.get("signature") or "-", "%.1f" % r["load_s"]) for r in probs]), ""]
    badsig = [r for r in rows if r.get("signature") in ("invalid", "unsigned")]
    L += ["Code signature (`codesign --verify --deep --strict`): %d of %d bundles invalid or unsigned%s. macOS kills a "
          "process that pages in modified signed code, so no host can load an invalid one." % (
              len(badsig), len(rows), (": " + ", ".join(sorted({r["name"] for r in badsig}))) if badsig else ""), ""]
    by = {}
    for r in rows:
        by.setdefault(product_key(r["name"]), {})[r["kind"]] = r
    asym = [(k, v["au"], v["vst3"]) for k, v in by.items() if "au" in v and "vst3" in v
            and (v["au"]["state"], tuple(v["au"].get("flags", []))) != (v["vst3"]["state"], tuple(v["vst3"].get("flags", [])))]
    pairs = sum(1 for v in by.values() if "au" in v and "vst3" in v)
    L += ["## AU vs VST3 of the same product", "",
          "%d products ship both; %d behave differently in Infinite (a difference has always been a host bug)." % (pairs, len(asym)), ""]
    if asym:
        L += [md_table(["Product", "AU", "VST3", "AU load s", "VST3 load s"],
                       [(a["name"], a["state"] + ("/" + ",".join(a["flags"]) if a.get("flags") else ""),
                         v["state"] + ("/" + ",".join(v["flags"]) if v.get("flags") else ""), "%.1f" % a["load_s"], "%.1f" % v["load_s"])
                        for _, a, v in asym]), ""]
    av = [r for r in rows if "auval" in r]
    if av:
        dis = [r for r in av if (r["auval"] == "pass") != (r["state"] == "ok")]
        L += ["## Apple's validator vs Infinite", "",
              "auval: %d pass, %d fail, %d hang; median %.1f s. Disagreements (auval pass but Infinite fails = ours to fix; "
              "auval fail but Infinite ok = we are lenient):" % (
                  sum(r["auval"] == "pass" for r in av), sum(r["auval"] in ("fail", "crash") for r in av), sum(r["auval"] == "hang" for r in av),
                  sorted(r["auval_s"] for r in av)[len(av) // 2]), ""]
        L += [md_table(["Plugin", "auval", "Infinite", "auval says"], [(r["name"], r["auval"], r["state"], r.get("auval_why", "")[:90]) for r in dis])
              if dis else "None.", ""]
    slow = sorted((r for r in rows if r["state"] == "ok"), key=lambda r: -r["load_s"])[:10]
    if slow:
        L += ["## Slowest loads", "", md_table(["Plugin", "Format", "Load s", "Params"],
                                               [(r["name"], r["kind"].upper(), "%.2f" % r["load_s"], r.get("params") or "-") for r in slow]), ""]
    return "\n".join(L) + "\n"


def self_test():
    t = SelfTest("host_audit")
    t.check(product_key("FabFilter: Pro-Q 4") == product_key("Pro-Q 4") == "proq4", "AU and VST3 names pair")
    t.check(product_key("Valhalla: ValhallaRoom") == product_key("ValhallaRoom"), "vendor prefix dropped")
    root = ensure_dir(os.path.join(RE_TMP, "host-audit-selftest"))
    for d in ("A.vst3/Contents", "Vendor/B.vst3/Contents", "Vendor/B.vst3/Contents/Nested.vst3"):
        ensure_dir(os.path.join(root, d))
    found = [os.path.relpath(b, root) for b in vst3_bundles((root,))]
    t.check(found == ["A.vst3", "Vendor/B.vst3"], "bundles in vendor folders, never inside a bundle (%s)" % found)
    flags = grade_audio("/nonexistent.wav", {"sample_peak": 0.0, "clipped_frames": 3, "dc_offset": [0.2, 0]}, {"midi_fx": False})
    t.check(flags["flags"] == ["silent", "clipped", "dc"], "silent, clipped and DC flagged (%s)" % flags["flags"])
    rep = os.path.join(root, "Infinite-x.ips")
    with open(rep, "w") as f:
        f.write('{"app_name":"Infinite"}\n' + json.dumps({"pid": 4242, "faultingThread": 0, "usedImages": [{"name": "Plug"}],
                "exception": {"type": "EXC_BAD_ACCESS", "signal": "SIGSEGV"},
                "threads": [{"frames": [{"imageIndex": 9}, {"imageIndex": 0, "symbol": "f"}]}]}))
    global REPORTS
    keep, REPORTS = REPORTS, root
    try:
        a = crash_culprit(0, 4141, wait=0)
        b = crash_culprit(0, 4242, wait=0)
        c = crash_culprit(0, 4242, wait=0)
    finally:
        REPORTS = keep
    t.check(a == (None, None, None), "a report for another pid is never blamed (%s)" % (a,))
    t.check(b == ("Infinite-x.ips", "Plug", "EXC_BAD_ACCESS SIGSEGV"), "report matched by pid, top named frame (%s)" % (b,))
    t.check(c == (None, None, None), "a report is handed out once (%s)" % (c,))
    t.check(code_signature("/System/Library/CoreServices/Finder.app") .startswith("valid"), "codesign verdict on a signed bundle")
    w = mark_whose([{"name": "Vendor: Fx", "state": "crash", "auval": "crash", "instrument": False},
                    {"name": "Fx", "state": "crash", "instrument": False},
                    {"name": "Cut", "state": "crash", "signature": "invalid", "instrument": False},
                    {"name": "Other", "state": "crash", "auval": "pass", "instrument": False}])
    t.check([bad(r) for r in w] == [False, False, False, True] and w[3]["whose"] == "host?",
            "a crash is the plugin's only with outside evidence: auval dies too (VST3 inherits it) or a bad signature (%s)" % [r["whose"] for r in w])
    binp = infinite_bin()
    if not binp:
        t.skip("no Infinite binary: the AUDelay load is not run")
    else:
        res = audit(formats=("au",), flt="__none__", do_auval=False, log=lambda m: None)
        t.check(res["rows"] == [] and res["base_s"] > 0, "dry rig renders, filter can exclude everything")
        tmp = ensure_dir(os.path.join(RE_TMP, "host-audit"))
        r = load_one(binp, {"kind": "au", "id": "au:aufx:dely:appl", "name": "Apple: AUDelay", "label": "AUDelay",
                            "instrument": False, "midi_fx": False}, os.path.join(tmp, "sine.wav"), tmp, 60)
        t.check(r["state"] == "ok" and not r["flags"], "Apple AUDelay loads clean (%s)" % {k: r.get(k) for k in ("state", "flags", "why")})
        a = auval("au:aufx:dely:appl", 120)
        t.check(a["auval"] == "pass", "auval passes AUDelay (%s)" % a)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("run")
    rp.add_argument("--filter")
    rp.add_argument("--formats", default="au,vst3")
    rp.add_argument("--no-auval", action="store_true")
    rp.add_argument("--timeout", type=int, default=90)
    rp.add_argument("--out")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd != "run":
        ap.print_usage(sys.stderr)
        return 2
    fm = tuple(x.strip() for x in a.formats.split(","))
    if not set(fm) <= {"au", "vst3"}:
        print("usage: --formats takes au, vst3", file=sys.stderr)
        return 2
    res = audit(fm, a.filter, not a.no_auval, a.timeout, log=lambda m: print(m, file=sys.stderr))
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "host-audit", time.strftime("%Y%m%d-%H%M%S")))
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    write_out(to_markdown(res), a.out)
    return 0 if not any(bad(r) for r in res["rows"]) else 1


if __name__ == "__main__":
    sys.exit(main())
