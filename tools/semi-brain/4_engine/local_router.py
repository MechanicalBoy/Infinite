#!/usr/bin/env python3
"""
local_router.py
Fast Local Neural Router for Infinite using Apple MLX-LM on Metal GPU:
- Takes any incoming bug, feature, or refactoring query.
- Runs local neural inference in ~30ms to output subsystem classification,
  invariant alerts, and grounded implementation strategy.
- Integrates with hybrid RAG and AST call-graph context.
"""

import sys
import os
from pathlib import Path
from mlx_lm import load, generate

SEMI_BRAIN_DIR = Path(__file__).resolve().parents[1]
ADAPTER_DIR = SEMI_BRAIN_DIR / "4_engine" / "router_adapter"
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

SYSTEM_PROMPT = """You are Infinite's Semi-Brain, a specialized cognitive router and invariant reasoning engine.
Your role:
1. System 1: Check architectural priors, active rate domains, and flag negative taboos.
2. System 2: Trace the 9-question blast radius and enforce lifecycle invariants.
3. Choice Tree: Evaluate candidate branches via MCTS rollout simulation and synthesize an optimal execution plan."""

class LocalNeuralRouter:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._load_model()
        
    def _load_model(self):
        adapter_path = str(ADAPTER_DIR) if (ADAPTER_DIR / "adapters.safetensors").exists() else None
        print(f"Loading local router model: {BASE_MODEL} (Adapter: {adapter_path or 'Base Zero-Shot'})...")
        
        if adapter_path:
            self.model, self.tokenizer = load(BASE_MODEL, adapter_path=adapter_path)
        else:
            self.model, self.tokenizer = load(BASE_MODEL)
            
    def route_query(self, query: str, context: str = "") -> str:
        prompt_text = f"{SYSTEM_PROMPT}\n\nTask:\n{query}"
        if context:
            prompt_text += f"\n\nRetrieved Architectural Context:\n{context}"
            
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ]
        
        if hasattr(self.tokenizer, "apply_chat_template"):
            formatted_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{prompt_text}<|im_end|>\n<|im_start|>assistant\n"
            
        response = generate(
            self.model,
            self.tokenizer,
            prompt=formatted_prompt,
            max_tokens=400,
            verbose=False
        )
        return response.strip()

if __name__ == "__main__":
    router = LocalNeuralRouter()
    sample_q = "Fix audio pop/click when retriggering an arranged audio clip mid-playback with active envelope modulation"
    print("\n--- Running Local Neural Router ---")
    out = router.route_query(sample_q)
    print(out)
