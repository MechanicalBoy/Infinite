"""Parse and write the .inf text format (the subset the agent language touches).

A graph keeps nodes in file order, the four wire tags, and any other record (mod, expr, glob, pal,
rev, unknown tags) as raw extras so a decode never loses what it does not understand.
Standard library only.
"""
import re

WIRE_TAGS = ("cable", "geo", "aud", "note")
NODE_TAGS = ("f", "i", "b", "c", "s")


class Node:
    def __init__(self, index, category, type_):
        self.index, self.category, self.type = index, category, type_
        self.id = None
        self.pos = None          # raw "x y" or None
        self.flags = None        # raw text or None
        self.params = []         # [tag, key, value-text], file order
        self.raw = []            # other lines inside the node
        self.pre = []            # comment lines before the node

    def get(self, key):
        for p in self.params:
            if p[1] == key:
                return p
        return None

    def put(self, tag, key, value):
        p = self.get(key)
        if p:
            p[0], p[2] = tag, value
        else:
            self.params.append([tag, key, value])


class Graph:
    def __init__(self):
        self.nodes = []          # Node, file order
        self.wires = []          # dict(tag, dst, slot, src, rest, pre); dst/src as written
        self.extras = []         # dict(tag, line, pre)
        self.header = "infinite-patch 1"

    def by_index(self, i):
        for n in self.nodes:
            if n.index == i:
                return n
        return None

    def by_name(self, name):
        for n in self.nodes:
            if n.id == name:
                return n
        return None

    def resolve(self, ref):
        """Node for an id or a numeric index written as text; None when unknown."""
        n = self.by_name(ref)
        if n:
            return n
        if re.fullmatch(r"\d+", ref):
            return self.by_index(int(ref))
        return None


def parse(text):
    g = Graph()
    lines = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").split("\n")
    pre, cur = [], None
    for ln in lines:
        s = ln.strip()
        if cur is not None:
            if s == "end":
                g.nodes.append(cur)
                cur = None
            elif s.startswith("#") or not s:
                continue
            else:
                tag, _, rest = s.partition(" ")
                if tag == "id":
                    cur.id = rest.strip()
                elif tag == "pos":
                    cur.pos = rest.strip()
                elif tag == "flags":
                    cur.flags = rest.strip()
                elif tag in NODE_TAGS:
                    key, _, val = rest.lstrip().partition(" ")
                    cur.params.append([tag, key, val if tag == "s" else val.strip()])
                else:
                    cur.raw.append(s)
            continue
        if not s:
            continue
        if s.startswith("#"):
            pre.append(s)
            continue
        tag, _, rest = s.partition(" ")
        if tag == "infinite-patch":
            g.header = s
        elif tag == "node":
            m = re.match(r"(\d+)\s+(\S+)\s+(.+?)\s*$", rest)
            if not m:
                g.extras.append({"tag": "bad", "line": s, "pre": pre})
            else:
                cur = Node(int(m.group(1)), m.group(2), m.group(3))
                cur.pre, pre = pre, []
                continue
        elif tag in WIRE_TAGS:
            t = rest.split()
            if len(t) < 3:
                g.extras.append({"tag": "bad", "line": s, "pre": pre})
            else:
                g.wires.append({"tag": tag, "dst": t[0], "slot": t[1], "src": t[2], "rest": t[3:], "pre": pre})
        else:
            g.extras.append({"tag": tag, "line": s, "pre": pre})
        pre = []
    return g


def write(g):
    out = [g.header]
    for n in g.nodes:
        out += n.pre
        out.append(f"node {n.index} {n.category} {n.type}")
        if n.id:
            out.append(f"  id {n.id}")
        if n.pos:
            out.append(f"  pos {n.pos}")
        if n.flags:
            out.append(f"  flags {n.flags}")
        for tag, key, val in n.params:
            out.append(f"  {tag} {key} {val}")
        out += ["  " + r for r in n.raw]
        out.append("end")
    for w in g.wires:
        out += w["pre"]
        out.append(" ".join([w["tag"], w["dst"], w["slot"], w["src"]] + w["rest"]))
    for e in g.extras:
        out += e["pre"]
        out.append(e["line"])
    return "\n".join(out) + "\n"
