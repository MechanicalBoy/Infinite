#!/usr/bin/env python3
"""re-survey plugin_probe: measure a plugin (or an Infinite node) through Infinite's own host.

Black-box only: a test signal goes in, Infinite renders headless, we measure what comes out.
Nothing of the plugin is opened, read or decompiled. Every target is measured with the same
stimulus so rows are comparable, and the first row is always `dry` (Audio File -> Audio Out),
which is the measurement floor of the rig itself.

Stimulus (one WAV, generated at the run's sample rate, 24-bit):
  0.0 s silence (plugin load) | 1.0 s impulse 0.5 | 6.5 s 1 kHz -12 dBFS | 8.0 s 1 kHz -1 dBFS |
  9.5 s high sine (0.3125 * fs, 15 kHz at 48k) -6 dBFS | 11.0 s end
Measured: latency (onset/peak, samples), gain @1 kHz, THD and THD+N at -12/-1 dBFS, aliasing
(non-harmonic energy around the high sine), response flatness 63 Hz-16 kHz from the impulse,
-60 dB tail time, RT60 (Schroeder T20), L/R correlation, CPU (ms of render per second of audio,
from the slope of a short and a long render so load time cancels), and the parameter list as
Infinite's host sees it (address, name, the plugin's own range: what a setting must use).

Targets:
  dry                     the rig alone (always added first)
  au:aufx:dLay:oDin       an Audio Unit by id (ids: `plugin_probe.py list`)
  "Pro-L 2"               an AU by name substring (must match one effect)
  node:Reverb             an Infinite audio node by type name (Q3: ours vs a benchmark)
  vst3:<id> | "vst3 Pro-Q 4" | X.vst3   a VST3 effect by id or bundle name
  "Saturn 2@Drive=0.6,Mix=1"            settings after @: host parameter names (see `params`) or node keys
  --sweep Drive=0,0.25,0.5,1            every non-dry target once per value
  --sweep Drive=range:5                 5 even steps across each plugin's own range for that parameter

Usage:
  python3 tools/re-survey/plugin_probe.py list [--filter fabfilter]
  python3 tools/re-survey/plugin_probe.py run "Pro-Q 4" "Pro-L 2" node:EQ [--sr 48000] [--no-cpu] [--out t.md]
  python3 tools/re-survey/plugin_probe.py params "Saturn 2" [--filter drive]
  python3 tools/re-survey/plugin_probe.py run "Saturn 2" "vst3 Saturn 2" --sweep "Band 1 Drive=range:5" --no-cpu
  python3 tools/re-survey/plugin_probe.py --self-test
Results JSON: ~/re-output/plugin-probe/<stamp>/results.json. Render WAVs are deleted unless --keep.
Limits: Infinite's headless --wav is 16-bit, so THD/aliasing floors sit near -90 dB (the dry row
shows the real floor). Instruments (aumu) need notes and are not probed yet. A sweep adds a
per-target table: each measure at each value, so a control's effect reads as a curve.

Exit: 0 ok, 1 a target failed to render / self-test failed, 2 usage error or no Infinite binary.
"""

import argparse
import glob
import json
import os
import plistlib
import re
import shutil
import struct
import sys
import time
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, RE_TMP, SelfTest, ensure_dir, infinite_bin, md_table, run, write_out  # noqa: E402

IMP_T, IMP_AMP = 1.0, 0.5
IR_LEN_S = 5.0
SINES = [  # (name, start s, freq factor or Hz, dBFS)
    ("lo", 6.5, 1000.0, -12.0),
    ("hi", 8.0, 1000.0, -1.0),
    ("hf", 9.5, None, -6.0),  # None = 0.3125 * fs
]
SINE_LEN_S = 1.0
TOTAL_S = 11.0
BANDS = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]


# ---------------------------------------------------------------- stimulus + wav io

def hf_freq(sr):
    return round(0.3125 * sr / 10.0) * 10.0


def make_stimulus(sr):
    n = int(TOTAL_S * sr)
    x = np.zeros(n)
    x[int(IMP_T * sr)] = IMP_AMP
    fade = int(0.01 * sr)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fade))
    for _, t0, f, db in SINES:
        f = f or hf_freq(sr)
        m = int(SINE_LEN_S * sr)
        s = 10 ** (db / 20.0) * np.sin(2 * np.pi * f * np.arange(m) / sr)
        s[:fade] *= ramp
        s[-fade:] *= ramp[::-1]
        i = int(t0 * sr)
        x[i:i + m] = s
    return x


