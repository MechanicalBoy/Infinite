# re-survey av_bench, TouchDesigner side. TD has no headless mode, so whoever drives the GUI runs this:
#   1. python3 tools/re-survey/av_bench.py td-prep --mode av      (writes ~/re-output/av-bench/TD/loop.wav and
#      prints the line to paste)
#   2. In a new TouchDesigner project: Dialogs > Textport, paste the printed line, Enter.
#   3. Wait for "AVBENCH done" in the Textport. Then repeat 1-2 with --mode scene.
#   4. python3 tools/re-survey/av_bench.py td      (analyses td_av.json / td_scene.json and the movie)
# Public TD Python only (op().create, par, run(), absTime, project). Nothing here reads TD's files.
# Modes (environment AV_TD_MODE):
#   av    : loop.wav (8 clicks at 128 BPM) looping in an Audio File In CHOP -> Analyze CHOP (maximum per frame)
#           -> a Constant TOP that turns white while the peak is over 0.2. Movie File Out records the picture with
#           that same audio, in real time, 15 s. Every frame's start time is logged too.
#   scene : the same audio driving a 10,000-instance scene (100 x 100 grid of boxes, scale from the audio level,
#           spinning) rendered at 1280 x 720 in real time for 60 s; logs every frame's time. The Render TOP is
#           force-cooked once per frame so it renders even with no viewer open.
import json, os, time

OUT = os.path.expanduser("~/re-output/av-bench/TD")
MODE = os.environ.get("AV_TD_MODE", "av")
SECONDS = {"av": 15, "scene": 60}[MODE]
root = op("/project1")
errors = []


def new(kind, name):
    old = root.op(name)
    if old is not None:
        old.destroy()
    return root.create(kind, name)


def setmenu(par, *wanted):
    names = list(par.menuNames)
    for w in wanted:
        for n in names:
            if n.lower() == w.lower():
                par.val = n
                return n
    errors.append("menu %s: none of %s in %s" % (par.name, wanted, names))
    return None


def setpar(o, name, value):
    try:
        setattr(o.par, name, value)
    except Exception as e:
        errors.append("%s.par.%s: %s" % (o.name, name, e))


def audio():
    au = new(audiofileinCHOP, "av_click")
    au.par.file = OUT + "/loop.wav"
    setmenu(au.par.repeat, "on", "loop", "repeat")
    setpar(au, "play", True)
    an = new(analyzeCHOP, "av_an")
    an.inputConnectors[0].connect(au)
    setmenu(an.par.function, "maximum", "max")
    return au, an


def av_net():
    au, an = audio()
    flash = new(constantTOP, "av_flash")
    flash.par.resolutionw, flash.par.resolutionh = 320, 180
    flash.par.colorr.expr = flash.par.colorg.expr = flash.par.colorb.expr = "1 if op('av_an')[0] > 0.2 else 0"
    flash.par.alpha = 1
    m = new(moviefileoutTOP, "av_out")
    m.inputConnectors[0].connect(flash)
    setmenu(m.par.type, "movie")
    m.par.file = OUT + "/av.mp4"
    setmenu(m.par.videocodec, "h264", "h264nvgpu", "h264cpu")
    m.par.audiochop = au.path
    setmenu(m.par.audiocodec, "aac", "mp3", "pcm16")
    au.par.cuepulse.pulse()
    m.par.record = True
    return m, None


def scene_net():
    au, an = audio()
    setmenu(an.par.function, "rmspower", "rms power", "maximum")
    dev = new(audiodeviceoutCHOP, "av_dev")   # heard, as in a real set
    dev.inputConnectors[0].connect(au)
    box = new(boxSOP, "av_box")
    box.par.sizex = box.par.sizey = box.par.sizez = 0.06
    grid = new(gridSOP, "av_grid")
    grid.par.rows = grid.par.cols = 100
    grid.par.sizex = grid.par.sizey = 10
    pts = new(soptoCHOP, "av_pts")
    pts.par.sop = grid.path
    geo = new(geometryCOMP, "av_geo")
    for c in list(geo.children):
        c.destroy()
    inside = geo.create(inSOP, "in1")
    inside.render = inside.display = True
    box.outputConnectors[0].connect(geo.inputConnectors[0])
    geo.par.instancing = True
    geo.par.instanceop = pts.path
    geo.par.instancetx, geo.par.instancety, geo.par.instancetz = "tx", "ty", "tz"
    geo.par.rz.expr = "absTime.seconds * 30"
    geo.par.sx.expr = geo.par.sy.expr = geo.par.sz.expr = "1 + 4 * op('av_an')[0]"
    cam = new(cameraCOMP, "av_cam")
    cam.par.tx, cam.par.ty, cam.par.tz = 0, -12, 8
    cam.par.rx = 55
    light = new(lightCOMP, "av_light")
    r = new(renderTOP, "av_render")
    r.par.geometry = geo.path
    r.par.camera = cam.path
    r.par.lights = light.path
    r.par.outputresolution = "custom"
    r.par.resolutionw, r.par.resolutionh = 1280, 720
    au.par.cuepulse.pulse()
    return None, r


def start():
    os.makedirs(OUT, exist_ok=True)
    project.realTime = True
    for c in list(root.children):
        if c.name.startswith("av_"):
            c.destroy()
    m, force = av_net() if MODE == "av" else scene_net()
    stamps = []
    t0 = absTime.seconds

    def tick():
        if force is not None:
            force.cook(force=True)
        stamps.append(time.perf_counter())
        if absTime.seconds - t0 < SECONDS:
            run("args[0]()", tick, delayFrames=1)
            return
        if m is not None:
            m.par.record = False
        json.dump({"app": "TouchDesigner", "version": app.version + "." + str(app.build), "mode": MODE,
                   "movie": OUT + "/av.mp4" if MODE == "av" else None, "cook_rate": project.cookRate,
                   "frame_s": stamps, "errors": errors}, open("%s/td_%s.json" % (OUT, MODE), "w"))
        print("AVBENCH done: %s/td_%s.json (%d frames, %d setup errors)" % (OUT, MODE, len(stamps), len(errors)))

    run("args[0]()", tick, delayFrames=10)


start()
