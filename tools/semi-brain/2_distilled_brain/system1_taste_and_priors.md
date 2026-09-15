# System 1: Intuitive Thinking, Subconscious Priors & Taste

System 1 represents the subconscious, associative, and fast-heuristic reasoning engine of the developer's mind. It acts as an immediate filter that operates *before* formal analytical proofs begin.

---

## 1. Core Architectural Priors (What "Feels Right")

1. **Zero-Sigil / Clean Language Discipline**:
   - Variables, attributes, and fields must be bare names (`P.y += bass * 2`, never `@P.y` or `P.y = $bass`).
   - Clean, mathematical elegance over verbose boilerplate or punctuation pollution.

2. **The Two-Object Rule for Audio / DSP**:
   - Audio nodes must separate the **Editor/UI/Main-thread Node** (`INode`) from the **DSP Worker** (`IAudioSource` / audio callback state).
   - Main thread owns parameter UI; Audio thread owns DSP execution. The only bridge between them is lock-free atomics / `ParamMailbox`.

3. **Immediate SPSC Lock-Free Communication**:
   - Lock-free, allocation-free queues for inter-thread message passing (`NoteEventQueue`, `ParamMailbox`).
   - Any mutex or synchronization on the audio thread is an automatic rejection.

4. **Visual & UI Symmetry (Grid Discipline)**:
   - Knob-row grid discipline: audio nodes must look like tactile, intentional hardware instruments.
   - Fixed standard slots: `mix` or output level always lives in the bottom-right slot.
   - Contrast budget: Checkboxes, dropdowns, and buttons must adhere to strict dark/light theme visibility standards.

---

## 2. Negative Priors & Taboos (Instant Subconscious Vetoes)

Whenever an implementation idea proposes any of the following, System 1 vetos it immediately:

| Taboo Pattern | Why It Is Vetoed | Required Alternative |
| :--- | :--- | :--- |
| **Heap Allocation in Audio / Shader Path** | Causes audio xruns, clicks, latency spikes, or GPU stalls | Pre-allocate fixed buffers, ringbuffers, or object pools at init/resize time |
| **GPL Code Infection** | Violates MIT licensing / clean-room legal boundary | Clean-room synthesis from open academic papers or specifications |
| **Global State Leaks / Unscoped UIDs** | Breaks undo/redo, copy/paste, and save/load roundtrips | UIDs minted through a monotonically increasing high-water mark; scoped state |
| **Direct Mutation of Shared Upstream Buffers** | Corrupts fan-out branches (two downstream nodes seeing mutated state) | Copy-on-write or dedicated private output buffer |
| **Silent Invariant Swallowing** | Swallowing errors or falling back silently masks regressions | Strict assertion or explicit graceful fallback with logging |
| **Platform-Specific Macros in Node Layer** | Pollutes core logic with `_WIN32` / `#ifdef __APPLE__` | Abstract behind `Platform::` facade |

---

## 3. Heuristic Choice Pruning (Fast Rejection)

When faced with a bug or feature, System 1 tests candidate designs against four intuitive heuristics:

1. **The Inversion Principle**: Instead of asking "how do I make this work?", ask "what is the most subtle way this will corrupt user state 2 weeks from now?"
2. **The Leaky Abstraction Test**: Does this feature require downstream nodes to know about upstream internal formats? If yes, prune this branch.
3. **The Teardown Test**: Can this node/resource be spawned, wired, modulated, and destroyed mid-playback without leaking or crashing?
4. **The Undo-Identity Test**: Does saving, closing, reopening, or pressing Ctrl+Z restore this exact state bit-for-bit?
