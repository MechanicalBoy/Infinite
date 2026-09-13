## Problem
VST3 plugin editors (JUCE-based) don't repaint on Linux when hosted in our own X11 window.

| # | Source (link) | Similarity — why | Status | Their fix (1–2 lines) | Applies to Infinite at | Confidence |
|---|---|---|---|---|---|---|
| 1 | [Steinberg Forum: Doc clarification on IRunLoop](https://forums.steinberg.net/t/doc-clarification-on-irunloop/916726) | Explains why JUCE VST3 plugin UIs freeze/stop repainting when event/timer handlers are not called on the UI thread | Solved | Host must dispatch all `IEventHandler::onFDIsSet` and `ITimerHandler::onTimer` callbacks on the main/UI thread, never on a background `poll()` thread | `docs/plans/linux/phase-04-vst3.md` §4.3 (threading requirement in `PumpPluginEditorEvents`) | High |
| 2 | [JUCE commit de712ca](https://github.com/juce-framework/JUCE/commit/de712ca02e2bca8a7b66e1f4c99ff246dd6a7c47) | Reference implementation of Linux VST3 plugin hosting and X11 window embedding (`VST3PluginWindow`, `XEmbedComponent`) | Solved | Exposes `Linux::IRunLoop` via `IPlugFrame::queryInterface`, embeds via `kPlatformTypeX11EmbedWindowID`, and forwards XEmbed notifications | `docs/plans/linux/phase-04-vst3.md` §4.3 (X11 window creation, frame queryInterface, and XEmbed handling) | High |
| 3 | [yabridge CHANGELOG](https://github.com/robbert-vdh/yabridge/blob/master/CHANGELOG.md) | Demonstrates how JUCE editors freeze or become sluggish when event loop processing has rigid count limits | Solved | Service ready file descriptors in a loop until none are pending, bounded by a time budget (e.g. 4 ms) rather than a rigid event-count cap | `docs/plans/linux/phase-04-vst3.md` §4.3 (event pump budget in `PumpPluginEditorEvents`) | High |
| 4 | [Steinberg: Provide a Runloop on Linux](https://steinbergmedia.github.io/vst3_dev_portal/pages/Technical+Documentation/Provide+A+Runloop+On+Linux/Index.html) | Host contract for `Steinberg::Linux::IRunLoop` | Solved | Host must expose `IRunLoop` both through `IPlugFrame` (for open editors) and via `IPluginFactory3::setHostContext` (for background/editorless timers) | `docs/plans/linux/phase-04-vst3.md` §4.3 (host context setup before editor creation) | High |
| 5 | [Carla (falkTX/Carla)](https://github.com/falkTX/Carla) | Multi-format Linux plugin host managing X11 foreign windows | Solved | Flushes and drains `XPending` on the display connection per frame and delivers `ConfigureNotify`/`Expose` events to the embedded XID | `docs/plans/linux/phase-04-vst3.md` §4.3 (`XPending` drain and event dispatch loop) | High |

## Patterns across sources
- **Main-thread dispatch is mandatory:** Even though the Steinberg VST3 API specification does not explicitly state that `IRunLoop` callbacks must be serialized on the UI thread, JUCE and all JUCE-derived plugins assume handler invocations happen on the main thread. Running poll loops on background threads leads directly to memory corruption or frozen UI.
- **Dual exposure paths:** `IRunLoop` must be made available through `IPlugFrame::queryInterface` (used by `JuceVST3Editor::attached()`) and via `IPluginFactory3::setHostContext` (used by plugins that maintain background timers without open editor views).
- **Time-budgeted event draining:** Simple count caps (e.g., max 10 events per frame) cause UI lag and event starvation during animated parameter movements or window resizes. A wall-clock time slice (e.g., 2–4 ms per UI tick) ensures responsive rendering without stalling audio or the main thread.
- **X11 parent structure notification:** The host window holding the plugin's XID must listen for `StructureNotifyMask` and handle window exposure and reparenting gracefully.

## Searched, found nothing
- `gh search issues "IRunLoop" --repo robbert-vdh/yabridge` → 0 relevant (yabridge documents run loop behavior in changelogs and Wine-host code rather than issue titles)
- `gh search code "kPlatformTypeX11EmbedWindowID" --repo falkTX/Carla` → 0 hits on exact symbol via GitHub code search (Carla wraps VST3 hosting modules via JUCE/custom layers)

## Open questions
- Does GLFW on Wayland reliably support foreign X11 window embedding via XWayland without a separate dedicated X11 display connection?
- Should `PumpPluginEditorEvents` allocate an adaptive time budget based on frame rendering overhead (e.g. 15% of frame target)?
