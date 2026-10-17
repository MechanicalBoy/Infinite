"""Chapter 29 of the Node Field Guide: Using the App (panels, menus, dropdowns, right-click menus, settings).

Screenshots live in docs/ui_screenshots/ and are captured by tools/manual/ui_shots.py (a scripted run of the real
app, 1440x780 window, 2x). Wide panels are cropped to the part being explained so the text stays legible at page
width; crops are never rescaled up or recoloured (BRAND.md section 10.1).
"""
import html
import os
import tempfile

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SHOTS = os.path.join(ROOT, "docs", "ui_screenshots")
_TMP = tempfile.mkdtemp(prefix="ui_chapter_")
THUMB = 1400.0  # boxes below are in a 1400-px-wide view of the 1440pt window; scaled to the 2x capture


def esc(s):
    return html.escape(s, quote=False)


def fig(name, caption, box=None, width="100%"):
    path = os.path.join(SHOTS, name + ".png")
    if box:
        with Image.open(path) as im:
            k = im.size[0] / THUMB
            out = os.path.join(_TMP, f"{name}_{'_'.join(map(str, box))}.png")
            im.crop(tuple(int(v * k) for v in box)).save(out)
            path = out
    return (f'<figure class="fig" style="display:block;width:{width};margin:0 0 12px"><div class="shot" style="display:block;padding:8px">'
            f'<img src="file://{path}" style="width:100%;display:block"></div>'
            f'<figcaption>{esc(caption)}</figcaption></figure>')


def row(*figs):
    return '<div style="display:flex;gap:12px;align-items:flex-start">' + "".join(
        f'<div style="flex:{w}">{f}</div>' for f, w in figs) + "</div>"


def table(head, rows):
    t = '<table class="t"><tr>' + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr>"
    for r in rows:
        t += "<tr>" + "".join(f"<td>{c}</td>" if i else f"<td><b>{esc(c)}</b></td>" for i, c in enumerate(r)) + "</tr>"
    return t + "</table>"


def page(*parts):
    return '<div style="break-before:page"></div>' + "".join(parts)


