---
name: semi-brain
description: The Cognitive Twin and Invariant Reasoning Engine for Infinite. Use at the start of ANY task (bug fix, feature implementation, refactoring, code review) to frame the problem through System 1 intuition, System 2 9-question blast radius, and Choice Tree MCTS rollouts. Also use after completing a task to record newly discovered invariants or user corrections into the self-improving training dataset.
category: Core
---

# Semi-Brain: Cognitive Twin & Invariant Engine

The Semi-Brain encodes Infinite's core engineering reflexes: System 1 (Intuitive taste, zero-sigil clarity, realtime safety, UI symmetry), System 2 (Systems thinking, 9-question blast radius, invariant interaction audit), and Choice Tree MCTS rollouts.

---

## 1. When to Consult the Semi-Brain

You must consult the Semi-Brain:
1. **At the start of any non-trivial task**: Before proposing or modifying code, run the engine or inspect the distilled schemas in `tools/semi-brain/2_distilled_brain/`.
2. **When framing a bug or feature**: To evaluate the 9-question blast radius, platform parity risks, and realtime thread constraints.
3. **When evaluating multiple design approaches**: To simulate forward rollouts across teardown, fanout, save/load identity, and transport clocks.

---

## 2. How to Run the Semi-Brain from CLI

To get an immediate architectural breakdown and invariant brief for any task:
```bash
# Cognitive reasoning analysis (RAG + AST + System 1/2 + MCTS Choice Tree):
python3 tools/semi-brain/4_engine/semi_brain_cli.py "<description of bug or feature>"

# Fast Apple Metal Local Neural Router (LoRA fine-tuned Qwen2.5-0.5B):
python3 tools/semi-brain/4_engine/semi_brain_cli.py "<description of bug or feature>" --neural
```

To run the automated 30-case benchmark evaluation suite:
```bash
python3 tools/semi-brain/5_evals/run_evals.py
```

---

## 3. How to Update & Improve the Brain After Completing Work

Whenever you complete a task or the user provides a correction:
1. **Sync with latest commits and plans**:
   ```bash
   python3 tools/semi-brain/4_engine/sync_brain.py --sync
   ```
2. **Log user corrections or negative lessons learned into the DPO preference dataset**:
   ```bash
   python3 tools/semi-brain/4_engine/sync_brain.py --feedback \
     --task "<task description>" \
     --chosen "<what was the correct invariant-safe fix>" \
     --rejected "<what was the flawed/naive approach>" \
     --reason "<why chosen was necessary (e.g. avoided audio xruns, preserved UID monotonicity)>"
   ```

---

## 4. Key Distilled References

* **System 1 Priors & Negative Taboos**: `tools/semi-brain/2_distilled_brain/system1_taste_and_priors.md`
* **System 2 Systems Logic & Blast Radius**: `tools/semi-brain/2_distilled_brain/system2_systems_logic.md`
* **Choice Tree Evaluator**: `tools/semi-brain/2_distilled_brain/choice_tree_evaluator.md`
* **Categorization & Rate Hierarchy**: `tools/semi-brain/2_distilled_brain/categorization_matrix.md`
* **From-Scratch Systems Blueprints**: `tools/semi-brain/2_distilled_brain/first_principles_blueprints.md`
