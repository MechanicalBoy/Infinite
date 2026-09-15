#!/usr/bin/env python3
"""
recover_git_docs.py
Scans Git tree history to find and extract all deleted and historical documentation,
plans, and prompts (e.g. docs/plans/**, docs/prompts/**, old skills) from the Git object database.
"""

import json
import os
import subprocess
from pathlib import Path

REPO_PATH = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "recovered_docs_corpus.json"

def run_cmd(cmd):
    res = subprocess.run(cmd, cwd=REPO_PATH, shell=True, capture_output=True, text=True)
    return res.stdout.strip()

def recover_docs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Scanning Git object history for historical docs and prompts...")
    
    # Find all deleted paths that were in docs/plans or docs/prompts or .claude/skills
    cmd = 'git log --diff-filter=D --summary | grep "delete mode" | awk \'{print $4}\''
    deleted_files = list(set([line.strip() for line in run_cmd(cmd).split("\n") if line.strip()]))
    
    # Filter for docs, plans, skills, prompts
    target_deleted = [
        f for f in deleted_files 
        if f.startswith("docs/plans/") or f.startswith("docs/prompts/") or f.startswith(".claude/skills/") or f.endswith(".md")
    ]
    
    print(f"Found {len(target_deleted)} deleted markdown/doc files in Git history.")
    
    recovered = []
    for file_path in target_deleted:
        # Find commit where file was deleted
        del_commit = run_cmd(f'git log -1 --diff-filter=D --pretty=format:"%H" -- "{file_path}"')
        if del_commit:
            # Show file from the commit right before deletion (del_commit^)
            content = run_cmd(f'git show {del_commit}^:"{file_path}"')
            if content and not content.startswith("fatal:"):
                commit_info = run_cmd(f'git log -1 --pretty=format:"%an|%ad|%s" {del_commit}^')
                recovered.append({
                    "path": file_path,
                    "deleted_in_commit": del_commit,
                    "commit_info": commit_info,
                    "content": content
                })
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(recovered, f, indent=2)
        
    print(f"Successfully recovered {len(recovered)} historical docs & prompts into {OUTPUT_FILE}")

if __name__ == "__main__":
    recover_docs()