def html_chapter(P):
    b = []
    b.append('<div class="kick">Chapter</div><div class="hand" style="font-size:40px;line-height:1">Twenty-nine</div>'
             '<h1>Using the App: Panels, Menus &amp; Settings</h1>'
             '<p class="lead">Everything around the nodes: the panels on the right, the strips along the bottom, the right-click menus, '
             'the dropdowns and the settings. Every picture here is a real screenshot of the app, taken by a script.</p>')
    b.append("<p>These are the questions people ask most: what does the library do, what is the modulation matrix, how do I build a "
             "performance page, how do clips and tracks work, what is in the right-click menu. Each section shows the panel big, "
             "then explains every column, icon and control in it.</p>")

    b.append("<h2>The window at a glance</h2>")
    b.append(fig("app_overview", "The whole window: menu bar and transport on top, the node canvas in the middle, panel buttons down the right edge."))
    b.append(fig("transport", "The transport bar: play/pause, rewind, tempo, time signature, key and scale, metronome, audio switch and the performance readout."))
    b.append(table(["Control", "What it does"], [
        ("Play / Rewind", "Starts and pauses the shared clock that drives sequencers, LFOs and the arrangement; rewind returns to the start."),
        ("BPM (120.0)", "Tempo. Double-click to type an exact value or drag to change it. Every tempo-synced node follows it."),
        ("Time signature (4 / 4)", "Beats per bar and the note value of a beat. It sets the bar lines in the arrangement."),
        ("Key and scale (C Major)", "The global key. Scale-aware nodes snap to it. The dropdown lists Major, Natural / Harmonic / Melodic Minor, the church modes, "
                                    "Major and Minor Pentatonic, Blues, Whole Tone and Chromatic."),
        ("Metronome", "Click track on or off."),
        ("Start Audio / Stop Audio", "Starts or stops the audio engine. While it is stopped you will hear nothing."),
        ("fps, ms, cpu", "Frame rate, frame time and audio load. Hover the audio readout for dropout (xrun) counts."),
    ]))

    b.append(page("<h2>Menus</h2>", "<p>The three menus at the top left. File handles patches, Edit handles undo and clipboard, "
                  "Menu holds the windows, help and the show/set tools.</p>",
                  row((fig("menu_file", "File"), 1), (fig("menu_edit", "Edit"), 1), (fig("menu_menu", "Menu"), 1)),
                  fig("menu_show_set", "Menu: the show and set tools submenu.", width="62%")))

    b.append(page("<h2>Library panel</h2>",
                  "<p>The button at the top right of the toolbar opens the library: every node, sample, media file and plugin you can drop on the canvas. "
                  "Click an entry, or drag it onto the canvas.</p>",
                  row((fig("panel_library_big", "Library, Modules tab: search box, Sort, order toggle, Filter, then the alphabetical list.", box=(1015, 85, 1350, 750)), 1),
                      (table(["Element", "What it does"], [
                          ("Tabs", "Modules (every node type), Field (Field-language nodes and examples), Samples and Media (your own files), Plugins (VST3 and AU instruments and effects)."),
                          ("Search", "Filters the list as you type."),
                          ("Sort", "Orders the list: favourites first, alphabetical and so on. The button beside it flips ascending and descending."),
                          ("Filter", "Narrows the list by category, for example only effects or only synths."),
                          ("List", "Click to add at the centre of the view, or drag to a spot. Star an entry to make it a favourite."),
                      ]), 1)),
                  row((fig("library_sort_dropdown", "Sort dropdown"), 1), (fig("library_filter_dropdown", "Filter dropdown"), 1),
                      (fig("library_field", "Field tab"), 1), (fig("library_plugins", "Plugins tab"), 1))))

    b.append(page("<h2>Viewport panel</h2>",
                  "<p>A live preview of any image node, next to the canvas. Right-click a node and choose <b>Open in viewport panel</b> (or select it and press Shift+V). "
                  "Each card follows its node in real time and has a close button at its top right. Add several cards to watch different stages of a chain at once.</p>",
                  row((fig("panel_viewport_cards", "Three cards open: render 3d, blend #1, blend #2. Scroll the panel for more.", box=(1050, 85, 1350, 750)), 1),
                      (fig("rc_node", "The node context menu where you open a card.", box=(530, 190, 800, 415)), 1))))

    b.append(page("<h2>Modulation Matrix</h2>",
                  "<p>Every modulation in the patch in one table: which source drives which parameter, and how. Drag the splitter above the panel to make it taller; "
                  "at this height thirteen routes are visible at once. The table is shown in two halves so each column is readable.</p>",
                  fig("panel_modmatrix_big", "Left half: Source, Destination, Parameter, Value, Confidence.", box=(10, 290, 700, 750)),
                  fig("panel_modmatrix_big", "Right half: Lo, Hi, Inv, Curve, Signal and the delete button.", box=(690, 290, 1350, 750)),
                  table(["Column", "What it means"], [
                      ("Colour bar", "The cable colour of the source, so you can match a row to the cable on the canvas."),
                      ("Source", "The node that produces the control signal: macro xy, random, an LFO, an envelope and so on."),
                      ("Destination", "The node that receives it."),
                      ("Parameter", "Which parameter on the destination is being moved."),
                      ("Value", "The live, current value of that parameter after modulation."),
                      ("Confidence", "Used by prediction sources to report how sure they are. It shows -- for ordinary sources."),
                      ("Lo / Hi", "The range the parameter travels between. Click a number to type an exact limit. Narrow it for subtle movement."),
                      ("Inv", "Inverts the mapping: when the source goes up, the parameter goes down."),
                      ("Curve", "The response curve between source and parameter, drawn as a small graph."),
                      ("Signal", "A tiny live scope of the incoming signal, so you can see it moving."),
                      ("x", "Removes the route. The cable on the canvas disappears with it."),
                  ])))

    b.append(page("<h2>Performance panel</h2>",
                  "<p>Build your own control surface from knobs, faders, pads and switches, then play it live. It opens in <b>Edit Mode</b>; "
                  "switch off Edit Mode (the button then reads <b>Perform</b>) to lock the layout and play it. Drag the splitter up for more room.</p>",
                  fig("perf_controls_edit", "Edit Mode with all ten control types placed on Page 1.", box=(10, 335, 440, 705), width="70%"),
                  table(["Toolbar", "What it does"], [
                      ("Edit Mode / Perform", "Edit Mode lets you add, move, resize and rename controls. Perform locks the layout so a stray drag cannot move anything."),
                      ("+ Add Control", "Opens the control list below and places the chosen control on the next free cell."),
                      ("Page 1, +", "Pages group controls into screens. The + button adds a page."),
                  ]),
                  row((fig("perf_add_control_menu", "+ Add Control menu: ten control types, with their grid size in brackets.", box=(10, 335, 440, 610)), 1),
                      (table(["Control", "Use it for"], [
                          ("Knob (1x1)", "Any single parameter."),
                          ("Vertical Fader (1x2)", "Levels and mixes."),
                          ("Horizontal Slider (2x1)", "Long throws, crossfades."),
                          ("Toggle (1x1)", "On/off switches and bypass."),
                          ("XY Pad (2x2)", "Two parameters with one finger."),
                          ("Momentary Trigger / Bang (1x1)", "Fires a one-shot while held."),
                          ("Digital Number Box (1x1)", "Type or drag an exact value."),
                          ("Radio Selector (2x1)", "Pick one of several steps, 1 to 8."),
                          ("Bipolar Pan Knob (1x1)", "Centre-detent knob for pan or detune."),
                          ("Step Gate Ribbon (3x1)", "Eight on/off steps for a gate pattern."),
                      ]), 1)),
                  row((fig("perf_control_menu", "Right-click a control: Rename, Type, Assign Parameter, MIDI CC Learn, Color Tint.", box=(10, 335, 440, 610)), 1),
                      (fig("perf_performance_mode", "The same page in Perform mode: the toolbar collapses to a Perform tab.", box=(10, 335, 440, 705)), 1)),
                  table(["Right-click item", "What it does"], [
                      ("Rename", "Change the label shown on the control."),
                      ("Type", "Swap the control for another type without losing its assignment."),
                      ("Assign Parameter...", "Bind the control to a node parameter, then move the control to move the parameter."),
                      ("MIDI CC Learn", "Move a knob on your MIDI controller to bind it to this control."),
                      ("Color Tint", "Colour-code the control so groups are easy to find on stage."),
                  ])))

    b.append(page("<h2>Arrangement panel</h2>",
                  "<p>The timeline. It sequences clips of nodes over time so a patch becomes a piece with a start and an end. "
                  "Each icon in the toolbar is explained below; hover any of them in the app for its tooltip.</p>",
                  fig("arr_empty", "Toolbar, track list and ruler of an empty arrangement.", box=(10, 300, 700, 745)),
                  fig("arr_empty", "Right end of the toolbar: Render and Enable Timeline Audio.", box=(1000, 305, 1350, 345), width="60%"),
                  table(["Toolbar item", "What it does"], [
                      ("Viewport monitor", "Shows or hides the preview of the timeline output at the left of the panel. Right-click for its dock position."),
                      ("Play / Pause (Space)", "Plays the timeline from the playhead."),
                      ("Return to Start (Enter)", "Jumps the playhead to the beginning."),
                      ("Bars / Time", "Switches the ruler between bars and beats and minutes and seconds."),
                      ("Snap (magnet)", "Clip edges snap to the grid when on."),
                      ("1/4 (grid division)", "How fine the snap grid is. See the dropdown below."),
                      ("Loop", "Turns the loop region on or off. Shift-drag on the ruler to set the region."),
                      ("Tool dropdown", "Selects the editing tool. See below."),
                      ("Flag (M)", "Drops a marker at the playhead."),
                      ("Row height", "Resets any resized tracks back to the default height."),
                      ("Pencil", "Opens the Clip / Track Inspector."),
                      ("Render", "Renders the timeline to a video file."),
                      ("Enable Timeline Audio", "Lets the timeline drive audio as well as picture. It reads Timeline Audio On when active."),
                  ]),
                  row((fig("arr_tool_dropdown", "Tool dropdown: Select (A), Trim (T), Range Selection (R), Blade (B), Zoom (Z), Hand (H), Pencil (P).", box=(330, 300, 700, 560)), 1),
                      (fig("arr_grid_dropdown", "Snap grid dropdown: Off, 1 bar, 1/2, 1/4, 1/8, 1/16 and triplets.", box=(250, 300, 600, 600)), 1))))

    b.append(page("<h2>Tracks, clips and the inspector</h2>",
                  "<h3>Adding tracks</h3><p>Click <b>+ Add Track</b> and choose Video Track or Audio Track. Audio tracks also carry <b>S</b> (solo), <b>M</b> (mute), a pan knob and a level knob; "
                  "video tracks carry an opacity slider.</p>",
                  fig("arr_add_track_menu", "+ Add Track offers Video Track and Audio Track.", box=(330, 350, 900, 520), width="75%"),
                  "<h3>Adding a clip</h3><p>Right-click an empty spot on a track and choose <b>Add Clip</b>. It appears at that position, snapped to the grid. "
                  "A clip with no node yet is shown hatched and reads <i>Unassigned</i>.</p>",
                  fig("arr_tracks_clip_menu", "Right-click a lane: Add Clip at the clicked bar and beat.", box=(330, 350, 900, 520), width="75%"),
                  "<h3>Assigning a clip to a node</h3><p>Three ways: right-click a node on the canvas and choose <b>Add to Timeline</b> (creates an assigned clip at the playhead), "
                  "choose <b>Assign Node...</b> in the clip's right-click menu, or use <b>Assign Different Node...</b> in the inspector. "
                  "An assigned clip takes the node's name and colour, and the viewport monitor shows its output as the playhead crosses it.",
                  fig("arr_clip_assigned", "A clip assigned to render 3d; the viewport monitor on the left shows its live output.", box=(10, 305, 1000, 745))))

    b.append(page("<h3>Right-clicking a clip</h3>",
                  row((fig("arr_clip_menu_assigned", "An assigned clip.", box=(580, 420, 900, 750)), 1),
                      (fig("arr_clip_menu_unassigned", "An unassigned clip.", box=(850, 390, 1250, 580)), 1),
                      (table(["Item", "What it does"], [
                          ("Rename (Cmd+R)", "Names the clip."),
                          ("Active", "Tick to play the clip; untick to mute it without deleting."),
                          ("Fade In / Fade Out", "Fade length in milliseconds."),
                          ("Opacity", "Clip brightness against what is beneath it."),
                          ("Compositing", "Blend mode used to combine this clip with lower tracks."),
                          ("Color Grade", "A submenu of colour-grade adjustments for the clip."),
                          ("Color Tint", "Colour of the clip block on the timeline."),
                          ("Assign Node...", "Pick the node this clip plays."),
                          ("Group (Cmd+G) / Ungroup (Cmd+Shift+G)", "Treat several clips as one block you can move together."),
                          ("Delete (Backspace)", "Removes the clip."),
                      ]), 1)),
                  "<h3>The Clip / Track Inspector</h3><p>The pencil icon opens a side panel for whatever is selected. Select a clip and it shows the clip; select a track and it shows the track.</p>",
                  row((fig("arr_inspector_clip_1", "Video Clip, top: name, Active, Timing &amp; Position, Compositing.", box=(1100, 345, 1345, 745)), 1),
                      (fig("arr_inspector_clip_3", "Video Clip, bottom: Speed, Reverse, Color Tint, Source Node, Modulations.", box=(1100, 345, 1345, 745)), 1),
                      (fig("arr_inspector_track", "Video Track: name, Active, opacity, tint, Duplicate, Delete.", box=(1100, 345, 1345, 745)), 1)),
                  table(["Inspector field", "What it does"], [
                      ("Name / Active", "Rename and enable or disable the clip or track."),
                      ("Start / Length", "Exact position and duration in bars.beats.ticks. Type a value for sample-accurate placement."),
                      ("Fade In / Fade Out", "Edge fades in milliseconds."),
                      ("Blend / Opacity / Bright / Contrast", "How the clip composites over tracks beneath it."),
                      ("Speed / Reverse", "Plays the clip faster, slower or backwards."),
                      ("Color Tint", "The ten swatches colour the clip block."),
                      ("Source Node", "The node and node type the clip plays."),
                      ("Modulations", "The modulation routes feeding that node, listed as parameter &lt;- source."),
                      ("Assign Different Node... / Clear Source", "Swap the node or make the clip unassigned again."),
                  ])))

    b.append(page("<h3>Selecting several clips and grouping</h3>",
                  "<p>To move or colour several clips at once, press <b>R</b> for the Range Selection tool and drag a box over them, then press <b>A</b> to return to Select. "
                  "Clips grouped with Group (Cmd+G) move as one.</p>",
                  fig("arr_range_select", "Range Selection: all three clips selected by one drag.", box=(330, 350, 1340, 480)),
                  "<h3>Grouping tracks</h3><p>Right-click a track name. <b>Convert to Group</b> wraps the track in a collapsible folder so a whole stack of tracks can be folded away. "
                  "The same menu adds and renames tracks, deletes them, and offers <b>Render Track</b> to export just that track.</p>",
                  row((fig("arr_track_menu", "Track menu.", box=(330, 350, 700, 580)), 1),
                      (fig("arr_track_group", "After Convert to Group: Group 2 (1) holds Video 3.", box=(330, 350, 1340, 520)), 2))))

    b.append(page("<h2>History panel</h2>",
                  "<p>Every edit you make is listed, newest at the top. Click any line to jump the patch back (or forward) to that moment; edits after it are kept until you make a new change.</p>",
                  row((fig("panel_history_big", "History, with a real session's edits.", box=(1070, 85, 1350, 500)), 1),
                      (table(["Entry", "Meaning"], [
                          ("Start", "The patch as it was loaded."),
                          ("Bypass", "A node was bypassed or enabled."),
                          ("Edit 2 settings", "Two or more parameters changed together."),
                          ("Edit timeline", "A change in the arrangement."),
                      ]), 1))))

    b.append(page("<h2>Right-click menus and the Add Node palette</h2>",
                  "<p>Right-click does different things depending on what is under the cursor.</p>",
                  row((fig("rc_node", "On a node: bypass, duplicate, hide parameters, open in viewport panel, add to timeline, open in new window, help, delete.", box=(530, 190, 800, 415)), 1),
                      (table(["Node menu item", "What it does"], [
                          ("Bypass Node (B)", "Passes the input straight through."),
                          ("Duplicate (Cmd+D)", "Copies the node and its settings."),
                          ("Hide params", "Hides the node's parameter controls so it takes less room on the canvas."),
                          ("Open in viewport panel", "Adds a live card to the Viewport panel."),
                          ("Add to Timeline", "Creates an assigned clip in the Arrangement."),
                          ("Open in new window", "Pops the node's output into its own window."),
                          ("Help", "Opens this node's help."),
                          ("Delete Node (Backspace)", "Removes it and its cables."),
                      ]), 1)),
                  "<p>Right-click empty canvas, or press Shift+N, to open the <b>Add node</b> palette. Type to search, or walk the categories "
                  "(source, compositing, effects, 3d, notes, synths, audio effects, modulators, prediction, macros, utility). "
                  "The arrow means a submenu.</p>",
                  row((fig("rc_canvas_palette", "The Add node palette.", box=(200, 445, 620, 755)), 1),
                      (fig("rc_palette_submenu", "Hover a category to see its nodes: synths shown.", box=(200, 320, 625, 755)), 1))))

    b.append(page("<h2>Settings</h2>",
                  "<p>The gear button opens Settings. It has seven tabs.</p>",
                  row((fig("settings_appearance", "Appearance"), 1), (fig("settings_canvas", "Canvas"), 1)),
                  row((fig("settings_audio", "Audio"), 1), (fig("settings_general", "General"), 1)),
                  row((fig("settings_field", "Field"), 1), (fig("settings_globals", "Globals"), 1)),
                  fig("settings_extensions", "Extensions: browse and install extension packs.", width="48%")))

    b.append(page("<h2>Take your own screenshots</h2>",
                  "<p>Every picture in this guide was made by script, so you can regenerate them after an update or make your own for a tutorial.</p>",
                  table(["Tool", "What it does"], [
                      ("scripts/screenshot_all_nodes.py", "Renders every node type through the app's RPC <code>screenshot_node</code> and saves a 2x PNG for each into docs/node_screenshots/."),
                      ("scripts/node_screenshot.py", "Spawns one node by type name and saves a cropped screenshot of it. Useful for tutorials and bug reports."),
                      ("tools/manual/ui_shots.py", "Drives the real app window with scripted clicks to capture the panels, menus and dropdowns in this chapter into docs/ui_screenshots/."),
                  ]),
                  "<pre><code>python3 scripts/screenshot_all_nodes.py --out docs/node_screenshots\n"
                  "python3 scripts/node_screenshot.py \"Wavetable\" --out /tmp/shots\n"
                  "python3 tools/manual/build.py        # rebuild this guide with the fresh pictures</code></pre>",
                  "<p>Screenshots are captured at 2x, show real values and are never recoloured. The control token for the RPC is read from the app's own settings folder, so nothing leaves your machine.</p>"))
    return "".join(b)
