import re, json, subprocess, sys, html
SRC = "/Users/namansoni/Infinite/worktrees/main/tools/manual/base/chapters_1_20.pdf"
txt = subprocess.run(["pdftotext","-layout",SRC,"-"],capture_output=True,text=True).stdout
lines = []
for l in txt.replace("\f","\n").split("\n"):
    s = l.strip()
    if re.match(r"^CHAPTER \d+ — ", s) or s == "INFINITE · NODE FIELD GUIDE": continue
    lines.append(l.rstrip())
WORDS = "One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen Twenty".split()
chs = []; cur = None; i = 0
def join(ls): return html.unescape(" ".join(x.strip() for x in ls if x.strip()))
while i < len(lines):
    s = lines[i].strip()
    m = re.match(r"^Chapter (\w+)$", s)
    if m and m.group(1) in WORDS:
        cur = dict(n=WORDS.index(m.group(1))+1, num=m.group(1), title="", intro=[], cards=[], rows=[], notes=[])
        chs.append(cur); i += 1
        while not lines[i].strip(): i += 1
        cur["title"] = lines[i].strip(); i += 1
        state = "intro"; continue
    if cur is None or not s: i += 1; continue
    hm = re.match(r"^(\S.*?)\s{3,}([A-Z0-9][A-Z0-9 /&+,\-]*(?: · [A-Z0-9 /&+,\-]+)+)$", lines[i].strip())
    if hm and "·" in hm.group(2):
        name, tag = hm.group(1), hm.group(2); i += 1
        desc = []; tryl = []; chain = ""
        while i < len(lines) and not lines[i].strip().startswith("Try it"):
            if lines[i].strip(): desc.append(lines[i])
            i += 1
        if i < len(lines):
            while i < len(lines) and lines[i].strip():
                tryl.append(lines[i]); i += 1
            while i < len(lines) and not lines[i].strip(): i += 1
            if i < len(lines) and not re.match(r"^Chapter \w+$", lines[i].strip()) and not re.match(r"^\S.*\s{3,}[A-Z0-9 ]+ · ", lines[i].strip()):
                chain = lines[i].strip(); i += 1
        t = join(tryl); t = re.sub(r"^Try it\s*[—-]\s*", "", t)
        ch = [c.strip() for c in re.split(r"\s*→\s*", chain)] if chain else []
        cur["cards"].append((html.unescape(name), tag, join(desc), t, ch)); continue
    # two-column table row: name then >=2 spaces then text
    rm = re.match(r"^(\S[^ ]*(?: [^ ]+)*?)\s{3,}(\S.*)$", lines[i].strip()) if (len(lines[i]) - len(lines[i].lstrip())) <= 4 and re.match(r"^\S.*?\s{3,}\S", lines[i].strip()) else None
    if rm and cur["cards"] == [] or (rm and (len(lines[i]) - len(lines[i].lstrip())) == 0 and len(rm.group(1)) < 32):
        name, d = rm.group(1), [rm.group(2)]; i += 1
        while i < len(lines) and lines[i].strip() and (len(lines[i]) - len(lines[i].lstrip())) > 15:
            d.append(lines[i]); i += 1
        cur["rows"].append((name, join(d))); continue
    # prose
    p = [lines[i]]; i += 1
    while i < len(lines) and lines[i].strip():
        p.append(lines[i]); i += 1
    (cur["intro"] if not cur["cards"] and not cur["rows"] else cur["notes"]).append(join(p))
json.dump(chs, open("/tmp/ex/base.json","w"), indent=1, ensure_ascii=False)
tot = 0
for c in chs:
    print(c["n"], c["title"], "| cards", len(c["cards"]), "rows", len(c["rows"]), "intro", len(c["intro"]), "notes", len(c["notes"]))
    tot += len(c["cards"]) + len(c["rows"])
print("total", tot)
