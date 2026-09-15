#!/usr/bin/env python3
"""
ingest_build_your_own_x.py
Ingests and structures the architectural blueprints from codecrafters-io/build-your-own-x
relevant to Infinite (3D Renderers, Audio Synthesizers, Compilers, Game Engines, Physics, Git).
"""

import json
import os
import re
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "build_your_own_x_corpus.json"
DISTILLED_FILE = Path(__file__).resolve().parents[1] / "2_distilled_brain" / "first_principles_blueprints.md"

GITHUB_RAW_URL = "https://raw.githubusercontent.com/codecrafters-io/build-your-own-x/master/README.md"

RELEVANT_CATEGORIES = [
    "3D Renderer",
    "Audio / Music",
    "Command-Line Tool",
    "Compiler",
    "Programming Language",
    "Game Engine",
    "Game",
    "Git",
    "Operating System",
    "Physics Engine",
    "Regex Engine",
    "Shell",
    "Virtual Machine",
    "Voxel Game"
]

def fetch_and_parse_byox():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching build-your-own-x repository from GitHub...")
    
    req = urllib.request.Request(
        GITHUB_RAW_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        
    print(f"Fetched README ({len(content)} chars). Parsing domain categories...")
    
    # Split on: #### Build your own `Category`
    category_chunks = re.split(r"####\s+Build your own\s+[`\"']?([^`\"'\n]+)[`\"']?", content)
    
    parsed_blueprints = []
    
    # category_chunks has format: [preamble, cat1_name, cat1_body, cat2_name, cat2_body, ...]
    for i in range(1, len(category_chunks), 2):
        cat_name = category_chunks[i].strip()
        cat_body = category_chunks[i+1].strip() if i+1 < len(category_chunks) else ""
        
        is_relevant = any(c.lower() in cat_name.lower() for c in RELEVANT_CATEGORIES)
        if not is_relevant:
            continue
            
        tutorials = []
        for line in cat_body.split("\n"):
            line_str = line.strip()
            if line_str.startswith("*") or line_str.startswith("-"):
                # Extract markdown links: [Title](URL)
                links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", line_str)
                if links:
                    title, url = links[0]
                    # Extract language tag like **C++**
                    lang_match = re.search(r"\*\*([^*]+)\*\*", line_str)
                    lang = lang_match.group(1) if lang_match else "General"
                    tutorials.append({
                        "language": lang,
                        "title": title,
                        "url": url,
                        "entry": line_str
                    })
                    
        parsed_blueprints.append({
            "category": cat_name,
            "tutorial_count": len(tutorials),
            "tutorials": tutorials
        })
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(parsed_blueprints, f, indent=2)
        
    print(f"Extracted {len(parsed_blueprints)} relevant architectural domains into {OUTPUT_FILE}")
    
    # Generate distilled first principles document
    distilled_doc = """# First-Principles Architectural Blueprints (from build-your-own-x)

This distilled knowledge base grounds the Semi-Brain in canonical, from-scratch systems engineering across Infinite's primary technical domains.

---

"""
    for bp in parsed_blueprints:
        distilled_doc += f"## 🏗 Domain: {bp['category']} ({bp['tutorial_count']} Canonical Blueprints)\n\n"
        distilled_doc += "### Core Architectural Invariants:\n"
        if "3D" in bp['category'] or "Render" in bp['category']:
            distilled_doc += "- **Pipeline Order**: Local Space -> World Matrix -> View Transform -> Projection Matrix -> Viewport Rasterization.\n- **Depth & Shading Invariant**: Perspective-correct interpolation of barycentric UVs and normals; depth buffer monotonic z-sorting.\n\n"
        elif "Audio" in bp['category'] or "Music" in bp['category']:
            distilled_doc += "- **Realtime DSP Invariant**: Zero heap allocation in callback; phase accumulator continuity across sample blocks; SPSC lock-free parameter delivery.\n\n"
        elif "Compiler" in bp['category'] or "Programming Language" in bp['category'] or "Virtual Machine" in bp['category']:
            distilled_doc += "- **Compilation Pipeline**: Lexer (Token Stream) -> Parser (AST) -> Type Checker / Domain Inference -> Typed IR -> Target Code (GLSL / Bytecode).\n\n"
        elif "Git" in bp['category']:
            distilled_doc += "- **DAG & Object Model**: Immutable content-addressed blobs, trees, and commit DAG; monotonic state transitions.\n\n"
        else:
            distilled_doc += "- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.\n\n"
            
        distilled_doc += "### Reference Blueprints:\n"
        for t in bp['tutorials'][:8]:
            distilled_doc += f"- **[{t['language']}]** {t['title']} — `{t['url']}`\n"
        distilled_doc += "\n---\n\n"
        
    DISTILLED_FILE.write_text(distilled_doc, encoding="utf-8")
    print(f"Generated first-principles architectural schema in {DISTILLED_FILE}")

if __name__ == "__main__":
    fetch_and_parse_byox()
