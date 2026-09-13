# Lens 4 — UI/UX

**Question:** What does the user see, touch and understand, and does it behave
like an instrument?

**Not this lens:** whether a control's value persists (→ 3), or whether a
shortcut works on Windows (→ 5, via the 4d coupling).

## Trigger questions
- Does it change a `Draw*Body` / `Draw*Params` function, a widget, or a visualizer?
- Does it change pins, cables, node sizing, dragging, groups, the minimap, or selection?
- Does it touch a docked panel, a floating window, a menu, or a popup?
- Does it add or change a key binding, trackpad gesture, or drag-and-drop behaviour?
- Does it change colours, icons, fonts, spacing, or anything visible in light or dark mode?
- Does it change a user-visible name, label, tooltip, help text, or error message?

## Sub-lenses

### 4a Node body
- **Anchors:** `Draw*Body` / `Draw*Params` in `main.cpp`, `DrawAudioNodeBody` + `EffectVisualizerId`, `AudioKnobRow`, `PushCheckboxStyle`, `PushDropdownStyle`, `DrawDiscreteParamPin`, `ModSlider`.
- **Rules:**
  - Keep a symmetric knob grid, with the `mix` slot at bottom-right.
  - Keep audio nodes KHS-plugin-simple: about 7 controls, one mode.
- **Owning skills:** `node-ui-pillars` (**load before any edit**), `audio-node-ui`, `node-ui-sweep`.

### 4b Canvas & graph interaction
- **Anchors:** `DrawPin`, link rendering (`ed::Link`), group UI (`DrawGroupNode`, `AutoFitGroupToMembers`), `DrawMinimap`, `DrawPreview`, `NodeViewport` (`src/core/NodeViewport.*`), drag-drop (`gDroppedFiles` / `gDropPos`).
- **Owning skills:** `node-ui-sweep`, `cable-logic-sweep` (what a drag may connect).

### 4c Panels & windows
- **Anchors:** mod matrix (`DrawModMatrixDocked` / `DrawModMatrixTable`), performance matrix (`DrawPerfPanelDocked`), the node/sample/plugin browser (`gBrowserFavorites`, `SampleScanner` / `PluginScanner` modes), `DrawHelpWindow`, `DrawShortcutsWindow`, projector windows, the Field editor, and the arrangement panel (in progress on `feature/arrange-step-*`).
- **Owning skills:** `panels-sweep`, `output-projection-sweep` (projector windows).

### 4d Input & shortcuts
- **Anchors:** `kShortcuts[]` in `DrawShortcutsWindow`, `cmdOrCtrl`, `MODKEY`, the keyboard-shortcut block (undo / delete / duplicate / group / copy-paste), and trackpad wheel damping.
- **Rules:**
  - Every binding appears in the shortcuts window.
  - No handler is gated on Cmd alone.
- **Owning skills:** `shortcuts-sweep`.

### 4e Theme & visual language
- **Anchors:** `CategoryColors.*`, `TablerIcons.h` / `IconsLucide.h`, HiDPI font setup, and the ImGui base style.
- **Rules:**
  - The light/dark contrast budget for checkboxes and dropdowns is non-negotiable (`node-ui-pillars`).
  - Debug tools (UI Debugger, Style Editor) sit behind `#ifndef NDEBUG`.
- **Owning skills:** `node-ui-pillars`, `apple-design-skill` (for critique against the HIG).

### 4f Wording & discoverability
- **Covers:** node names (`DisplayName`), filter-mode naming, tooltips, help text, error text from Field or formula compile, and release notes.
- **Owning skills:** `node-ui-pillars` (filter-mode naming), `release-notes-audit`, and `ship-infinite` (Node Reference Manual changes).

## Zoom guide
| Zoom | For UI/UX it means |
|---|---|
| L1 | Which surface X appears on (node body, canvas, panel, window, menu) and in which user flow |
| L2 | The controls/states X exposes and the interactions they accept (click, drag, key, drop) |
| L3 | Draw function → widget helpers → style push/pop → param write → undo checkpoint |
| L4 | The exact `ImGui` calls, sizes, and colours responsible for a misalignment or contrast bug |
