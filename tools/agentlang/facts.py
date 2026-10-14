"""Node facts for the codec.

Three layers, later ones win:
  1. types, slots, kinds   from the generated table in the infinite-patch-authoring skill
  2. key kinds (f/i/b/c/s) harvested from the repo's own .inf files (keys_seen.json, harvest_keys.py)
  3. ranges, options, defaults from nodefacts.json, the output of `Infinite --describe --json`
     (dump_facts.py, run where the app is built). Optional: without it the codec cannot check
     ranges, and says so in the reply (`checked_by: --validate`).
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SKILL = os.path.join(ROOT, ".claude/skills/infinite-patch-authoring/SKILL.md")
KEYS_SEEN = os.path.join(HERE, "keys_seen.json")
NODEFACTS = os.path.join(HERE, "nodefacts.json")

FIELD_TYPES = {"Field Synth", "Field Effect", "Field Graph", "Field Notes", "Field Modifier",
               "Field Primitive", "FieldPixel"}
GEO_KINDS = {"geometry", "camera", "light", "environment"}


def wire_tag(kind):
    """Record tag for a wire carrying this kind, or None (modulator, palette, predictor: not a `wire`)."""
    if kind == "image":
        return "cable"
    if kind == "audio":
        return "aud"
    if kind == "note":
        return "note"
    if kind in GEO_KINDS:
        return "geo"
    return None


class TypeFacts:
    def __init__(self, name, category, inputs, outputs, nparams, bypass):
        self.name, self.category = name, category
        self.inputs = inputs      # [(slot name, kind)]
        self.outputs = outputs    # [(label, kind)]
        self.nparams, self.bypass = nparams, bypass
        self.keys = {}            # key -> {tag, min, max, options, default}


def _sig(cell):
    cell = cell.strip()
    if cell == "none":
        return []
    out = []
    for part in cell.split(", "):
        name, _, kind = part.rpartition(":")
        out.append((name, kind))
    return out


class Facts:
    def __init__(self, types):
        self.types = types
        self.has_ranges = False
        self.complete = set()   # types whose key list is complete (came from nodefacts)

    def type(self, name):
        return self.types.get(name)

    def slot_index(self, tname, slot):
        """Input slot index for a name or number, or None."""
        ins = self.types[tname].inputs
        if re.fullmatch(r"\d+", slot):
            i = int(slot)
            return i if i < len(ins) else None
        for i, (n, _) in enumerate(ins):
            if n == slot:
                return i
        return None


def load(skill=SKILL, keys_seen=KEYS_SEEN, nodefacts=NODEFACTS):
    text = open(skill).read()
    body = text.split("<!-- generated:begin -->")[1].split("<!-- generated:end -->")[0]
    types, cat = {}, None
    for line in body.splitlines():
        if line.startswith("### "):
            cat = line[4:].strip()
        m = re.match(r"\| `([^`]+)` \| (.*?) \| (.*?) \| (\d+) \| (.*?) \|$", line)
        if m and cat:
            types[m.group(1)] = TypeFacts(m.group(1), cat, _sig(m.group(2)), _sig(m.group(3)),
                                          int(m.group(4)), "bypass" in m.group(5))
    f = Facts(types)
    if keys_seen and os.path.exists(keys_seen):
        for t, ks in json.load(open(keys_seen)).items():
            if t in types:
                for k, tag in ks.items():
                    types[t].keys[k] = {"tag": tag}
    if nodefacts and os.path.exists(nodefacts):
        f.has_ranges = True
        for t in json.load(open(nodefacts))["types"]:
            tf = types.get(t["type"])
            if not tf:
                continue
            for r in t.get("rows") or []:
                tf.keys[r["key"]] = {"tag": r["tag"], "min": r.get("min"), "max": r.get("max"),
                                     "options": r.get("options") or [], "default": r.get("default")}
            f.complete.add(t["type"])
    return f
