#!/usr/bin/env python3
"""Stage user patches for the website library: clean them, render a frame, make a contact sheet.

What: for every patch listed in tools/website/community.json (or found by --scan), copies it to
      website/assets/community/, blanks every file path inside it (export/record/media paths carry
      usernames and do not exist on a visitor's machine), and renders one frame headless to a webp
      preview (a node diagram when the patch has no picture or needs a camera).
Why:  patches arrive with odd names and unknown origin; one manifest holds name, author and permission,
      and only entries with "ok": true are published.
Usage: python3 tools/website/community_patches.py --scan DIR [DIR..]   (adds new files to the manifest)
       python3 tools/website/community_patches.py                      (build every "ok" entry + index.json)
       python3 tools/website/community_patches.py --sheet              (contact sheet of all entries to /tmp/community_sheet.png)
       python3 tools/website/community_patches.py --smoke              (every published patch must open, play and show a picture)
Smoke: runs the staged copies in website/assets/community through --validate and --frame. A patch must load
      without errors, render its frame, and show a picture unless it needs a camera/mic or its manifest
      entry says "picture": false (sound-only patch). Pixels are never compared: patches may look different
      as Infinite evolves, they must only keep working.
Exit codes: 0 done, 1 a smoke check failed.
"""
import json, os, re, subprocess, sys, shutil, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from template_preview import render as diagram
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAN = os.path.join(os.path.dirname(__file__), "community.json")
OUT = os.path.join(ROOT, "website", "assets", "community")
BIN = os.path.join(ROOT, "build/Infinite.app/Contents/MacOS/Infinite")
HW = {"Camera", "Microphone", "Audio Input", "MIDI Input"}
PATHKEYS = re.compile(r"^(\s+s (?:path|[A-Za-z]*Path|[A-Za-z]*File|file)) .*$")

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def clean(src):
    out = []
    for l in open(src, encoding="utf-8", errors="replace").read().split("\n"):
        m = PATHKEYS.match(l)
        l = re.sub(r"/Users/[^/\s]+|[A-Za-z]:\\+Users\\+[^\\/\s]+", "~", l)
        out.append(m[1] + " " if m else l)
    return "\n".join(out)

def nodes(txt): return [re.match(r"node \d+ (\S+) (.+)", l).groups() for l in txt.split("\n") if re.match(r"node \d+ (\S+) (.+)", l)]

def load(): return json.load(open(MAN)) if os.path.exists(MAN) else {"items": []}

def scan(dirs):
    m = load(); have = {i["src"] for i in m["items"]}
    for d in dirs:
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if f.endswith((".inf", ".infinite")) and p not in have:
                m["items"].append({"src": p, "name": os.path.splitext(f)[0], "author": "", "description": "", "ok": False, "frame": 12})
    json.dump(m, open(MAN, "w"), indent=1, ensure_ascii=False); print(len(m["items"]), "entries")

