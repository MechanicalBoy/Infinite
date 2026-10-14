#!/usr/bin/env python3
"""FINAL: one command, one JSON line. Local tests (T1 T2 T3 T5 T6) and, given run files, T4, T7 and the verdict.

  final_suite.py [--runs out/full.runs.jsonl] [--t7 out/t7.runs.jsonl]
T2 here also pushes every fuzz paragraph through the real CLI `--validate`: 0 crashes (a crash = no JSON or a
code other than 0/3). T4 = first-try validity of the first `al apply`, B1 held-out, per model (>= 90%).
T7 = share of decode-back sessions that pass the same oracle (>= 95%). Exit 0 only when every present gate passes.
"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check, codec, harness, oracle, test_codec  # noqa: E402

out, bad = {}, []


def gate(name, ok, **kw):
    out[name] = dict(ok=bool(ok), **kw)
    if not ok:
        bad.append(name)


# T1 T2 T3 T6 from the codec tests (their own failure list)
test_codec.out.clear() if hasattr(test_codec, "out") else None
captured = []
real_decode = codec.decode


def spy(text, patch=codec.EMPTY, F=None):
    r = real_decode(text, patch, F)
    if r.get("ok"):
        captured.append(r["patch_text"])
    return r


codec.decode = spy
test_codec.t1(); test_codec.t3(); test_codec.t2(); test_codec.t6()
codec.decode = real_decode
gate("T1_T3_T6_T2decode", not test_codec.bad, **{k: test_codec.out.get(k) for k in ("T1", "T3", "T2", "T6")})

# T2 through the CLI
crash = valid = typed = 0
for p in captured[:200]:
    f = tempfile.mktemp(suffix=".inf")
    open(f, "w").write(p)
    try:
        rc, j, _ = check.run(["--validate", f])
        if rc == 0 and j.get("ok"): valid += 1
        elif rc == 3 and j.get("errors") is not None: typed += 1
        else: crash += 1
    except Exception:
        crash += 1
gate("T2_cli", crash == 0, fuzzed=len(captured[:200]), valid=valid, typed_rejections=typed, crashes=crash)

# T5 meaning: encode then decode keeps the oracle verdict and the frame stats
T, same, tot, skipped = oracle.load_tasks(), 0, 0, []
for i, t in T.items():
    sol = open(os.path.join(HERE, "tasks", i + ".solution.inf")).read()
    enc = codec.encode(sol)
    if not enc.get("complete"):
        skipped.append(i); continue
    r = real_decode(enc["sentences"], codec.EMPTY)
    f = tempfile.mktemp(suffix=".inf"); open(f, "w").write(r["patch_text"]) if r.get("ok") else None
    tot += 1
    if r.get("ok") and harness.score(t, f)["ok"]:
        same += 1
gate("T5_meaning", tot > 0 and same == tot, round_tripped=same, of=tot, not_expressible=skipped)

# T4, T7 and the verdict from model runs
args = sys.argv[1:]
def arg(n): return args[args.index(n) + 1] if n in args else None
if arg("--runs"):
    rows = [json.loads(l) for l in open(arg("--runs")) if l.strip()]
    per = {}
    for m in sorted({r["model"] for r in rows}):
        b1 = [r for r in rows if r["model"] == m and r["arm"] == "B1" and r["split"] == "held-out" and r.get("al_first_ok") is not None]
        per[m] = round(sum(bool(r["al_first_ok"]) for r in b1) / max(1, len(b1)), 3)
    gate("T4_cold_write", per and all(v >= 0.9 for v in per.values()), first_try_valid=per)
    v = subprocess.run([sys.executable, os.path.join(HERE, "verdict.py"), arg("--runs")], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    vj = json.loads(v)
    gate("VERDICT", vj["verdict"] == "KEEP-GOING", verdict=vj["verdict"], wins=vj["wins"], models=vj["models"])
if arg("--t7"):
    rows = [json.loads(l) for l in open(arg("--t7")) if l.strip()]
    ok = sum(bool(r["oracle"]["ok"]) for r in rows)
    gate("T7_decode_back", rows and ok / len(rows) >= 0.95, passed=ok, of=len(rows))
print(json.dumps({"ok": not bad, "failed": bad, "gates": out}))
sys.exit(0 if not bad else 1)