def write_wav24(path, mono, sr):
    v = np.clip(np.round(mono * 8388607.0), -8388608, 8388607).astype("<i4")
    st = np.repeat(v, 2)
    b = st.tobytes()
    raw = b"".join(b[i:i + 3] for i in range(0, len(b), 4))  # little-endian: drop the top byte
    w = wave.open(path, "wb")
    w.setnchannels(2)
    w.setsampwidth(3)
    w.setframerate(int(sr))
    w.writeframes(raw)
    w.close()


def read_wav(path):
    w = wave.open(path, "rb")
    ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    b = w.readframes(n)
    w.close()
    if sw == 2:
        a = np.frombuffer(b, "<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        u = np.frombuffer(b, np.uint8).reshape(-1, 3).astype(np.int32)
        v = u[:, 0] | (u[:, 1] << 8) | (u[:, 2] << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        a = v.astype(np.float64) / 8388608.0
    elif sw == 4:
        a = np.frombuffer(b, "<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError("unsupported sample width %d" % sw)
    return a.reshape(-1, ch), sr, sw * 8


# ---------------------------------------------------------------- analysis (pure numpy)

def bh4(n):
    k = np.arange(n) / (n - 1)
    return 0.35875 - 0.48829 * np.cos(2 * np.pi * k) + 0.14128 * np.cos(4 * np.pi * k) - 0.01168 * np.cos(6 * np.pi * k)


def tone_metrics(seg, sr, f0):
    """Fundamental power, THD (harmonics 2..10 below Nyquist), THD+N, non-harmonic (aliasing+noise)."""
    n = len(seg)
    p = np.abs(np.fft.rfft(seg * bh4(n))) ** 2
    k0 = f0 * n / sr
    w = 6

    def band(k):
        lo, hi = int(round(k)) - w, int(round(k)) + w + 1
        return p[max(lo, 0):min(hi, len(p))].sum()

    fund = band(k0)
    harm = 0.0
    mask = np.ones(len(p), bool)
    mask[:w + 4] = False  # DC
    for h in range(1, 11):
        kh = h * k0
        if kh >= len(p) - w - 1:
            break
        lo, hi = int(round(kh)) - w, int(round(kh)) + w + 1
        mask[max(lo, 0):hi] = False
        if h > 1:
            harm += band(kh)
    total = p[w + 4:].sum()
    nonharm = p[mask].sum()
    eps = 1e-30
    return {
        "fund_power": fund,
        "thd_db": 10 * np.log10((harm + eps) / (fund + eps)),
        "thdn_db": 10 * np.log10((max(total - fund, 0) + eps) / (fund + eps)),
        "nonharm_db": 10 * np.log10((nonharm + eps) / (fund + eps)),
    }


def latency(ir, thresh_db=-12.0):
    a = np.abs(ir)
    pk = a.max()
    if pk <= 0:
        return None, None
    onset = int(np.argmax(a >= pk * 10 ** (thresh_db / 20.0)))
    return onset, int(np.argmax(a))


def tail_seconds(ir, sr, floor_db=-60.0):
    a = np.abs(ir)
    pk = a.max()
    if pk <= 0:
        return None
    blk = max(1, int(0.01 * sr))
    nb = len(a) // blk
    env = a[:nb * blk].reshape(nb, blk).max(1)
    above = np.nonzero(env >= pk * 10 ** (floor_db / 20.0))[0]
    return (above[-1] + 1) * blk / sr if len(above) else 0.0


def rt60(ir, sr):
    """Schroeder backward integration, T20 fit (-5..-25 dB) x3. None if the decay is too short/noisy."""
    e = ir.astype(np.float64) ** 2
    start = int(np.argmax(np.abs(ir)))
    e = e[start:]
    if e.sum() <= 0:
        return None
    edc = np.cumsum(e[::-1])[::-1]
    edc_db = 10 * np.log10(edc / edc[0] + 1e-30)
    i5 = np.argmax(edc_db <= -5)
    i25 = np.argmax(edc_db <= -25)
    if i25 <= i5 or edc_db[i25] > -25 or i25 - i5 < int(0.005 * sr):
        return None
    t = np.arange(i5, i25) / sr
    slope = np.polyfit(t, edc_db[i5:i25], 1)[0]
    return -60.0 / slope if slope < 0 else None


def response(ir, sr, amp):
    n = 1 << int(np.ceil(np.log2(min(len(ir), int(1.4 * sr)))))
    seg = np.zeros(n)
    seg[:min(n, len(ir))] = ir[:n]
    h = np.abs(np.fft.rfft(seg)) / amp
    f = np.fft.rfftfreq(n, 1.0 / sr)
    out = {}
    for c in BANDS:
        if c * 2 ** (1 / 6.0) >= sr / 2:
            continue
        sel = (f >= c * 2 ** (-1 / 6.0)) & (f < c * 2 ** (1 / 6.0))
        if sel.any():
            out[c] = float(20 * np.log10(np.sqrt(np.mean(h[sel] ** 2)) + 1e-12))
    return out


def analyse(out, sr, stim):
    """Everything the table shows, from one stereo render of the stimulus."""
    L, R = out[:, 0], out[:, 1] if out.shape[1] > 1 else out[:, 0]
    mono = 0.5 * (L + R)
    i0 = int(IMP_T * sr)
    ir = mono[i0:i0 + int(IR_LEN_S * sr)]
    onset, peak = latency(ir)
    res = {"latency_onset": onset, "latency_peak": peak}
    res["ir_peak"] = float(np.abs(ir).max())
    res["tail_s"] = tail_seconds(ir, sr)
    res["rt60_s"] = rt60(ir, sr)
    res["response_db"] = response(ir, sr, IMP_AMP) if res["ir_peak"] > 0 else {}
    irl, irr = L[i0:i0 + int(IR_LEN_S * sr)], R[i0:i0 + int(IR_LEN_S * sr)]
    res["lr_corr"] = float(np.corrcoef(irl, irr)[0, 1]) if irl.std() > 0 and irr.std() > 0 else None
    shift = onset or 0
    for name, t0, f, db in SINES:
        f = f or hf_freq(sr)
        a = int((t0 + 0.2) * sr)
        b = int((t0 + SINE_LEN_S - 0.2) * sr)
        m_out = tone_metrics(mono[a + shift:b + shift], sr, f)
        m_in = tone_metrics(stim[a:b], sr, f)
        res[name] = {
            "freq": f, "dbfs": db,
            "gain_db": float(10 * np.log10((m_out["fund_power"] + 1e-30) / (m_in["fund_power"] + 1e-30))),
            "thd_db": float(m_out["thd_db"]), "thdn_db": float(m_out["thdn_db"]), "nonharm_db": float(m_out["nonharm_db"]),
        }
    res["peak"] = float(np.abs(out).max())
    res["nan"] = bool(not np.isfinite(out).all())
    return res


# ---------------------------------------------------------------- targets and rendering

def list_aus():
    roots = ["/Library/Audio/Plug-Ins/Components", os.path.expanduser("~/Library/Audio/Plug-Ins/Components")]
    out = []
    for r in roots:
        for comp in sorted(glob.glob(os.path.join(r, "*.component"))):
            try:
                with open(os.path.join(comp, "Contents", "Info.plist"), "rb") as f:
                    d = plistlib.load(f)
            except Exception:
                continue
            for c in d.get("AudioComponents", []) or []:
                out.append({"id": "au:%s:%s:%s" % (c.get("type"), c.get("subtype"), c.get("manufacturer")),
                            "name": c.get("name", ""), "type": c.get("type"), "bundle": comp})
    # Apple's own AUs live in the system, not in Components: keep the ones the self-test uses.
    out.append({"id": "au:aufx:dely:appl", "name": "Apple: AUDelay", "type": "aufx", "bundle": "(system)"})
    out.append({"id": "au:aufx:lmtr:appl", "name": "Apple: AUPeakLimiter", "type": "aufx", "bundle": "(system)"})
    return out


def split_settings(target):
    """'Saturn 2@Drive=60,Mix=100' -> ('Saturn 2', {'Drive': '60', 'Mix': '100'})."""
    name, _, rest = target.partition("@")
    settings = {}
    for kv in filter(None, (x.strip() for x in rest.split(","))):
        k, eq, v = kv.partition("=")
        if not eq or not k.strip():
            raise ValueError("bad setting '%s' in '%s' (want Name=value)" % (kv, target))
        settings[k.strip()] = v.strip()
    return name.strip(), settings


def list_vst3(folders=("/Library/Audio/Plug-Ins/VST3", os.path.expanduser("~/Library/Audio/Plug-Ins/VST3"))):
    out = []
    for f in folders:
        if os.path.isdir(f):
            out += [os.path.join(f, b) for b in sorted(os.listdir(f)) if b.endswith(".vst3")]
    return out


def vst3_classes(binp, bundle):
    """Effect classes in one bundle via Infinite's own out-of-process scanner (format, name, vendor, id, path, notes)."""
    rc, out, _ = run([binp, "--vst3-scan-bundle", bundle], timeout=60)
    rows = [l.split("\t") for l in out.splitlines() if l.startswith("vst3\t")]
    return [{"id": r[3], "name": r[1], "path": r[4], "notes": r[5] == "1"} for r in rows if len(r) == 6]


def resolve(target, aus):
    t, settings = split_settings(target)
    suffix = (" @ " + ", ".join("%s=%s" % kv for kv in settings.items())) if settings else ""
    if t == "dry":
        return {"kind": "dry", "label": "dry (rig floor)", "settings": {}}
    if t.startswith("node:"):
        return {"kind": "node", "type": t[5:], "label": t + suffix, "settings": settings}
    if t.startswith("vst3:") or t.lower().startswith("vst3 ") or t.lower().endswith(".vst3"):
        if t.startswith("vst3:"):
            return {"kind": "vst3", "id": t, "label": t + suffix, "name": t, "settings": settings}
        want = t[5:].strip() if t.lower().startswith("vst3 ") else os.path.basename(t)[:-5]
        binp = infinite_bin()
        hits = [b for b in list_vst3() if want.lower() in os.path.basename(b)[:-5].lower()]
        exact = [b for b in hits if os.path.basename(b)[:-5].lower() == want.lower()]
        hits = exact or hits
        if len(hits) != 1 or not binp:
            raise ValueError("'%s' matches %d VST3 bundles: %s" % (t, len(hits), ", ".join(map(os.path.basename, hits[:8])) or "none"))
        cls = [c for c in vst3_classes(binp, hits[0]) if not c["notes"]]
        if len(cls) != 1:
            raise ValueError("%s: %d effect classes in the bundle" % (hits[0], len(cls)))
        return {"kind": "vst3", "id": cls[0]["id"], "label": cls[0]["name"] + " (VST3)" + suffix, "name": cls[0]["name"],
                "settings": settings}
    if t.startswith("au:"):
        hit = [a for a in aus if a["id"] == t]
        name = hit[0]["name"] if hit else t
        return {"kind": "au", "id": t, "label": name + suffix, "name": name, "type": t.split(":")[1], "settings": settings}
    hits = [a for a in aus if t.lower() in a["name"].lower() and a["type"] in ("aufx", "aumf")]
    exact = [a for a in hits if a["name"].lower().endswith(t.lower())]
    if len(exact) == 1:
        hits = exact
    if len(hits) != 1:
        names = ", ".join("%s (%s)" % (a["name"], a["id"]) for a in hits[:8]) or "none"
        raise ValueError("'%s' matches %d effects: %s" % (t, len(hits), names))
    a = hits[0]
    return {"kind": "au", "id": a["id"], "label": a["name"] + suffix, "name": a["name"], "type": a["type"], "settings": settings}


def sweep_values(spec, lo=None, hi=None):
    """'0,0.5,1' -> those values; 'range:N' -> N even steps across lo..hi (the host range)."""
    if spec.startswith("range:"):
        n = int(spec[6:])
        if n < 2 or lo is None or hi is None:
            raise ValueError("range:N wants N >= 2 and a parameter with a host range")
        return ["%.6g" % (lo + (hi - lo) * i / (n - 1)) for i in range(n)]
    return [v.strip() for v in spec.split(",") if v.strip()]


def expand_sweep(targets, sweep, aus=None):
    """--sweep Name=v1,v2,... (or Name=range:N) -> each non-dry target once per value."""
    if not sweep:
        return list(targets)
    name, eq, vals = sweep.partition("=")
    name = name.strip()
    if not eq or not vals:
        raise ValueError("--sweep wants Name=v1,v2,... or Name=range:N")
    out = []
    for t in targets:
        if t.strip() == "dry":
            out.append(t)
            continue
        lo = hi = None
        if vals.startswith("range:"):
            r = resolve(t, aus if aus is not None else list_aus())
            if r["kind"] not in ("au", "vst3"):
                raise ValueError("%s: range:N needs a plugin (node keys have no host range); list the values" % t)
            p = find_param(r, name)
            lo, hi = p["min"], p["max"]
        for v in sweep_values(vals, lo, hi):
            out.append("%s%s%s=%s" % (t, "," if "@" in t else "@", name, v))
    return out


_HOST_PARAMS = {}


def host_params(target):
    """The plugin's parameters as Infinite's host sees them: one short --plugin-params render, cached.
    Ranges are the plugin's own units (auval prints display units: Saturn's Drive reads 0-100% but is 0-1)."""
    key = (target["kind"], target["id"])
    if key not in _HOST_PARAMS:
        binp = infinite_bin()
        tmp = ensure_dir(os.path.join(RE_TMP, "plugin-params"))
        bare = dict(target, settings={})
        st = render(binp, patch_text(bare, "", False), os.path.join(tmp, "p.wav"), 48000, 0.25, tmp, ["--plugin-params"])
        plugs = st.get("plugins") or []
        if not plugs or not plugs[0].get("ready"):
            raise ValueError("%s: the plugin did not load in Infinite's host" % target["label"])
        _HOST_PARAMS[key] = plugs[0].get("params", [])
    return _HOST_PARAMS[key]


def find_param(target, key):
    params = host_params(target)
    hit = [p for p in params if p["name"].lower() == key.lower() or p["address"] == key]
    if len(hit) != 1:
        near = ", ".join(p["name"] for p in params if key.lower() in p["name"].lower())[:200]
        raise ValueError("%s: no single parameter '%s' (close: %s)" % (target["label"], key, near or "none"))
    return hit[0]


def plugin_mapping(target):
    """Settings by host parameter name (case-insensitive) or address -> Plugin node map slots."""
    slots = []
    for key, val in target["settings"].items():
        p = find_param(target, key)
        lo, hi, v = p["min"], p["max"], float(val)
        if lo is None or hi is None:
            raise ValueError("%s: parameter '%s' has no numeric range" % (target["label"], key))
        if not min(lo, hi) - 1e-9 <= v <= max(lo, hi) + 1e-9:
            raise ValueError("%s: %s=%g is outside the plugin's range %g..%g" % (target["label"], key, v, lo, hi))
        slots.append((p["address"], p["name"], lo, hi, v))
    return slots


def node_category(binp, typ, tmp):
    j = os.path.join(tmp, "describe.json")
    rc, _, _ = run([binp, "--describe", typ, "--json", j], timeout=60)
    try:
        d = json.load(open(j))
        return d["types"][0]["category"]
    except Exception:
        raise ValueError("node:%s - Infinite --describe does not know this type (rc %d)" % (typ, rc))


def patch_text(target, wav, loop, category=None):
    L = ["infinite-patch 1",
         "node 1 Modulators Audio File", "  id src", "  s path " + wav, "  b loop %d" % (1 if loop else 0),
         "  f volume 1", "  f gain 1", "  f attack 0", "  f release 0", "end"]
    if target["kind"] == "dry":
        L += ["node 2 Utility Audio Out", "  id out", "end", "aud out audio src"]
        return "\n".join(L) + "\n"
    if target["kind"] in ("au", "vst3"):
        L += ["node 2 AudioEffects Plugin", "  id fx", "  s plugin_format " + target["kind"], "  s plugin_id " + target["id"],
              "  s plugin_name " + target.get("name", target["label"])]
        slots = plugin_mapping(target) if target.get("settings") else []
        if slots:
            L.append("  i map_slots %d" % len(slots))
        for i, (addr, name, lo, hi, v) in enumerate(slots):
            L += ["  b map%d_assigned 1" % i, "  s map%d_addr %s" % (i, addr), "  s map%d_name %s" % (i, name),
                  "  f map%d_min %r" % (i, lo), "  f map%d_max %r" % (i, hi), "  f map%d_value %r" % (i, v)]
        L.append("end")
    else:
        L += ["node 2 %s %s" % (category, target["type"]), "  id fx"]
        for k, v in target.get("settings", {}).items():
            try:
                L.append("  f %s %r" % (k, float(v)))
            except ValueError:
                L.append("  s %s %s" % (k, v))
        L.append("end")
    L += ["node 3 Utility Audio Out", "  id out", "end", "aud fx 0 src", "aud out audio fx"]
    return "\n".join(L) + "\n"


def render(binp, patch, wav_out, sr, dur, tmp, extra=()):
    # --lenient: the schema comes from a fresh Plugin node, which has no map slots,
    # so strict mode would reject the map<N>_* keys a parameter setting writes.
    p = os.path.join(tmp, "probe.inf")
    with open(p, "w") as f:
        f.write(patch)
    j = os.path.join(tmp, "summary.json")
    rc, out, err = run([binp, "--audio-summary", p, j, "--duration", "%g" % dur, "--sample-rate", "%d" % sr,
                        "--wav", wav_out, "--timeout", "300", "--lenient"] + list(extra), timeout=400)
    status = {}
    for line in reversed(out.strip().splitlines()):
        try:
            # %g prints a non-finite plugin range as inf/nan, which JSON has no spelling for.
            status = json.loads(re.sub(r":(-?)(inf|nan)\b", ":null", line))
            break
        except ValueError:
            continue
    if rc != 0 or not status.get("ok"):
        errs = status.get("errors") or [{"message": (err.strip().splitlines() or ["rc %d" % rc])[-1]}]
        raise RuntimeError("render failed (rc %d): %s" % (rc, errs[0].get("message")))
    return status


def probe(targets, sr=48000, cpu=True, keep=False, params=True, log=print):
    binp = infinite_bin()
    if not binp:
        raise SystemExit(2)
    aus = list_aus()
    resolved = [resolve("dry", aus)]
    for t in targets:
        r = resolve(t, aus)
        if r["kind"] != "dry":
            resolved.append(r)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tmp = ensure_dir(os.path.join(RE_TMP, "plugin-probe-" + stamp))
    stim_path = os.path.join(tmp, "stimulus.wav")
    stim = make_stimulus(sr)
    write_wav24(stim_path, stim, sr)
    stim_rt, _, _ = read_wav(stim_path)
    stim_q = stim_rt[:, 0]
    results, dry_out, dry_slope = [], None, None
    for r in resolved:
        row = {"target": r, "sr": sr}
        try:
            cat = node_category(binp, r["type"], tmp) if r["kind"] == "node" else None
            wav = os.path.join(tmp, "out_%d.wav" % len(results))
            st = render(binp, patch_text(r, stim_path, False, cat), wav, sr, TOTAL_S, tmp)
            out, osr, bits = read_wav(wav)
            row.update(analyse(out, sr, stim_q))
            row["wav_bits"] = bits
            row["warnings"] = [w.get("message") for w in st.get("warnings", [])]
            if r["kind"] == "dry":
                dry_out = out
            elif dry_out is not None and out.shape == dry_out.shape and np.array_equal(out, dry_out):
                row["warnings"].append("output identical to dry: unity setting, or the plugin did not load")
            if cpu:
                t_short = st.get("elapsed_ms", 0)
                st2 = render(binp, patch_text(r, stim_path, True, cat), os.path.join(tmp, "cpu.wav"), sr, TOTAL_S + 30, tmp)
                slope = (st2.get("elapsed_ms", 0) - t_short) / 30.0  # ms of render per second of audio
                if r["kind"] == "dry":
                    dry_slope = slope
                row["cpu_ms_per_s"] = slope
                row["cpu_ms_per_s_net"] = slope - (dry_slope or 0.0)
            if params and r["kind"] in ("au", "vst3"):
                row["params"] = host_params(r)
            row["ok"] = True
        except Exception as e:  # one bad plugin must not stop the table
            row["ok"] = False
            row["error"] = str(e)
        results.append(row)
        log("probed %-32s %s" % (r["label"], "ok" if row["ok"] else "FAILED: " + row["error"]))
    out_dir = ensure_dir(os.path.join(RE_OUTPUT, "plugin-probe", stamp))
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=1, default=float)
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return results, out_dir


# ---------------------------------------------------------------- report

def fmt(v, spec="%.1f", none="-"):
    return none if v is None else spec % v


def sweep_tables(results, name):
    """One table per swept target: every measure at every value of the swept parameter."""
    groups = {}
    for r in results:
        t = r["target"]
        if t["kind"] == "dry" or name not in t.get("settings", {}):
            continue
        base = t["label"].split(" @ ")[0]
        groups.setdefault(base, []).append(r)
    L = []
    for base, rows in groups.items():
        out = []
        for r in sorted(rows, key=lambda r: float(r["target"]["settings"][name])):
            v = r["target"]["settings"][name]
            if not r.get("ok"):
                out.append((v, "FAILED: " + r.get("error", "")) + ("",) * 6)
                continue
            resp = r.get("response_db") or {}
            ref = resp.get(1000, 0.0)
            flat = max([abs(x - ref) for c, x in resp.items() if 63 <= c <= 16000] or [0.0])
            out.append((v, fmt(r["lo"]["gain_db"], "%+.2f"), fmt(r["lo"]["thd_db"]), fmt(r["hi"]["thd_db"]),
                        fmt(r["hf"]["nonharm_db"]), fmt(flat, "%.2f"), fmt(r["tail_s"], "%.2f"),
                        fmt(r.get("cpu_ms_per_s_net"), "%.2f")))
        L += ["## Sweep: %s, %s" % (base, name), "",
              md_table([name, "Gain 1k dB", "THD -12", "THD -1", "Alias HF dB", "Flatness ±dB", "Tail -60 s", "CPU ms/s"], out), ""]
    return L


def to_markdown(results, sweep=None):
    sr = results[0]["sr"] if results else 0
    rows = []
    for r in results:
        if not r.get("ok"):
            rows.append((r["target"]["label"], "FAILED: " + r.get("error", "")) + ("",) * 10)
            continue
        resp = r.get("response_db") or {}
        ref = resp.get(1000, 0.0)
        flat = max([abs(v - ref) for c, v in resp.items() if 63 <= c <= 16000] or [0.0])
        lat = r["latency_onset"]
        # A time-based effect smears the tones with its own tail: THD/alias then measure the tail, not distortion.
        star = "*" if (r["tail_s"] or 0) > 0.5 else ""
        rows.append((
            r["target"]["label"],
            "%s (%s ms)" % (fmt(lat, "%d"), fmt(None if lat is None else lat * 1000.0 / sr, "%.2f")),
            fmt(r["lo"]["gain_db"], "%+.2f"),
            fmt(r["lo"]["thd_db"]) + star, fmt(r["lo"]["thdn_db"]) + star, fmt(r["hi"]["thd_db"]) + star,
            fmt(r["hf"]["nonharm_db"]) + star,
            fmt(flat, "%.2f"),
            fmt(r["tail_s"], "%.2f"), fmt(r["rt60_s"], "%.2f"),
            fmt(r.get("cpu_ms_per_s_net"), "%.2f"),
            len(r.get("params") or []) or "-",
        ))
    L = ["# Plugin probe (%d Hz, %d-bit render)" % (sr, results[0].get("wav_bits", 0) if results else 0), "",
         "Generated by `tools/re-survey/plugin_probe.py`. Black-box: test signal in, Infinite's own host, "
         "measurement out. Plugins run at their default state except the settings shown after @.", "",
         md_table(["Target", "Latency smp (ms)", "Gain 1k dB", "THD -12", "THD+N -12", "THD -1", "Alias HF dB",
                   "Flatness ±dB 63-16k", "Tail -60 s", "RT60 s", "CPU ms/s (net)", "Params"], rows), "",
         "- THD/aliasing in dB relative to the fundamental. The dry row is the rig floor: nothing below it is real.",
         "- Alias HF: all non-harmonic energy around a %.0f Hz sine at -6 dBFS (aliasing + noise)." % hf_freq(sr),
         "- `*` = tail longer than 0.5 s (reverb/delay): its THD/alias columns measure the tail, compare tails instead.",
         "- CPU: render ms per second of audio minus the dry rig, offline single-thread. Lower is better; 10 = 1% of a core.", ""]
    for r in results:
        if r.get("ok") and r.get("response_db"):
            L.append("- %s response dB: %s" % (r["target"]["label"], ", ".join(
                "%g:%+.1f" % (c, v) for c, v in sorted(r["response_db"].items()))))
        for w in r.get("warnings", []) if r.get("ok") else []:
            L.append("- WARNING %s: %s" % (r["target"]["label"], w))
    if sweep:
        L += [""] + sweep_tables(results, sweep)
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("plugin_probe")
    sr = 48000
    ir = np.zeros(sr)
    ir[100] = 0.5
    t.check(latency(ir) == (100, 100), "latency of a 100-sample delayed impulse")
    n = 24000
    k = np.arange(n)
    x = np.sin(2 * np.pi * 1000 * k / sr) + 0.01 * np.sin(2 * np.pi * 3000 * k / sr)
    thd = tone_metrics(x, sr, 1000)["thd_db"]
    t.check(abs(thd + 40.0) < 0.5, "THD of 1%% third harmonic = -40 dB (got %.2f)" % thd)
    clean = tone_metrics(np.sin(2 * np.pi * 1000 * k / sr), sr, 1000)["thd_db"]
    t.check(clean < -120, "THD of a clean float sine below -120 dB (got %.1f)" % clean)
    rng = np.random.default_rng(1)
    tt = np.arange(2 * sr) / sr
    rev = rng.standard_normal(2 * sr) * 10 ** (-3 * tt / 1.0)  # RT60 = 1.0 s
    rt = rt60(rev, sr)
    t.check(rt is not None and abs(rt - 1.0) < 0.1, "RT60 of a 1.0 s exponential decay (got %s)" % rt)
    flat = response(ir, sr, 0.5)
    t.check(all(abs(v) < 0.01 for v in flat.values()), "unit impulse response is flat")
    stim = make_stimulus(sr)
    tmp = ensure_dir(os.path.join(RE_TMP, "plugin-probe-selftest"))
    try:
        p = os.path.join(tmp, "s.wav")
        write_wav24(p, stim, sr)
        back, bsr, bits = read_wav(p)
        t.check(bits == 24 and bsr == sr and np.max(np.abs(back[:, 0] - stim)) < 2e-7, "24-bit WAV round trip")
        a = analyse(np.stack([back[:, 0], back[:, 0]], 1), sr, back[:, 0])
        t.check(a["latency_onset"] == 0 and abs(a["lo"]["gain_db"]) < 0.01, "analysing the stimulus itself: 0 latency, 0 dB")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    t.check(resolve("au:aufx:dely:appl", list_aus())["kind"] == "au", "AU id resolves")
    t.check(resolve("vst3:ABC@Mix=1", [])["settings"] == {"Mix": "1"}, "VST3 id resolves with settings")
    t.check(sweep_values("range:5", 0.0, 1.0) == ["0", "0.25", "0.5", "0.75", "1"], "range:5 spans the host range")
    if not infinite_bin():
        t.skip("no Infinite binary: integration part (set INFINITE_BIN or build)")
        return t.done()
    res, out_dir = probe(["au:aufx:dely:appl"], sr=sr, cpu=False, params=False, log=lambda *_: None)
    dry, dly = res[0], res[1]
    t.check(dry.get("ok") and dry["latency_onset"] == 0, "dry rig: zero latency")
    t.check(dry.get("ok") and abs(dry["lo"]["gain_db"]) < 0.1, "dry rig: unity gain (%.3f dB)" % dry["lo"]["gain_db"])
    t.check(dry.get("ok") and dry["lo"]["thdn_db"] < -70, "dry rig floor THD+N < -70 dB (%.1f)" % dry["lo"]["thdn_db"])
    t.check(dly.get("ok") and (dly["tail_s"] or 0) > 1.5, "AUDelay: echo tail > 1.5 s (%s)" % dly.get("tail_s"))
    t.check(dly.get("ok") and not any("identical to dry" in w for w in dly.get("warnings", [])), "AUDelay output differs from dry")
    shutil.rmtree(out_dir, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    lp = sub.add_parser("list", help="installed Audio Unit effects with probe ids")
    lp.add_argument("--filter", default="")
    rp = sub.add_parser("run", help="probe targets")
    rp.add_argument("targets", nargs="+")
    rp.add_argument("--sr", type=int, default=48000)
    rp.add_argument("--no-cpu", action="store_true")
    rp.add_argument("--no-params", action="store_true")
    rp.add_argument("--keep", action="store_true", help="keep render WAVs in ~/re-output/tmp")
    rp.add_argument("--out", help="markdown table path (default stdout)")
    rp.add_argument("--sweep", help="Name=v1,v2,... or Name=range:N : run every non-dry target once per value")
    pp = sub.add_parser("params", help="a plugin's parameters as Infinite's host sees them (names + own ranges)")
    pp.add_argument("target")
    pp.add_argument("--filter", default="")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == "list":
        rows = [(x["id"], x["name"], x["type"]) for x in list_aus() if a.filter.lower() in x["name"].lower()]
        print(md_table(["id", "name", "type"], rows))
        return 0
    if a.cmd == "params":
        if not infinite_bin():
            print("no Infinite binary (build it, or set INFINITE_BIN)", file=sys.stderr)
            return 2
        try:
            r = resolve(a.target, list_aus())
            if r["kind"] not in ("au", "vst3"):
                raise ValueError("params lists plugin parameters; for a node use Infinite --describe")
            rows = [(p["address"], p["name"], fmt(p["min"], "%g"), fmt(p["max"], "%g"), fmt(p["default"], "%g"), p["unit"])
                    for p in host_params(r) if a.filter.lower() in p["name"].lower()]
        except ValueError as e:
            print("usage: %s" % e, file=sys.stderr)
            return 2
        print(md_table(["address", "name", "min", "max", "default", "unit"], rows))
        return 0
    if a.cmd != "run":
        ap.print_usage(sys.stderr)
        return 2
    if not infinite_bin():
        print("no Infinite binary (build it, or set INFINITE_BIN)", file=sys.stderr)
        return 2
    try:
        aus = list_aus()
        targets = expand_sweep(a.targets, a.sweep, aus)
        for t in targets:
            r = resolve(t, aus)
            if r["kind"] in ("au", "vst3") and r["settings"]:
                plugin_mapping(r)
    except ValueError as e:
        print("usage: %s" % e, file=sys.stderr)
        return 2
    res, out_dir = probe(targets, sr=a.sr, cpu=not a.no_cpu, keep=a.keep, params=not a.no_params,
                         log=lambda m: print(m, file=sys.stderr))
    write_out(to_markdown(res, a.sweep.partition("=")[0].strip() if a.sweep else None), a.out)
    print("results: %s" % os.path.join(out_dir, "results.json"), file=sys.stderr)
    return 0 if all(r.get("ok") for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
