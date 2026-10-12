#!/usr/bin/env python3
"""re-survey capability_map: what each app lets a script reach, from its official public API reference.

Sources (public documentation only; no app code, no decompiling):
  bitwig  the Controller API Javadoc that ships in Bitwig Studio.app (Resources/Documentation)
  live    Ableton's Live Object Model reference (docs.cycling74.com/apiref/lom)
  td      TouchDesigner's Python class reference (docs.derivative.ca, every *_Class page)
  logic   Logic Pro's Scripter guide pages (support.apple.com; MIDI-effect scripting only)
  infinite Infinite's own scripting surface: RPC methods (src/app/graph/Rpc.cpp) and headless CLI flags

Every member (method, property, child, function) is sorted into one capability domain (transport, tracks
and mixer, clips and scenes, devices, parameters, modulation, notes/MIDI, browser, view/UI, project,
hardware, visual/3D, audio data, timing) by keywords over its class and name. The report gives a
domain x app matrix of member counts, then per domain the members each app has, so "can a script in X
reach Y" is one lookup. Counts compare surfaces, not quality: Live lists properties, Bitwig observers.

Usage:
  python3 tools/re-survey/capability_map.py run [bitwig live td logic infinite] [--out t.md] [--refresh]
  python3 tools/re-survey/capability_map.py --self-test
Fetched pages are cached in ~/re-output/capability-map/cache (--refresh refetches); results JSON next to it.
Exit: 0 ok, 1 a source failed / self-test failed, 2 usage error.
"""

import argparse
import collections
import glob
import html
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(RE_OUTPUT, "capability-map", "cache")
BITWIG_DOCS = "/Applications/Bitwig Studio.app/Contents/Resources/Documentation/control-surface/api"
LOM = "https://docs.cycling74.com/apiref/lom/"
TD = "https://docs.derivative.ca/"
LOGIC_PAGES = [
    "use-the-scripter-midi-plug-in-lgce728c68f6", "midi-processing-functions-overview-lgce19021147",
    "handlemidi-function-lgce12088271", "processmidi-function-lgce225e4d89",
    "use-the-javascript-event-object-lgce0d0efc5a", "create-scripter-controls-lgce9f7063b5",
]
SOURCES = ["bitwig", "live", "td", "logic", "infinite"]

# First match wins, so the specific domains come before the broad ones.
DOMAINS = [
    ("modulation", r"modulat|lfo\b|envelope|macro|automation"),
    ("notes / MIDI", r"note|midi|velocity|pitch|step|drum|arpegg|chord|scale|tuning"),
    ("transport", r"transport|play|stop|tempo|metronome|loop|record|punch|count_?in|song_?time|position|beat|bpm"),
    ("clips / scenes", r"clip|scene|slot|launch|take"),
    ("arrangement", r"arrang|cue|marker|timeline|sequence|timecode"),
    ("tracks / mixer", r"track|channel|mixer|send|return|volume|pan|mute|solo|arm|crossfad|meter|group"),
    ("devices / nodes", r"device|chain|rack|plugin|layer|node|\bop\b|operator|comp\b|instrument|effect"),
    ("parameters", r"param|remote_?control|\bpar\b|value|knob|range"),
    ("browser / presets", r"browser|preset|librar|file|sample|vfs|import"),
    ("visual / 3D", r"top\b|sop\b|pop\b|mat\b|render|texture|image|camera|light|geometry|mesh|prim|point|vertex|shader|color|bezier|body|actor"),
    ("audio data", r"chop\b|audio|channel_?data|waveform|spectrum|warp"),
    ("hardware / IO", r"hardware|surface|controller|usb|port|osc\b|dongle|peer|monitor|display|connection"),
    ("timing / groove", r"groove|quantiz|swing|time_?signature|clock|absTime|frame"),
    ("view / UI", r"view|pane|window|panel|\bui\b|editor|popup|select|focus|zoom|scroll|screenshot|visible"),
    ("project / app", r"project|application|document|save|load|undo|redo|preferences|license|app\b|sysinfo|patch|validate|explain|describe"),
]


def domain_of(cls, name):
    for text in (name, cls):
        t = re.sub(r"([a-z])([A-Z])", r"\1_\2", text).lower()
        for d, rx in DOMAINS:
            if re.search(rx, t):
                return d
    return "other"


def fetch(url, key, refresh=False):
    path = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9._-]+", "_", key))
    if os.path.exists(path) and not refresh:
        with open(path, encoding="utf-8") as f:
            return f.read()
    ensure_dir(CACHE)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (re-survey capability_map)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    time.sleep(0.3)  # be polite to the doc servers
    return text


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def first_sentence(s, n=140):
    s = re.sub(r"\s+", " ", strip(s))
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m else s
    return s[:n]


