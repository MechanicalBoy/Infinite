#!/usr/bin/env python3
"""Capture the UI/UX screenshots used by the Node Field Guide's app chapter.

macOS only. Needs an unlocked, awake screen and Accessibility permission for the terminal.
It launches nothing: start Infinite first (`open -n Infinite.app --args -ApplePersistenceIgnoreState YES`),
then run this. It resizes the window to 1000x720 at (0,30), loads assets/examples/patch_1.inf over the
control port, drives the real mouse, and saves 2x crops to docs/ui_screenshots/ (BRAND.md 10.1: real
values, no recolouring, no personal paths). Every click first checks that Infinite is the frontmost app.

    python3 tools/manual/ui_shots.py            # all shots
    python3 tools/manual/ui_shots.py library    # only shots whose name contains "library"
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import Quartz as Q  # noqa: E402
import node_screenshot as ns  # noqa: E402

OUT = os.path.join(ROOT, "docs", "ui_screenshots")
WX, WY, WW, WH = 0, 30, 1100, 780          # window rect in screen points
ONLY = sys.argv[1] if len(sys.argv) > 1 else ""


def front():
    return subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true'],
                          capture_output=True, text=True).stdout.strip()


def _ev(t, x, y, b=Q.kCGMouseButtonLeft):
    Q.CGEventPost(Q.kCGHIDEventTap, Q.CGEventCreateMouseEvent(None, t, (x, y), b))


def click(x, y, right=False, wait=0.8):
    """x, y are window points (origin = window top-left)."""
    assert front() == "Infinite", "Infinite is not the frontmost app; refusing to click"
    x, y = x + WX, y + WY
    _ev(Q.kCGEventMouseMoved, x, y); time.sleep(0.2)
    d, u, b = ((Q.kCGEventRightMouseDown, Q.kCGEventRightMouseUp, Q.kCGMouseButtonRight) if right
               else (Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp, Q.kCGMouseButtonLeft))
    _ev(d, x, y, b); time.sleep(0.08); _ev(u, x, y, b); time.sleep(wait)


def key(code, flags=0):
    assert front() == "Infinite"
    for dn in (True, False):
        e = Q.CGEventCreateKeyboardEvent(None, code, dn)
        if flags: Q.CGEventSetFlags(e, flags)
        Q.CGEventPost(Q.kCGHIDEventTap, e); time.sleep(0.05)
    time.sleep(0.6)


ESC, SHIFT = 53, Q.kCGEventFlagMaskShift


def shot(name, crop=None):
    crop = crop or (0, 0, WW, WH)
    if ONLY and ONLY not in name:
        return
    x, y, w, h = crop
    _ev(Q.kCGEventMouseMoved, WX + 3, WY + 3); time.sleep(0.15)    # the app redraws on input: a nudge flushes fade frames
    _ev(Q.kCGEventMouseMoved, WX + 4, WY + 4); time.sleep(0.7)
    subprocess.run(["screencapture", "-x", "-R", f"{WX + x},{WY + y},{w},{h}", os.path.join(OUT, name + ".png")], check=True)
    print("shot", name)


def lum(x, y):
    """Brightness of one window pixel (to tell whether the library panel is open)."""
    from PIL import Image
    tmp = "/tmp/_ui_px.png"
    subprocess.run(["screencapture", "-x", "-R", f"{WX + x},{WY + y},2,2", tmp], check=True)
    r, g, b = Image.open(tmp).convert("RGB").getpixel((1, 1))
    return r + g + b


def set_library(open_):
    """Library panel toggle with a check: its body is lighter than the empty canvas."""
    for _ in range(3):
        if (lum(940, 140) > 60) == open_:
            return
        click(978, 56)


def main():
    os.makedirs(OUT, exist_ok=True)
    subprocess.run(["osascript", "-e", 'tell application "Infinite" to activate'])
    time.sleep(1)
    subprocess.run(["osascript", "-e", 'tell application "System Events" to tell process "Infinite" to set position of window 1 to {0,30}'])
    subprocess.run(["osascript", "-e", 'tell application "System Events" to tell process "Infinite" to set size of window 1 to {1100,780}'])
    time.sleep(1)
    c = ns.RpcClient("127.0.0.1", 7777, open(ns.TOKEN_PATH).read().strip())
    c.call("load_patch", path=os.path.join(ROOT, "assets", "examples", "patch_1.inf"))
    c.call("fit_view"); time.sleep(2)
    STEPS(c)


def STEPS(c):
    LIB, VIEW, MOD, PERF, ARR, HIST, SET = [(978, y) for y in (56, 102, 142, 182, 222, 261, 302)]
    shot("app_overview")
    shot("transport", (0, 0, WW, 80))
    # menus
    for nm, (x, y) in (("menu_file", (64, 56)), ("menu_edit", (112, 56)), ("menu_menu", (166, 56))):
        click(x, y); shot(nm, (0, 0, 480, 440)); key(ESC)
    click(166, 56); click(200, 226); shot("menu_show_set", (0, 0, 640, 440)); key(ESC); key(ESC)
    # library
    set_library(True); shot("library_modules", (590, 70, 410, 650))
    # Samples and Media tabs list the user's own folders and files, so they are described in text, not shown.
    for nm, x in (("field", 711), ("plugins", 905)):
        click(x, 113); shot("library_" + nm, (590, 70, 410, 650))
    click(660, 113)
    click(672, 218); shot("library_sort_dropdown", (590, 70, 410, 650)); key(ESC)
    click(870, 218); shot("library_filter_dropdown", (590, 70, 410, 650)); key(ESC)
    set_library(False)
    # docked panels
    for nm, pos in (("modmatrix", MOD), ("performance", PERF), ("arrangement", ARR), ("history", HIST)):
        click(*pos); shot("panel_" + nm); click(*pos)
    click(*SET)
    for nm, x in (("appearance", 185), ("canvas", 292), ("audio", 383), ("general", 470), ("field", 589), ("globals", 703), ("extensions", 804)):
        click(x, 166); shot("settings_" + nm, (120, 95, 760, 575))
    click(846, 117)          # the Settings window's close button
    for nm, pos in (("modmatrix", MOD), ("performance", PERF), ("arrangement", ARR)):
        click(*pos); shot("strip_" + nm, (0, 500, WW, 220)); click(*pos)
    # viewport card: select an image node, Shift+V, open the panel
    click(303, 212); key(9, SHIFT); click(*VIEW); shot("panel_viewport"); click(*VIEW)
    # menu pages
    click(166, 56); click(150, 282, wait=1.6); shot("window_shortcuts"); click(816, 137, wait=1.2)
    click(166, 56); click(150, 306, wait=1.6); shot("window_help"); click(836, 87, wait=1.2)
    # right-click menus
    click(500, 640, right=True); shot("rc_canvas", (300, 440, 400, 280)); key(ESC)
    click(303, 225, right=True); shot("rc_node", (150, 120, 400, 400)); key(ESC)
    click(550, 594, right=True); shot("rc_cable", (350, 420, 400, 280)); key(ESC)
    # Add Node palette (Shift+N) and its Source submenu
    key(45, SHIFT); shot("addnode_palette", (250, 100, 500, 560)); key(ESC)
    # history after a few edits
    click(303, 225); key(2, Q.kCGEventFlagMaskCommand); key(2, Q.kCGEventFlagMaskCommand); key(11)
    click(*HIST); shot("panel_history_edits"); click(*HIST)


if __name__ == "__main__":
    main()
