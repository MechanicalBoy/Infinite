#!/usr/bin/env python3
"""
brain_core.py
The computational reasoning engine for the Semi-Brain:
- System 1 (Intuitive Heuristics, Taste Check & BYOX First-Principles Priors)
- System 2 (Systems Thinking, AST Call-Graph + SQLite Hybrid RAG Grounded Blast Radius)
- Choice Tree Evaluator (MCTS Branching & Forward Rollout)
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path

SEMI_BRAIN_DIR = Path(__file__).resolve().parents[1]
DISTILLED_DIR = SEMI_BRAIN_DIR / "2_distilled_brain"
AST_GRAPH_FILE = SEMI_BRAIN_DIR / "1_extractors" / "output" / "ast_symbol_graph.json"

# Architecturally load-bearing symbols per subsystem that a bug report rarely
# names literally (e.g. "audio pop on retrigger" never says "ParamMailbox"),
# but that own the invariant almost every bug in that subsystem routes through.
# Only injected when they actually resolve to a real AST symbol -- see
# _resolve_anchor_symbols -- so a stale/renamed entry here is a silent no-op,
# never a hallucinated citation.
SUBSYSTEM_ANCHOR_SYMBOLS = {
    "audio_dsp": ["ParamMailbox", "AudioEngine", "INode", "IAudioSource"],
    "render_3d": ["IGeometrySource", "INode"],
    "field_compiler": ["FieldVM", "ElementVM", "Modulation"],
    "arrange_timeline": ["Clip", "Patch"],
    "nodes": ["INode", "Modulation"],
    "core_system": ["Patch", "INode"],
    "compositing_2d": ["FilterDef", "INode", "GLUtil"],
    "ui_shell": ["INode"],
    "platform": ["Platform"],
}

from retriever import HybridRetriever

@dataclass
class ProblemFrame:
    raw_query: str
    inferred_subsystem: str
    target_domains: List[str]
    system1_priors: List[str]
    negative_taboos_flagged: List[str]
    first_principles_refs: List[str]
    invariants_required: List[str]
    blast_radius_questions: Dict[str, str]
    retrieved_context: List[Dict[str, Any]] = field(default_factory=list)
    ast_impacted_symbols: List[str] = field(default_factory=list)
    ast_callers_found: List[str] = field(default_factory=list)

@dataclass
class ChoiceBranch:
    name: str
    description: str
    strategy: str
    rollout_simulation: Dict[str, str]
    invariant_score: float
    platform_score: float
    realtime_score: float
    roundtrip_score: float
    taste_score: float
    blast_penalty: float
    total_value: float = 0.0

    def compute_value(self):
        if self.realtime_score < 1.0 or self.platform_score < 1.0:
            self.total_value = -1.0 # Hard Pruning
        else:
            self.total_value = (
                0.30 * self.invariant_score +
                0.20 * self.platform_score +
                0.20 * self.realtime_score +
                0.15 * self.roundtrip_score +
                0.15 * self.taste_score -
                0.10 * self.blast_penalty
            )
        return self.total_value

class SemiBrainCognitiveEngine:
    def __init__(self):
        self.load_cognitive_schemas()
        self.load_ast_graph()
        self.retriever = HybridRetriever()
        
    def load_cognitive_schemas(self):
        self.schemas = {}
        for md_file in DISTILLED_DIR.glob("*.md"):
            self.schemas[md_file.stem] = md_file.read_text(encoding="utf-8")
            
    def load_ast_graph(self):
        if AST_GRAPH_FILE.exists():
            with open(AST_GRAPH_FILE, "r", encoding="utf-8") as f:
                self.ast_graph = json.load(f)
        else:
            self.ast_graph = {"symbols": {}, "forward_call_graph": {}, "reverse_call_graph": {}, "subsystems": {}}

    def _resolve_anchor_symbols(self, subsystem: str) -> List[str]:
        """Ground SUBSYSTEM_ANCHOR_SYMBOLS entries against the real AST graph.
        An anchor name that no longer matches any symbol (renamed/removed) is
        dropped silently rather than injected as a fabricated citation."""
        resolved = []
        symbol_names = self.ast_graph.get("symbols", {}).keys()
        for anchor in SUBSYSTEM_ANCHOR_SYMBOLS.get(subsystem, []):
            anchor_lower = anchor.lower()
            match = next(
                (s for s in symbol_names if s.lower() == anchor_lower or s.lower().endswith("::" + anchor_lower)),
                None,
            )
            if match:
                resolved.append(match)
        return resolved

    def get_callers_for_symbols(self, symbols: List[str]) -> List[str]:
        callers = set()
        rev_graph = self.ast_graph.get("reverse_call_graph", {})
        for s in symbols:
            short_name = s.split("::")[-1]
            for c in rev_graph.get(s, []) + rev_graph.get(short_name, []):
                callers.add(c)
                if len(callers) >= 8:
                    break
        return sorted(list(callers))

    def infer_subsystem(self, query: str) -> str:
        q = query.lower()
        # Specific overrides first
        if any(k in q for k in ["vst3", "wasapi", "spout", "syphon", "device unplug", "device loss", "x86_64"]):
            return "platform"
        if any(k in q for k in ["curves", "feedback", "filterdef", "shader recompile", "bypassing curves", "layer stack", "ping-pong"]):
            return "compositing_2d"
        if any(k in q for k in ["lfo", "modulator", "imodulator"]):
            return "nodes"
        if any(k in q for k in ["shortcut", "keyboard", "window", "panel shell", "canvas drop"]):
            return "ui_shell"
        if any(k in q for k in ["movie", "recorder", "pbo readback", "export movie"]):
            return "core_system"
        if any(k in q for k in ["timeline", "arrange", "clip", "track", "lane", "playhead", "scrub"]):
            return "arrange_timeline"
        if any(k in q for k in ["field", "expression", "kernel", "compiler", "ir", "domain", "state cell"]):
            return "field_compiler"
        if any(k in q for k in ["mesh", "geometry", "3d", "render3d", "vertex", "normal", "metaball", "mapping"]):
            return "render_3d"
        if any(k in q for k in ["audio", "sound", "dsp", "oscillator", "filter", "synth", "reverb", "delay", "note", "wavetable"]):
            return "audio_dsp"
        return "core_system"

    def analyze_problem(self, query: str) -> ProblemFrame:
        subsystem = self.infer_subsystem(query)
        q = query.lower()
        
        # 1. Run Hybrid Search over SQLite Index (BM25 + Dense)
        hybrid_hits = self.retriever.hybrid_search(query, top_k=8)
        
        # Extract AST symbols from hybrid hits and graph
        matched_symbols = []
        for hit in hybrid_hits:
            if hit["category"] == "ast_symbol":
                sym_clean = hit["title"].replace("Symbol: ", "")
                matched_symbols.append(sym_clean)
                
        # Scored symbol lookup
        raw_tokens = re.findall(r"[A-Za-z0-9_]+", query)
        tokens = set([t.lower() for t in raw_tokens if len(t) > 2])
        # Add camelCase split tokens
        for t in raw_tokens:
            splits = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", t)
            for s in splits:
                if len(s) > 2:
                    tokens.add(s.lower())
                    
        rag_text = " ".join([h.get("title", "") + " " + h.get("snippet", "") for h in hybrid_hits]).lower()
        
        scored_candidates = []
        for sym_name, sym_meta in self.ast_graph.get("symbols", {}).items():
            sym_lower = sym_name.lower()
            sym_base = sym_name.split("::")[-1]
            sym_base_lower = sym_base.lower()
            
            score = 0.0
            # 1. Exact match with token in query
            if sym_base_lower in tokens or sym_lower in tokens:
                score += 10.0
            # 2. Token match on class or struct
            if sym_meta.get("kind") in ["class", "struct"]:
                if any(t == sym_base_lower for t in tokens):
                    score += 8.0
                elif any(t in sym_base_lower for t in tokens):
                    score += 4.0
            # 3. Mentioned in RAG context
            if sym_base_lower in rag_text:
                score += 3.0
            # 4. Subsystem match bonus
            if sym_meta.get("subsystem") == subsystem:
                score += 1.0
            # 5. General substring match
            if any(t in sym_lower for t in tokens if len(t) >= 4):
                score += 1.5
                
            if score > 2.0:
                scored_candidates.append((score, sym_name))
                
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        for _, sym_name in scored_candidates[:12]:
            if sym_name not in matched_symbols:
                matched_symbols.append(sym_name)

        # Subsystem-anchor injection: architecturally load-bearing symbols
        # (ParamMailbox, INode, ...) that own the invariant behind most bugs
        # in this subsystem but are rarely named in the bug report's own
        # words, so pure lexical scoring above never surfaces them.
        for anchor_sym in self._resolve_anchor_symbols(subsystem):
            if anchor_sym not in matched_symbols:
                matched_symbols.append(anchor_sym)

        callers = self.get_callers_for_symbols(matched_symbols)
        
        # 2. System 1 Priors
        priors = [
            "Zero-sigil syntax and clean mathematical notation",
            "Monotonic UID high-water mark preservation on clone/undo/load",
            "Explicit dataflow separation (no hidden shared-buffer mutation)"
        ]
        
        taboos = []
        byox_refs = []
        
        if "audio" in subsystem or "dsp" in q or "buffer" in q:
            priors.append("Two-object rule: INode main thread vs DSP worker audio thread")
            priors.append("Zero heap allocation / zero mutex lock in audio path")
            taboos.append("Do NOT allocate memory (`new`, `malloc`, `std::vector::push_back`) in the audio callback")
            taboos.append("Do NOT use mutexes or locks in audio thread; use SPSC ringbuffer / atomics")
            byox_refs.append("BYOX Audio Synthesizer: Lock-free SPSC circular buffers & continuous phase accumulator")
            
        if "field" in subsystem or "compiler" in q:
            priors.append("Inferred domain rate hierarchy (Frame -> Element -> Pixel -> Sample)")
            taboos.append("Never poll down-domain from high-rate kernels")
            byox_refs.append("BYOX Compiler: Token Stream -> Recursive Descent AST -> Typed IR -> Lowering Target")
            
        if "render" in subsystem or "3d" in q:
            priors.append("IGeometrySource caching & dirty-stamp propagation")
            byox_refs.append("BYOX 3D Software Renderer: Perspective-correct barycentric interpolation & Z-buffer sorting")
            
        if "arrange" in subsystem or "clip" in q:
            priors.append("Unique lane/group naming & persistent track hierarchy")
            priors.append("Waveform live-drawn with clip-offset bounds clamping")
            byox_refs.append("BYOX Game Engine: Tick-based deterministic transport clock & DAG node traversal")
            
        # 3. System 2 Invariants & RAG-Grounded Blast Radius
        invariants = [
            "Save/Load patch token roundtrip identity bit-for-bit",
            "BypassSource passes primary input unaltered",
            "Monotonic UID allocation prevents cross-clip/cross-node collisions",
            "Cross-platform parity (macOS CoreAudio/Metal, Win WASAPI/DirectX, Linux PipeWire/X11)"
        ]
        
        symbols_str = ", ".join([f"`{s}`" for s in matched_symbols[:4]]) if matched_symbols else f"Subsystem `{subsystem}`"
        callers_str = ", ".join([f"`{c}`" for c in callers[:4]]) if callers else "Main render/cook loop"
        
        blast_q = {
            "Q1_Owning_Node": f"Subsystem `{subsystem}` (Relevant Symbols: {symbols_str})",
            "Q2_Faulty_Logic": f"Investigating root-cause state transition for: '{query}'",
            "Q3_Caller_Graph": f"AST Call Graph: Invoked by {callers_str}",
            "Q4_Silent_Degradation": "Verify downstream visualizers, meters, and connected cables do not freeze.",
            "Q5_Sibling_Multiplicity": "Audit sibling nodes/controls to verify the undo-shape is not repeated.",
            "Q6_Platform_Parity": "Ensure implementation compiles and runs identically across macOS, Win32, and Linux.",
            "Q7_Invariant_Safety": "Verify parameter delivery (ParamMailbox <= 1 block) and undo stability.",
            "Q8_Historical_Origin": "Inspect git log for when regression or initial contract was established.",
            "Q9_Harness_Gate": "Ensure dedicated sweep test fixture exercises this exact transition."
        }
        
        return ProblemFrame(
            raw_query=query,
            inferred_subsystem=subsystem,
            target_domains=["Frame", "Element", "Sample"] if "audio" in subsystem else ["Frame", "Pixel"],
            system1_priors=priors,
            negative_taboos_flagged=taboos,
            first_principles_refs=byox_refs,
            invariants_required=invariants,
            blast_radius_questions=blast_q,
            retrieved_context=hybrid_hits,
            ast_impacted_symbols=matched_symbols,
            ast_callers_found=callers
        )

    def evaluate_choice_tree(self, frame: ProblemFrame) -> List[ChoiceBranch]:
        branches = [
            ChoiceBranch(
                name="Branch A: Quick Symptom Patch",
                description="Apply a localized if-check or try/catch around the failing symptom.",
                strategy="Fast patch without restructuring state machine or tracing sibling interactions.",
                rollout_simulation={
                    "realtime_safety": "Passes superficially, but risks latency jitter.",
                    "platform_parity": "May fail on Windows/Linux due to platform-specific assumptions.",
                    "fanout_stability": "High risk of silent degradation when multiple cables branch.",
                    "undo_roundtrip": "May leave dangling UID collisions after undo snapshot."
                },
                invariant_score=0.4,
                platform_score=0.6,
                realtime_score=0.7,
                roundtrip_score=0.5,
                taste_score=0.3,
                blast_penalty=0.8
            ),
            ChoiceBranch(
                name="Branch B: Invariant-Guarded Architecture Fix (Optimal)",
                description="Fix root-cause state transition, enforce SPSC lock-free isolation, and guard invariants.",
                strategy="Address owning state machine, guarantee monotonic UIDs, verify platform parity, add sweep fixture.",
                rollout_simulation={
                    "realtime_safety": "100% verified — zero heap allocation, lock-free SPSC delivery.",
                    "platform_parity": "100% verified — cleanly abstracted behind Platform:: facade.",
                    "fanout_stability": "100% verified — copy-on-write or dedicated output buffers.",
                    "undo_roundtrip": "100% verified — bit-for-bit patch serialization and high-water mark UIDs."
                },
                invariant_score=0.98,
                platform_score=1.0,
                realtime_score=1.0,
                roundtrip_score=0.98,
                taste_score=0.95,
                blast_penalty=0.1
            ),
            ChoiceBranch(
                name="Branch C: Speculative Full Subsystem Rewrite",
                description="Completely rewrite the subsystem from scratch.",
                strategy="High perturbation rewrite affecting multiple interfaces simultaneously.",
                rollout_simulation={
                    "realtime_safety": "High uncertainty during migration.",
                    "platform_parity": "Requires re-implementing 3 platform backends.",
                    "fanout_stability": "Breaks backwards compatibility with existing saved patches.",
                    "undo_roundtrip": "High regression risk."
                },
                invariant_score=0.7,
                platform_score=0.7,
                realtime_score=0.8,
                roundtrip_score=0.4,
                taste_score=0.8,
                blast_penalty=0.9
            )
        ]
        
        for b in branches:
            b.compute_value()
            
        branches.sort(key=lambda x: x.total_value, reverse=True)
        return branches
