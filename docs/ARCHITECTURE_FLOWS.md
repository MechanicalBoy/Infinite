# Architecture flows

Diagrams of how Infinite's code is layered, threaded and cooked. The text map with symbols to
grep is [`ARCHITECTURE.md`](../ARCHITECTURE.md); that file wins on any detail. Labels here name
real symbols (checked 2026-10-12); if one stops existing, fix the label.

## 1. Layers

```mermaid
flowchart TD
    subgraph L5["Dev & verification harness"]
        H1["In-app self-tests: src/app/selftest/ (INFINITE_* env)"]
        H2["Headless CLI (docs/headless)"]
        H3["driver.sh · scripts/bench/ab.sh · tools/render-check.py"]
    end
    subgraph L4["Editor UI: src/main.cpp, src/app/"]
        U1["Node canvas (imgui-node-editor)"]
        U2["Draw*Params / Draw*Body"]
        U3["Docked panels: modulation, performance, browser"]
        U4["Arrange timeline: src/arrange/"]
    end
    subgraph L3["Nodes: src/nodes/"]
        N1["3D & geometry"] --- N2["2D compositing"] --- N3["Audio & synths"]
        N4["Field nodes"] --- N5["Modulators & prediction"] --- N6["Utility & I/O"]
    end
    subgraph L2["Core: src/core/, src/audio/"]
        E1["INode, NodeFactory"] --- E2["AudioEngine, SampleSlot"] --- E3["Modulation, ParamMailbox"]
        E4["Field compiler: src/core/field/"] --- E5["Transport"] --- E6["Patch save/load, undo"]
    end
    subgraph L1["Platform: src/platform/ (macOS · Windows · Linux, every Platform:: function on all three)"]
    end
    L4 --> L3 --> L2 --> L1
    L5 -.-> L4 & L3 & L2
```

## 2. Threads and how they hand off

```mermaid
flowchart TD
    subgraph Audio["AUDIO CALLBACK: AudioEngine"]
        A1["Block deadline = buffer / sample rate<br/>(256 @ 48 kHz ≈ 5.3 ms)<br/>no alloc, no lock, no file I/O, no ImGui"]
        A2["Node ProcessBlock / IEffectKernel"]
        A1 --- A2
    end
    subgraph Main["MAIN THREAD: src/main.cpp"]
        M1["Event loop"] --> M2["ApplyModulationAndPalette"] --> M3["CookIfNeeded(frameId) pull"] --> M4["ImGui draw"] --> M5["GL render, projector swaps"]
    end
    subgraph Workers["WORKERS (std::thread)"]
        W1["SampleScanner, PluginScanner"]
        W2["MolderNode, GrainMolderNode analysis"]
        W3["RemoveBgNode (latest-only queue)"]
        W4["NdiInNode, OSC receivers, LooperNode save"]
    end

    M2 == "ParamMailbox: one atomic slot per param<br/>(latest value wins, deliberately not a ring)" ==> A2
    M1 == "SampleSlot: pending / active / retire<br/>+ SPSC retire ring" ==> A2
    A2 -. "atomic meters" .-> M4
    W1 == "mResultReady flag" ==> M1
    W2 == "mResultReady flag" ==> M1
    W3 == "latest-only result" ==> M3
```

## 3. Data flow per frame

```mermaid
flowchart TD
    subgraph Push["MODULATION (push, main thread, once per frame)"]
        T["Transport tick"] --> Mod["Evaluate modulators"] --> Mx["Matrix: source × depth → ParamRef"]
        Mx --> UI["Main-thread params"]
        Mx --> MB["ParamMailbox → audio thread"]
    end
    subgraph Pull["VISUALS (pull, main thread)"]
        Out["Output / viewport / projector"] --> C["CookIfNeeded(frameId)"]
        C --> Same{"Already cooked<br/>this frame?"}
        Same -- yes --> Cached["Reuse texture"]
        Same -- no --> Up["Inputs' CookIfNeeded"] --> Rev{"Input revision<br/>moved?"}
        Rev -- yes --> Re["Recompute"]
        Rev -- no --> Keep["Reuse cache"]
    end
    subgraph APull["AUDIO (pull, audio thread, per block)"]
        CB["Device callback"] --> Pop["Read ParamMailbox slots"] --> Graph["Pull inputs along audio cables"] --> DSP["DSP"] --> HW["Device out"]
    end
```

## 4. The two-object node

```mermaid
flowchart LR
    subgraph Engine["Engine: src/nodes/XNode.h/.cpp"]
        E["XNode : INode (+ IAudioSource / IGeometrySource)<br/>CookIfNeeded, ProcessBlock, geometry getters<br/>no ImGui"]
    end
    subgraph Bridge["Binding"]
        B["Modulation::RegisterParam(ParamRef)<br/>INode::VisitParams → save/load, undo, copy/paste"]
    end
    subgraph Drawer["Drawer: src/main.cpp / src/app/"]
        D["Draw*Params / Draw*Body<br/>knobs, dropdowns, visualizers<br/>node-ui-pillars rules"]
    end
    Engine <==> Bridge <==> Drawer
```
