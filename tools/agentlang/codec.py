#!/usr/bin/env python3
"""Tongue codec: sentences <-> .inf text. Standard library only.

  decode(text, patch_text) -> {ok, patch_text, errors, checked_by, asked, applied}
  encode(inf_text)         -> {ok, sentences, excluded, complete}
  gloss(text, lang="en")   -> text
  ask(type)                -> trimmed describe dict from the node facts

Errors: E_LEX (1), E_SYN (2), E_SEM (3) are checked here; E_FIELD (4) is the CLI's `--validate`.
Ranges and options come from nodefacts.json when present (dump_facts.py, Phase 2); without it the
reply says `checked_by: "--validate"` for what this checker cannot see.

CLI: codec.py decode SENTENCES.txt PATCH.inf | encode PATCH.inf | gloss SENTENCES.txt | ask TYPE
(last stdout line is JSON).
"""
import difflib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import facts, inf  # noqa: E402

VERBS = ["ask", "add", "set", "wire", "cut", "del", "field"]
SIG = {
    "ask": "ask <type>",
    "add": "add <type> as <name>",
    "set": "set <name>.<key> <value>",
    "wire": "wire <src> <dst>[.<slot>]",
    "cut": "cut <src> <dst>[.<slot>]",
    "del": "del <name>",
    "field": "field <name> <code>",
}
NUM = re.compile(r"[-]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*$")
EMPTY = "infinite-patch 1\n"


class Fail(Exception):
    def __init__(self, code, level, hint):
        self.code, self.level, self.hint = code, level, hint


def near(word, pool, n=3):
    return difflib.get_close_matches(word, sorted(pool), n=n, cutoff=0.0)


def isnum(v):
    return bool(NUM.match(v))


def fmt_num(v):
    """Canonical number text: no trailing zeros, no '+', no exponent padding."""
    try:
        x = float(v)
    except ValueError:
        return v
    if x == int(x) and abs(x) < 1e15 and "e" not in v.lower():
        return str(int(x))
    return repr(x)


def key_tag(F, tf, key, value):
    """Tag the decoder writes for this key: from the facts, else inferred from the value."""
    k = tf.keys.get(key)
    if k:
        return k["tag"]
    if isnum(value):
        return "f"
    if value in ("0", "1"):
        return "f"
    return "i" if re.fullmatch(r"[A-Za-z][\w ]*", value) else "s"


# ------------------------------------------------------------------ ask / gloss

def ask(type_, F=None):
    F = F or facts.load()
    tf = F.type(type_)
    if not tf:
        return {"error": "E_LEX", "hint": "nearest: " + ", ".join(near(type_, F.types))}
    keys = []
    for k, d in sorted(tf.keys.items()):
        row = {"key": k, "tag": d["tag"]}
        for f in ("min", "max", "options", "default"):
            if d.get(f) not in (None, []):
                row[f] = d[f]
        keys.append(row)
    return {"type": tf.name, "category": tf.category,
            "inputs": [{"slot": n, "kind": k} for n, k in tf.inputs],
            "outputs": [{"label": n, "kind": k} for n, k in tf.outputs],
            "keys": keys, "bypass": tf.bypass,
            "ranges": F.has_ranges and tf.name in F.complete}


def gloss(text, lang="en", F=None):
    if lang != "en":
        raise ValueError("only en")
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            out.append("")
            continue
        verb, _, rest = s.partition(" ")
        if verb == "ask":
            out.append(f"Look up the node type {rest}.")
        elif verb == "add":
            m = re.match(r"(.+) as (\S+)$", rest)
            out.append(f"Add a {m.group(1)} node called {m.group(2)}." if m else f"(bad) {s}")
        elif verb == "set":
            m = re.match(r"(\S+?)\.(\S+) (.+)$", rest)
            out.append(f"Set {m.group(2)} of {m.group(1)} to {m.group(3)}." if m else f"(bad) {s}")
        elif verb in ("wire", "cut"):
            m = re.match(r"(\S+) (\S+?)(?:\.(\S+))?$", rest)
            if m:
                where = f"input {m.group(3)} of {m.group(2)}" if m.group(3) else m.group(2)
                out.append(f"Connect {m.group(1)} into {where}." if verb == "wire"
                           else f"Disconnect {m.group(1)} from {where}.")
            else:
                out.append(f"(bad) {s}")
        elif verb == "del":
            out.append(f"Delete {rest} and its connections.")
        elif verb == "field":
            n, _, code = rest.partition(" ")
            out.append(f"Set the Field code of {n} to: {code}")
        else:
            out.append(f"(bad) {s}")
    return "\n".join(out)