# ---------------------------------------------------------------- sources -> [(class, member, kind, note)]

def src_bitwig(refresh=False):
    out = []
    for p in sorted(glob.glob(os.path.join(BITWIG_DOCS, "com/bitwig/extension/**/*.html"), recursive=True)):
        b = os.path.basename(p)
        if b.startswith(("package-", "class-use")) or "/class-use/" in p:
            continue
        s = open(p, encoding="utf-8", errors="replace").read()
        h = re.search(r'<h1[^>]*class="title"[^>]*>\s*(Interface|Class|Enum Class|Enum|Annotation[^ ]*)\s+([^<]+)', s)
        if not h:
            continue
        cls = h.group(2).strip()
        rows = re.findall(r'class="col-second[^"]*method-summary[^"]*"><code><a href="[^"]*" class="member-name-link">([A-Za-z0-9_]+)</a>'
                          r'.*?<div class="col-last[^"]*">(.*?)</div>\s*(?=<div class="col-first|</div>\s*</div>|$)', s, re.S)
        seen = set()
        for name, desc in rows:
            if name in seen:
                continue
            seen.add(name)
            out.append((cls, name, "method", first_sentence(desc)))
    return out


def src_live(refresh=False):
    idx = fetch(LOM, "lom_index.html", refresh)
    pages = sorted(set(re.findall(r'href="/apiref/lom/([a-z_]+)/"', idx)))
    out = []
    for pg in pages:
        s = fetch(LOM + pg + "/", "lom_" + pg + ".html", refresh)
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
        cls = strip(h1.group(1)) if h1 else pg
        section = None
        for lvl, body in re.findall(r"<h([23])[^>]*>(.*?)</h\1>", s, re.S):
            t = strip(body)
            if lvl == "2":
                section = t.lower()
                continue
            if section in ("children", "properties", "functions"):
                name = t.split()[0] if t else ""
                if re.match(r"^[a-z_][a-z0-9_]*$", name):
                    out.append((cls, name, {"children": "child", "properties": "property", "functions": "function"}[section],
                                " ".join(t.split()[1:])[:60]))
    return out


def src_td(refresh=False):
    idx = fetch(TD + "Python_Classes_and_Modules", "td_index.html", refresh)
    pages = sorted(set(re.findall(r'href="/([A-Za-z0-9_]+_Class)"', idx)))
    out = []
    for pg in pages:
        s = fetch(TD + pg, "td_" + pg + ".html", refresh)
        cls = pg[:-6]
        mi = s.find('id="Methods"')
        for m in re.finditer(r'<p><code class="python">([^<]+)</code>\s*(?:&#8594;|→)\s*<code class="return">(.*?)</code>', s):
            sig = html.unescape(m.group(1)).strip()
            name = re.match(r"[A-Za-z_][A-Za-z0-9_.]*", sig)
            if not name:
                continue
            kind = "method" if (mi >= 0 and m.start() > mi) or "(" in sig else "member"
            out.append((cls, name.group(0).split(".")[-1], kind, strip(m.group(2))[:40]))
    return out


def src_logic(refresh=False):
    out, seen = [], set()
    for pg in LOGIC_PAGES:
        s = fetch("https://support.apple.com/guide/logicpro/%s/mac" % pg, "logic_" + pg + ".html", refresh)
        body = s[s.find("<main"):] if "<main" in s else s
        for c in re.findall(r"<code[^>]*>(.*?)</code>", body, re.S):
            for ident in re.findall(r"\b([A-Z][A-Za-z]+(?:\.[a-z][A-Za-z]+)?|[a-z]+[A-Z][A-Za-z]+)\b", strip(c)):
                if ident not in seen and len(ident) > 3:
                    seen.add(ident)
                    cls, _, name = ident.rpartition(".")
                    out.append((cls or "Scripter", name or ident, "api", pg.split("-lgc")[0]))
    return out


def src_infinite(refresh=False):
    out = []
    rpc = open(os.path.join(ROOT, "src/app/graph/Rpc.cpp"), encoding="utf-8").read()
    for m in sorted(set(re.findall(r'method == "([a-z_]+)"', rpc))):
        out.append(("RPC", m, "method", ""))
    flags = set()
    for p in glob.glob(os.path.join(ROOT, "src/**/*.cpp"), recursive=True):
        if "Headless" in p or p.endswith("main.cpp"):
            flags |= set(re.findall(r'"(--[a-z][a-z0-9-]+)"', open(p, encoding="utf-8", errors="replace").read()))
    for f in sorted(flags):
        out.append(("CLI", f.lstrip("-").replace("-", "_"), "flag", ""))
    return out