def build(it, only_ok=True):
    ext = os.path.splitext(it["src"])[1]; sl = slug(it["name"]) or hashlib.md5(it["src"].encode()).hexdigest()[:8]
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, sl + ext); txt = clean(it["src"])
    open(dst, "w").write(txt)
    prev = os.path.join(OUT, sl + ".webp"); ns = nodes(txt)
    ok = False
    if not any(t in HW for _, t in ns):
        tmp = f"/tmp/cp_{sl}"; shutil.rmtree(tmp, ignore_errors=True)
        outs = [re.match(r"node (\d+)", l)[1] for l in txt.split("\n") if re.match(r"node \d+ Utility Output", l)]
        pick = ["--output", outs[0]] if len(outs) > 1 else []
        r = subprocess.run([BIN, "--frame", dst, str(it.get("frame", 12)), tmp + "/", "--timeout", "60", "--lenient"] + pick, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        fs = [f for f in os.listdir(tmp)] if os.path.isdir(tmp) else []
        if fs:
            im = Image.open(os.path.join(tmp, fs[0])).convert("RGB")
            if max(im.resize((24, 24)).convert("L").getextrema()) - min(im.resize((24, 24)).convert("L").getextrema()) > 12:
                s = min(im.size); l, t = (im.width - s) // 2, (im.height - s) // 2
                im.crop((l, t, l + s, t + s)).resize((640, 640), Image.LANCZOS).save(prev, quality=84); ok = True
    if not ok: diagram(dst, prev)
    it["_slug"], it["_ext"], it["_frame"], it["_nodes"] = sl, ext, ok, len(ns)
    return it

def sheet():
    its = [build(i) for i in load()["items"]]
    cols = 6; W = Image.new("RGB", (cols * 330, ((len(its) + cols - 1) // cols) * 330), "white")
    for k, i in enumerate(its):
        W.paste(Image.open(os.path.join(OUT, i["_slug"] + ".webp")).convert("RGB").resize((320, 320)), ((k % cols) * 330, (k // cols) * 330))
        print(k, i["name"], "frame" if i["_frame"] else "diagram", i["_nodes"], "nodes")
    W.save("/tmp/community_sheet.png")

def publish():
    items = []
    for i in load()["items"]:
        if not i.get("ok"): continue
        i = build(i); sl = i["_slug"]
        items.append({"id": sl, "name": i["name"], "category": "Community", "kind": "Patch", "author": i.get("author", ""),
                      "description": i["description"], "price": 0, "preview": f"assets/community/{sl}.webp",
                      "file": f"assets/community/{sl}{i['_ext']}", "nodes": []})
    json.dump({"version": 1, "items": items}, open(os.path.join(OUT, "index.json"), "w"), indent=1, ensure_ascii=False)
    print(len(items), "published")

def headless(args):
    """(exit code, last JSON line as dict) of one headless Infinite run."""
    try: r = subprocess.run([BIN] + args + ["--lenient"], capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired: return -1, {"errors": [{"code": "TIMEOUT", "message": "no result in 180 s"}]}
    try: j = json.loads(r.stdout.strip().split("\n")[-1])
    except ValueError: j = {"errors": [{"code": "CRASH" if r.returncode < 0 else "EXIT", "message": "exit %d" % r.returncode}]}
    return r.returncode, j

def errs(j): return "; ".join("%s %s" % (e.get("code", ""), e.get("message", "")) for e in j.get("errors", []))[:200]

def smoke_one(it, tmp):
    """(what was checked, '' or what failed) for one staged patch."""
    sl = slug(it["name"]); dst = os.path.join(OUT, sl + os.path.splitext(it["src"])[1])
    if not os.path.exists(dst): return "", "not staged (run community_patches.py)"
    txt = open(dst, encoding="utf-8", errors="replace").read(); ns = nodes(txt)
    rc, j = headless(["--validate", dst])
    if rc != 0: return "", "does not open: " + errs(j)
    if any(t in HW for _, t in ns): return "opens (needs a camera, mic or MIDI to play)", ""
    d = os.path.join(tmp, sl); os.makedirs(d, exist_ok=True)
    outs = [m[1] for m in (re.match(r"node (\d+) \S+ Output$", l) for l in txt.split("\n")) if m]
    if outs:
        fs = []
        for o in outs:  # a patch may keep spare Outputs with nothing wired in: one that renders is enough
            rc, j = headless(["--frame", dst, str(it.get("frame", 12)), d + "/", "--timeout", "60"] + (["--output", o] if len(outs) > 1 else []))
            fs = sorted(f for f in os.listdir(d) if f.endswith(".png"))
            if rc == 0 and fs: break
        if rc != 0 or not fs: return "", "does not play: " + (errs(j) or "no frame")
        if not it.get("picture", True): return "opens, plays", ""
        lo, hi = Image.open(os.path.join(d, fs[0])).convert("RGB").resize((24, 24)).convert("L").getextrema()
        return ("opens, plays, shows a picture", "") if hi - lo > 12 else ("", "blank picture")
    if any(t == "Audio Out" for _, t in ns):
        rc, j = headless(["--audio-summary", dst, os.path.join(d, "a.json"), "--duration", "2"])
        if rc != 0 and "E_HARDWARE_SOURCE" in errs(j): return "opens (needs a live source to play)", ""
        return ("opens, plays sound", "") if rc == 0 else ("", "does not play: " + errs(j))
    return "opens (no Output or Audio Out to play)", ""

def smoke():
    import tempfile
    its = [i for i in load()["items"] if i.get("ok")]; bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i in its:
            did, why = smoke_one(i, tmp); bad += bool(why)
            print("%s  %s: %s" % ("FAIL" if why else "ok  ", i["name"], why or did))
    print('QUALITY id=patch.community_fail subject="Infinite: community patches" value=%d' % bad)
    print("community smoke: %d patches, %d failed" % (len(its), bad))
    return 1 if bad else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--smoke"]: sys.exit(smoke())
    if a[:1] == ["--scan"]: scan(a[1:])
    elif a == ["--sheet"]: sheet()
    else: publish()