# ------------------------------------------------------------------ decode

class State:
    def __init__(self, patch_text, F):
        self.F = F
        self.g = inf.parse(patch_text)
        for w in self.g.wires:
            w["_d"], w["_s"] = self.g.resolve(w["dst"]), self.g.resolve(w["src"])

    def clone(self):
        return State(self.text(), self.F)

    def text(self):
        g = self.g
        for i, n in enumerate(g.nodes, 1):
            n.index = i
        for w in g.wires:
            if w["_d"] and w["_s"]:
                w["dst"] = w["_d"].id or str(w["_d"].index)
                w["src"] = w["_s"].id or str(w["_s"].index)
        return inf.write(g)

    def node(self, name, what="node"):
        n = self.g.resolve(name)
        if not n:
            names = [x.id or str(x.index) for x in self.g.nodes]
            raise Fail("E_SEM", 3, f"no {what} named {name}; names: {', '.join(names) or '(none)'}")
        return n

    def tfacts(self, n):
        tf = self.F.type(n.type)
        if not tf:
            raise Fail("E_SEM", 3, f"{n.type} is not a known node type")
        return tf


def _split_ref(tok):
    name, _, slot = tok.partition(".")
    return name, (slot or None)


def _pick_slot(st, dst, slot, kind_needed=None):
    tf = st.tfacts(dst)
    if slot is None:
        if len(tf.inputs) != 1:
            names = ", ".join(n for n, _ in tf.inputs) or "none"
            raise Fail("E_SEM", 3, f"{tf.name} has {len(tf.inputs)} input slots; write dst.slot, one of: {names}")
        return 0
    si = st.F.slot_index(tf.name, slot)
    if si is None:
        names = ", ".join(n for n, _ in tf.inputs) or "none"
        raise Fail("E_SEM", 3, f"{tf.name} has no slot {slot}; slots: {names}")
    return si


def _check_value(F, tf, n, key, value):
    k = tf.keys.get(key, {})
    tag = key_tag(F, tf, key, value)
    if tag == "f":
        if not isnum(value):
            raise Fail("E_SEM", 3, f"{key} needs a number, got {value}")
    elif tag == "i":
        opts = k.get("options") or []
        if not isnum(value) and opts and value.lower() not in [o.lower() for o in opts]:
            raise Fail("E_SEM", 3, f"{key} options: {', '.join(opts)}")
        if not isnum(value) and not re.fullmatch(r"[A-Za-z][\w ]*", value):
            raise Fail("E_SEM", 3, f"{key} needs a number or an option name, got {value}")
    elif tag == "b":
        if value not in ("0", "1"):
            raise Fail("E_SEM", 3, f"{key} is a switch: 0 or 1")
    elif tag == "c":
        parts = value.split()
        if len(parts) not in (3, 4) or not all(isnum(p) for p in parts):
            raise Fail("E_SEM", 3, f"{key} is a colour: r g b or r g b a")
    if tag in ("f", "i") and isnum(value) and (k.get("min") is not None or k.get("max") is not None):
        x = float(value)
        lo, hi = k.get("min"), k.get("max")
        if (lo is not None and x < lo) or (hi is not None and x > hi):
            cur = n.get(key)[2] if n.get(key) else k.get("default")
            raise Fail("E_SEM", 3, f"{key} min {lo} max {hi} current {cur}")
    return tag


