# Choice Tree Evaluator: Computational MCTS & Forward Rollout

The Choice Tree Evaluator models developer decision-making as a Monte Carlo Tree Search (MCTS) / Tree-of-Thoughts exploration over possible architecture, refactoring, and bugfix branches.

---

## 1. Decision Branch Exploration

When a problem statement $P$ arrives, the engine generates candidate branches $\mathcal{B} = \{B_1, B_2, B_3, \dots\}$:

```
                                  [Problem Node: P]
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
   [Branch 1: Fast Patch]       [Branch 2: Invariant Guard]   [Branch 3: Root Refactor]
   (Fix symptom locally)        (Guard invariants + sweeps)   (Restructure subsystem)
            │                             │                             │
    [Rollout: Fail Win32]         [Rollout: 100% Passes]        [Rollout: High Regress Risk]
            │                             │                             │
    Reward: R = 0.2               Reward: R = 0.95              Reward: R = 0.6
```

---

## 2. Multi-Objective Value Function (Scoring Heuristic)

Every branch $B$ is evaluated against a 6-factor utility function $V(B)$:

$$V(B) = w_1 \cdot \text{Inv}(B) + w_2 \cdot \text{Plat}(B) + w_3 \cdot \text{RT}(B) + w_4 \cdot \text{RoundTrip}(B) + w_5 \cdot \text{Taste}(B) - w_6 \cdot \text{Blast}(B)$$

Where:
1. $\text{Inv}(B) \in [0, 1]$: **Invariant Preservation Score**
   - Does the branch preserve all existing subsystem contracts without regression?
2. $\text{Plat}(B) \in [0, 1]$: **Cross-Platform Parity Score**
   - Is the implementation identical or cleanly abstracted across macOS, Windows, and Linux?
3. $\text{RT}(B) \in [0, 1]$: **Realtime Safety Score**
   - Zero allocation, zero blocking locks, zero unbounded loops in audio/GPU cook threads.
4. $\text{RoundTrip}(B) \in [0, 1]$: **Serialization & Undo Identity Score**
   - Does state survive Save $\to$ Close $\to$ Load and Undo $\to$ Redo cycles bit-for-bit?
5. $\text{Taste}(B) \in [0, 1]$: **System 1 Aesthetic Score**
   - Zero-sigil syntax, UI symmetry, clean encapsulation, low cognitive overhead.
6. $\text{Blast}(B) \in [0, 1]$: **Blast Radius Risk Penalty**
   - How many unrelated subsystems or files are perturbed?

---

## 3. Forward Rollout Simulation (Simulating Failure Modes)

For each candidate branch, the engine simulates 4 concrete forward rollouts:

1. **The Teardown & Hot-Reload Rollout**:
   - *Simulation*: What happens if the user deletes this node, closes the project, or hot-reloads the shader while the transport is running at 140 BPM?
2. **The Fan-Out / Topology Rollout**:
   - *Simulation*: What happens if 5 downstream nodes connect to this single output? Does memoization hold, or does buffer mutation clobber data?
3. **The Multi-Rate / Transport Rollout**:
   - *Simulation*: What happens if the patch scrubs backward, loops over a 1-bar region, or changes sample rate from 44.1kHz to 96kHz?
4. **The Platform Boundary Rollout**:
   - *Simulation*: How does WASAPI vs CoreAudio vs PipeWire handle device disconnection and sleep/wake cycles under this code?

---

## 4. Branch Selection Policy

$$\text{Select } B^* = \arg\max_{B \in \mathcal{B}} V(B) \quad \text{subject to } \text{RT}(B) = 1.0 \land \text{Plat}(B) = 1.0$$

Any branch with $\text{RT}(B) < 1.0$ (realtime violation) or $\text{Plat}(B) < 1.0$ (platform breakage) is **hard pruned**, regardless of developer convenience or speed.
