#!/usr/bin/env python3
"""Publish extension packs: build extensions.json and upload it with the pack zips to the `extensions` release.

What: the app reads its pack catalog from one fixed release tag, `extensions`
(src/core/Extensions.cpp kCatalogUrl), so packs and app releases ship independently. This tool turns a folder
of pack zips into the catalog (SHA-256, size, URLs) and, with --publish, uploads everything to that release.
Why: the catalog used to ride on whichever app release was "latest"; cutting a new app release without it left
every user's Extensions tab empty.

Input: a folder of  <id>-<platform>.zip  (platform = macos | windows-x64 | windows-arm64 | linux-x64), each zip
with a pack.json {"id","version"} at its root. Name and purpose per pack come from tools/release/packs.json.
Files are uploaded as <id>-<version>-<platform>.zip, so an older catalog's SHA-256 never meets a newer zip.

Usage:
    python3 tools/release/publish_extensions.py PACKDIR                 # build ./extensions.json, print what would upload
    python3 tools/release/publish_extensions.py PACKDIR --publish       # upload to the `extensions` release (needs gh)
    python3 tools/release/publish_extensions.py PACKDIR --publish --also-latest
                                                                        # also attach extensions.json to the latest app
                                                                        # release, for apps that predate the fixed tag
    python3 tools/release/publish_extensions.py --verify                # fetch the live catalog, check every file's SHA-256
"""
import argparse, hashlib, json, os, subprocess, sys, tempfile, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "n1m21n/Infinite"
TAG = "extensions"
PLATFORMS = ("macos", "windows-x64", "windows-arm64", "linux-x64")
BASE = f"https://github.com/{REPO}/releases/download/{TAG}"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(packdir):
    meta = json.load(open(os.path.join(HERE, "packs.json")))
    packs, uploads = {}, []
    for fn in sorted(os.listdir(packdir)):
        if not fn.endswith(".zip"):
            continue
        stem = fn[:-4]
        pid, _, plat = stem.partition("-")
        # ids may not contain '-'; platform keys do ("windows-x64")
        if plat not in PLATFORMS:
            sys.exit(f"{fn}: expected <id>-<platform>.zip with platform one of {', '.join(PLATFORMS)}")
        path = os.path.join(packdir, fn)
        with zipfile.ZipFile(path) as z:
            pj = json.loads(z.read("pack.json"))
        if pj.get("id") != pid:
            sys.exit(f"{fn}: pack.json id {pj.get('id')!r} does not match the file name")
        p = packs.setdefault(pid, {"id": pid, "version": pj["version"], "size": 0, "files": {}})
        if p["version"] != pj["version"]:
            sys.exit(f"{pid}: platform zips disagree on version ({p['version']} vs {pj['version']})")
        up = f"{pid}-{pj['version']}-{plat}.zip"
        p["files"][plat] = {"url": f"{BASE}/{up}", "sha256": sha256(path)}
        p["size"] = max(p["size"], os.path.getsize(path))
        uploads.append((path, up))
    if not packs:
        sys.exit(f"no <id>-<platform>.zip files in {packdir}")
    out = []
    for pid, p in packs.items():
        m = meta.get(pid)
        if not m:
            sys.exit(f"{pid}: add name and purpose to tools/release/packs.json")
        out.append({"id": pid, "name": m["name"], "purpose": m["purpose"], "version": p["version"],
                    "size": p["size"], "files": p["files"]})
    return {"schema": 1, "packs": out}, uploads


def gh(*args):
    subprocess.run(["gh", *args, "--repo", REPO], check=True)


def publish(catalog, uploads, also_latest):
    cat = os.path.join(tempfile.mkdtemp(), "extensions.json")
    json.dump(catalog, open(cat, "w"), indent=1)
    if subprocess.run(["gh", "release", "view", TAG, "--repo", REPO], capture_output=True).returncode != 0:
        gh("release", "create", TAG, "--title", "Extensions",
           "--notes", "Extension packs and the catalog Infinite reads in Settings > Extensions. Updated independently of app releases.",
           "--latest=false", "--prerelease=false")
    # zips first, catalog last: the catalog never points at a file that is not there yet
    for path, name in uploads:
        tmp = os.path.join(tempfile.mkdtemp(), name)
        os.symlink(os.path.abspath(path), tmp)
        gh("release", "upload", TAG, tmp, "--clobber")
    gh("release", "upload", TAG, cat, "--clobber")
    if also_latest:
        latest = subprocess.run(["gh", "release", "view", "--repo", REPO, "--json", "tagName", "--jq", ".tagName"],
                                capture_output=True, text=True, check=True).stdout.strip()
        gh("release", "upload", latest, cat, "--clobber")
        print(f"also attached extensions.json to {latest} (apps before the fixed tag read it there)")


def verify():
    with urllib.request.urlopen(f"{BASE}/extensions.json") as r:
        cat = json.load(r)
    bad = 0
    for p in cat["packs"]:
        for plat, f in p["files"].items():
            h = hashlib.sha256()
            with urllib.request.urlopen(f["url"]) as r:
                for chunk in iter(lambda: r.read(1 << 20), b""):
                    h.update(chunk)
            ok = h.hexdigest() == f["sha256"]
            bad += not ok
            print(("ok   " if ok else "BAD  ") + f"{p['id']} {p['version']} {plat}")
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packdir", nargs="?")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--also-latest", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        verify()
    if not a.packdir:
        ap.error("PACKDIR required unless --verify")
    catalog, uploads = build(a.packdir)
    out = os.path.join(os.getcwd(), "extensions.json")
    json.dump(catalog, open(out, "w"), indent=1)
    print(f"wrote {out}")
    for _, name in uploads:
        print(f"  {'upload' if a.publish else 'would upload'} {name}")
    if a.publish:
        publish(catalog, uploads, a.also_latest)
        print("published; run with --verify to check the live files")


main()
