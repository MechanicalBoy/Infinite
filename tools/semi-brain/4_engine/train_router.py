#!/usr/bin/env python3
"""
train_router.py
Automated LoRA fine-tuning for the local router model using Apple's MLX-LM.
Trains Qwen/Qwen2.5-0.5B-Instruct on the distilled Semi-Brain dataset.
"""

import sys
import subprocess
from pathlib import Path

SEMI_BRAIN_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SEMI_BRAIN_DIR / "3_datasets" / "mlx_data"
ADAPTER_DIR = SEMI_BRAIN_DIR / "4_engine" / "router_adapter"

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

def train():
    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Prepare MLX splits
    prep_script = SEMI_BRAIN_DIR / "3_datasets" / "prepare_mlx_dataset.py"
    print("Preparing MLX training splits...")
    subprocess.run(["python3", str(prep_script)], check=True)
    
    # 2. Run MLX-LM LoRA training
    print(f"🚀 Starting LoRA fine-tuning on Apple Metal (Base: {BASE_MODEL})...")
    
    cmd = [
        "python3", "-m", "mlx_lm", "lora",
        "--model", BASE_MODEL,
        "--train",
        "--data", str(DATA_DIR),
        "--adapter-path", str(ADAPTER_DIR),
        "--iters", "200",
        "--batch-size", "4",
        "--num-layers", "8",
        "--learning-rate", "1e-4",
        "--steps-per-report", "20",
        "--save-every", "50",
        "--max-seq-length", "512"
    ]
    
    subprocess.run(cmd, check=True)
    print(f"✅ Training completed! LoRA adapter saved to: {ADAPTER_DIR}")

if __name__ == "__main__":
    train()