def apply_sentence(st, line):
    F, g = st.F, st.g
    verb, _, rest = line.partition(" ")
    rest = rest.strip()
    if verb not in SIG:
        raise Fail("E_LEX", 1, "nearest: " + ", ".join(near(verb, VERBS)))
    sig = f"signature: {SIG[verb]}"

    if verb == "ask":
        if not rest:
            raise Fail("E_SYN", 2, sig)
        if rest not in F.types:
            raise Fail("E_LEX", 1, "nearest: " + ", ".join(near(rest, F.types)))
        return ask(rest, F)

    if verb == "add":
        m = re.fullmatch(r"(.+?) as (\S+)", rest)
        if not m:
            raise Fail("E_SYN", 2, sig)
        type_, name = m.groups()
        if type_ not in F.types:
            raise Fail("E_LEX", 1, "nearest: " + ", ".join(near(type_, F.types)))
        if not NAME.match(name) or g.by_name(name):
            raise Fail("E_SEM", 3, f"name {name} is taken or not a word (letters, digits, _ and -; not a number)")
        tf = F.type(type_)
        n = inf.Node(max([x.index for x in g.nodes] + [0]) + 1, tf.category, type_)
        n.id = name
        g.nodes.append(n)
        return None

    if verb == "set":
        m = re.fullmatch(r"([^\s.]+)\.(\S+) (.+)", rest)
        if not m:
            raise Fail("E_SYN", 2, sig)
        name, key, value = m.group(1), m.group(2), m.group(3).strip()
        n = st.node(name)
        tf = st.tfacts(n)
        if tf.name in facts.FIELD_TYPES and key == "code":
            raise Fail("E_SEM", 3, "use: field <name> <code>")
        if tf.name in F.complete and key not in tf.keys:
            raise Fail("E_SEM", 3, f"{tf.name} has no key {key}; nearest: " + ", ".join(near(key, tf.keys)))
        tag = _check_value(F, tf, n, key, value)
        n.put(tag, key, fmt_num(value) if tag == "f" else value)
        return None

    if verb == "field":
        name, _, code = rest.partition(" ")
        if not name or not code.strip():
            raise Fail("E_SYN", 2, sig)
        if "#" in code:
            raise Fail("E_SYN", 2, "no # in a field sentence (it would start a comment); " + sig)
        n = st.node(name)
        if n.type not in facts.FIELD_TYPES:
            raise Fail("E_SEM", 3, f"{n.type} is not a Field node; Field nodes: " + ", ".join(sorted(facts.FIELD_TYPES)))
        n.put("s", "code", code.strip())
        return None

    if verb == "del":
        if not rest or " " in rest:
            raise Fail("E_SYN", 2, sig)
        n = st.node(rest)
        g.nodes.remove(n)
        g.wires = [w for w in g.wires if w["_d"] is not n and w["_s"] is not n]
        return None

    # wire / cut
    toks = rest.split()
    if len(toks) != 2:
        raise Fail("E_SYN", 2, sig)
    src = st.node(toks[0], "source")
    dname, slot = _split_ref(toks[1])
    dst = st.node(dname, "destination")
    stf, dtf = st.tfacts(src), st.tfacts(dst)
    si = _pick_slot(st, dst, slot)
    if verb == "cut":
        hit = [w for w in g.wires if w["_s"] is src and w["_d"] is dst and
               (slot is None or F.slot_index(dtf.name, w["slot"]) == si)]
        if not hit:
            raise Fail("E_SEM", 3, f"no wire from {toks[0]} to {toks[1]}")
        g.wires = [w for w in g.wires if w not in hit]
        return None
    kind = dtf.inputs[si][1]
    tag = facts.wire_tag(kind)
    if tag is None:
        raise Fail("E_SEM", 3, f"{dtf.name}.{dtf.inputs[si][0]} takes a {kind}; not a wire in v0")
    if not stf.outputs:
        raise Fail("E_SEM", 3, f"{stf.name} has no output")
    if stf.outputs[0][1] != kind:
        raise Fail("E_SEM", 3, f"{stf.name} gives {stf.outputs[0][1]}; {dtf.name}.{dtf.inputs[si][0]} takes {kind}")
    for w in g.wires:
        if w["_d"] is dst and F.slot_index(dtf.name, w["slot"]) == si:
            who = w["_s"].id if w["_s"] else "another node"
            raise Fail("E_SEM", 3, f"{dtf.name}.{dtf.inputs[si][0]} already takes {who}; cut it first")
    g.wires.append({"tag": tag, "dst": "", "slot": dtf.inputs[si][0], "src": "", "rest": [], "pre": [],
                    "_d": dst, "_s": src})
    return None


def paragraphs(text):
    """[(first line number, [sentence lines])]; a blank line ends a paragraph."""
    out, cur, start = [], [], 0
    for i, ln in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        if ln.strip():
            if not cur:
                start = i
            cur.append((i, ln.strip()))
        elif cur:
            out.append((start, cur))
            cur = []
    if cur:
        out.append((start, cur))
    return out


def decode(text, patch_text=EMPTY, F=None):
    F = F or facts.load()
    st = State(patch_text or EMPTY, F)
    asked, applied = [], 0
    for _, lines in paragraphs(text):
        trial = st.clone()
        got = []
        for no, ln in lines:
            try:
                r = apply_sentence(trial, ln)
            except Fail as e:
                return {"ok": False, "patch_text": st.text(), "applied": applied, "asked": asked,
                        "errors": [{"code": e.code, "level": e.level, "line": no, "hint": e.hint}]}
            if r:
                got.append(r)
        st, applied = trial, applied + 1
        asked += got
    return {"ok": True, "patch_text": st.text(), "applied": applied, "asked": asked, "errors": [],
            "checked_by": "--validate" + ("" if F.has_ranges else " (ranges, Field)")}


