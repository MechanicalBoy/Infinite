#!/usr/bin/env python3
"""
prepare_mlx_dataset.py
Formats the 1,137 SFT samples into standard MLX-LM train.jsonl and valid.jsonl chat format:
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
"""

import json
import random
from pathlib import Path

DATASETS_DIR = Path(__file__).resolve().parent
ALPACA_FILE = DATASETS_DIR / "train_sft_alpaca.jsonl"
MLX_DIR = DATASETS_DIR / "mlx_data"

SYSTEM_PROMPT = """You are Infinite's Semi-Brain, a specialized cognitive router and invariant reasoning engine.
Your role:
1. System 1: Check architectural priors, active rate domains, and flag negative taboos.
2. System 2: Trace the 9-question blast radius and enforce lifecycle invariants.
3. Choice Tree: Evaluate candidate branches via MCTS rollout simulation and synthesize an optimal execution plan."""

def prepare_mlx_data():
    MLX_DIR.mkdir(parents=True, exist_ok=True)
    if not ALPACA_FILE.exists():
        print(f"Error: {ALPACA_FILE} not found. Run compile_training_data.py first.")
        return
        
    samples = []
    with open(ALPACA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line.strip()))
                
    print(f"Loaded {len(samples)} SFT samples. Formatting into MLX chat records...")
    
    chat_records = []
    for s in samples:
        user_msg = s.get("instruction", "").strip()[:800]
        assistant_msg = s.get("output", "").strip()[:1200]
        
        if not user_msg or not assistant_msg:
            continue
            
        chat_records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg}
            ]
        })
        
    # Deterministic train/test split (90% train, 10% validation)
    random.seed(42)
    random.shuffle(chat_records)
    
    split_idx = int(len(chat_records) * 0.90)
    train_records = chat_records[:split_idx]
    valid_records = chat_records[split_idx:]
    
    train_file = MLX_DIR / "train.jsonl"
    valid_file = MLX_DIR / "valid.jsonl"
    
    with open(train_file, "w", encoding="utf-8") as f:
        for r in train_records:
            f.write(json.dumps(r) + "\n")
            
    with open(valid_file, "w", encoding="utf-8") as f:
        for r in valid_records:
            f.write(json.dumps(r) + "\n")
            
    print(f"✅ MLX Dataset ready!")
    print(f"Train split: {len(train_records)} samples -> {train_file}")
    print(f"Valid split: {len(valid_records)} samples -> {valid_file}")

if __name__ == "__main__":
    prepare_mlx_data()