FETCHERS = {"bitwig": src_bitwig, "live": src_live, "td": src_td, "logic": src_logic, "infinite": src_infinite}
LABEL = {"bitwig": "Bitwig", "live": "Live (LOM)", "td": "TouchDesigner", "logic": "Logic Scripter", "infinite": "Infinite"}


# ---------------------------------------------------------------- report

def classify(rows):
    return [{"class": c, "name": n, "kind": k, "note": note, "domain": domain_of(c, n)} for c, n, k, note in rows]


def report(data, errors):
    apps = [a for a in SOURCES if a in data]
    L = ["# Capability map (official scripting APIs)", "",
         "Generated by `tools/re-survey/capability_map.py` from public API references. A member is a method, "
         "property, child or function a script can reach; domains are keyword-sorted, so treat counts as a "
         "shape, not a score.", ""]
    rows = [("Classes",) + tuple(str(len({m["class"] for m in data[a]})) for a in apps),
            ("Members",) + tuple(str(len(data[a])) for a in apps)]
    dom_names = [d for d, _ in DOMAINS] + ["other"]
    cnt = {a: collections.Counter(m["domain"] for m in data[a]) for a in apps}
    for d in dom_names:
        rows.append((d,) + tuple(str(cnt[a][d]) if cnt[a][d] else "·" for a in apps))
    L += [md_table(["Domain"] + [LABEL[a] for a in apps], rows), ""]
    for a, e in errors.items():
        L.append("- %s FAILED: %s" % (LABEL[a], e))
    L.append("")
    for d in dom_names:
        L += ["## %s" % d, ""]
        for a in apps:
            ms = [m for m in data[a] if m["domain"] == d]
            if not ms:
                continue
            by = collections.defaultdict(list)
            for m in ms:
                by[m["class"]].append(m["name"])
            parts = ["**%s** %s" % (c, ", ".join(sorted(set(n))[:25]) + (" …" if len(set(n)) > 25 else ""))
                     for c, n in sorted(by.items(), key=lambda kv: -len(kv[1]))[:12]]
            L.append("- %s (%d): %s" % (LABEL[a], len(ms), "; ".join(parts)))
        L.append("")
    return "\n".join(L) + "\n"


def run(sources, refresh=False, log=print):
    data, errors = {}, {}
    for s in sources:
        try:
            data[s] = classify(FETCHERS[s](refresh))
            if not data[s]:
                raise RuntimeError("parsed 0 members (page layout changed?)")
            log("%-9s %5d members, %4d classes" % (s, len(data[s]), len({m["class"] for m in data[s]})))
        except Exception as e:  # one source must not stop the rest
            data.pop(s, None)
            errors[s] = str(e)
            log("%-9s FAILED: %s" % (s, e))
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "capability-map", time.strftime("%Y%m%d-%H%M%S")))
    with open(os.path.join(out_dir, "members.json"), "w") as f:
        json.dump(data, f, indent=0)
    return data, errors, out_dir


def self_test():
    t = SelfTest("capability_map")
    t.check(domain_of("Transport", "isPlaying") == "transport", "Transport.isPlaying -> transport")
    t.check(domain_of("Track", "volume") == "tracks / mixer", "Track.volume -> tracks / mixer")
    t.check(domain_of("Device", "createModulationSource") == "modulation", "modulation beats device")
    t.check(domain_of("Song", "tempo") == "transport", "Song.tempo -> transport")
    t.check(domain_of("ClipSlot", "fire") == "clips / scenes", "ClipSlot.fire -> clips")
    t.check(first_sentence("<b>Returns</b> the track. More text.") == "Returns the track.", "first sentence")
    inf = src_infinite()
    t.check(any(n == "set_param" for _, n, _, _ in inf), "Infinite RPC has set_param (%d members)" % len(inf))
    if os.path.isdir(BITWIG_DOCS):
        bw = src_bitwig()
        t.check(len(bw) > 1000 and any(c == "Transport" and n == "play" for c, n, _, _ in bw),
                "Bitwig Javadoc parses (%d methods, Transport.play present)" % len(bw))
    else:
        t.skip("Bitwig not installed")
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("run")
    rp.add_argument("sources", nargs="*", default=SOURCES)
    rp.add_argument("--out")
    rp.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd != "run":
        ap.print_usage(sys.stderr)
        return 2
    bad = [s for s in a.sources if s not in FETCHERS]
    if bad:
        print("usage: unknown source %s (have %s)" % (", ".join(bad), ", ".join(SOURCES)), file=sys.stderr)
        return 2
    data, errors, out_dir = run(a.sources or SOURCES, a.refresh, log=lambda m: print(m, file=sys.stderr))
    write_out(report(data, errors), a.out)
    print("members: %s" % os.path.join(out_dir, "members.json"), file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