# ------------------------------------------------------------------ encode

def _names(g):
    used, out = set(), {}
    for n in g.nodes:
        if n.id and NAME.match(n.id) and n.id not in used:
            used.add(n.id)
            out[id(n)] = n.id
    for n in g.nodes:
        if id(n) not in out:
            base = f"n{n.index}"
            while base in used:
                base += "x"
            used.add(base)
            out[id(n)] = base
    return out


def encode(inf_text, F=None):
    F = F or facts.load()
    g = inf.parse(inf_text)
    why, lines = [], []
    names = _names(g)
    for e in g.extras:
        why.append(f"record {e['tag']} (modulation, expressions and other records are out of v0)")
    seen = set()
    for n in g.nodes:
        tf = F.type(n.type)
        if not tf:
            why.append(f"unknown node type {n.type}")
            continue
        if n.flags:
            why.append(f"{n.type}: flags line")
        if n.raw:
            why.append(f"{n.type}: record {n.raw[0].split()[0]}")
        lines.append(f"add {n.type} as {names[id(n)]}")
        keys = set()
        for tag, key, val in n.params:
            if key in keys:
                why.append(f"{n.type}.{key} written twice")
            keys.add(key)
            if tag == "s" and "\n" in val:
                why.append(f"{n.type}.{key}: multi-line text")
            if n.type in facts.FIELD_TYPES and key == "code":
                if "#" in val:
                    why.append(f"{n.type}.code contains #")
                lines.append(f"field {names[id(n)]} {val}")
                continue
            if tag == "f":
                if not isnum(val):
                    why.append(f"{n.type}.{key}: float text {val!r}")
                    continue
                val = fmt_num(val)
            if key_tag(F, tf, key, val) != tag:
                why.append(f"{n.type}.{key}: tag {tag} cannot be derived from the sentence")
            if " " in key or not val:
                why.append(f"{n.type}.{key}: unwritable key or empty value")
            lines.append(f"set {names[id(n)]}.{key} {val}")
    for w in g.wires:
        d, s = g.resolve(w["dst"]), g.resolve(w["src"])
        if w["rest"]:
            why.append("wire with extra fields")
        if not d or not s or not F.type(d.type):
            why.append("wire to a missing or unknown node")
            continue
        dtf = F.type(d.type)
        si = F.slot_index(d.type, w["slot"])
        if si is None:
            why.append(f"{d.type}: unknown slot {w['slot']}")
            continue
        tok = names[id(d)] if len(dtf.inputs) == 1 else f"{names[id(d)]}.{dtf.inputs[si][0]}"
        lines.append(f"wire {names[id(s)]} {tok}")
    sentences = "\n".join(lines) + ("\n" if lines else "")
    why = list(dict.fromkeys(why))
    if not why:
        r = decode(sentences, EMPTY, F)
        if not r["ok"]:
            e = r["errors"][0]
            why.append(f"decoder rejects line {e['line']}: {e['code']} {e['hint']}")
    return {"ok": True, "sentences": sentences, "excluded": why, "complete": not why}


# ------------------------------------------------------------------ compare

def canon(inf_text, F=None):
    """Graph identity for T1: node types and params in order, wires as index triples; ignores ids,
    positions, comments, categories and float formatting."""
    F = F or facts.load()
    g = inf.parse(inf_text)
    order = {id(n): i for i, n in enumerate(g.nodes)}
    nodes = []
    for n in g.nodes:
        ps = []
        for tag, key, val in n.params:
            ps.append((tag, key, ("%.9g" % float(val)) if tag == "f" and isnum(val) else val))
        nodes.append((n.type, tuple(ps)))
    wires = []
    for w in g.wires:
        d, s = g.resolve(w["dst"]), g.resolve(w["src"])
        si = F.slot_index(d.type, w["slot"]) if d and F.type(d.type) else w["slot"]
        wires.append((w["tag"], order.get(id(d)), si, order.get(id(s))))
    return nodes, wires


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "decode":
        r = decode(open(argv[1]).read(), open(argv[2]).read() if len(argv) > 2 else EMPTY)
    elif cmd == "encode":
        r = encode(open(argv[1]).read())
    elif cmd == "gloss":
        print(gloss(open(argv[1]).read()))
        return 0
    elif cmd == "ask":
        r = ask(" ".join(argv[1:]))
    else:
        print(__doc__)
        return 2
    print(json.dumps(r))
    return 0 if r.get("ok", True) and "error" not in r else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
