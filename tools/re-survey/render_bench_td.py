# re-survey render_bench, TouchDesigner side. TD has no headless mode, so the owner runs this once:
#   1. python3 tools/re-survey/render_bench.py td-prep      (writes ~/re-output/render-bench/TD/click.wav
#      and prints the line to paste)
#   2. In a new TouchDesigner project: Dialogs > Textport, paste the printed line, Enter.
#   3. Wait for "BENCH done" in the Textport (about 11 minutes: the sync take records in real time).
#   4. python3 tools/re-survey/render_bench.py analyse ~/re-output/render-bench/*/ --out results.md
# Public TD Python only (op().create, par, Movie File Out TOP). Nothing here reads TD's files.
# Jobs, matching Infinite and Blender (render_bench.py):
#   instanced : 10,000 boxes instanced on a 100 x 100 grid, spinning, 1280 x 720 (TD non-commercial caps
#               resolution at 1280 x 1280, so 1080p/4K are not reachable without a licence) - frames/s of
#               Movie File Out in non-realtime mode, H264
#   blur      : 30 x 30 boxes + 4 Blur TOPs of 20 px
#   sync      : black, white for 0.1 s each second, click.wav under it, 600 s, H264 + AAC, real time
import json, os, time

OUT = os.path.expanduser("~/re-output/render-bench/TD")
SYNC_S = int(os.environ.get("RB_TD_SYNC_S", "600"))
FRAMES = 180
root = op("/project1")


def new(kind, name):
    old = root.op(name)
    if old is not None:
        old.destroy()
    return root.create(kind, name)


def setmenu(par, *wanted):
    # Menu names differ between TD versions: take the first wanted name the menu has, print the menu otherwise.
    names = list(par.menuNames)
    for w in wanted:
        for n in names:
            if n.lower() == w.lower():
                par.val = n
                return n
    print("BENCH menu %s: none of %s in %s" % (par.name, wanted, names))
    return None


def movie_out(name, src, path, audio=None):
    m = new(moviefileoutTOP, name)
    m.inputConnectors[0].connect(src)
    setmenu(m.par.type, "movie")
    m.par.file = path
    setmenu(m.par.videocodec, "h264", "h264nvgpu", "h264cpu")
    if audio is not None:
        m.par.audiochop = audio.path
        setmenu(m.par.audiocodec, "aac", "mp3", "pcm16")
    return m


def scene(n, blurs):
    box = new(boxSOP, "rb_box")
    box.par.sizex = box.par.sizey = box.par.sizez = 0.06
    grid = new(gridSOP, "rb_grid")
    grid.par.rows = grid.par.cols = n
    grid.par.sizex = grid.par.sizey = 10
    pts = new(soptoCHOP, "rb_pts")
    pts.par.sop = grid.path
    geo = new(geometryCOMP, "rb_geo")
    for c in list(geo.children):
        c.destroy()
    inside = geo.create(inSOP, "in1")
    inside.render = inside.display = True
    box.outputConnectors[0].connect(geo.inputConnectors[0])
    geo.par.instancing = True
    geo.par.instanceop = pts.path
    geo.par.instancetx, geo.par.instancety, geo.par.instancetz = "tx", "ty", "tz"
    geo.par.rz.expr = "absTime.seconds * 90 / 3"
    cam = new(cameraCOMP, "rb_cam")
    cam.par.tx, cam.par.ty, cam.par.tz = 0, -12, 8
    cam.par.rx = 55
    light = new(lightCOMP, "rb_light")
    r = new(renderTOP, "rb_render")
    r.par.geometry = geo.path
    r.par.camera = cam.path
    r.par.lights = light.path
    r.par.outputresolution = "custom"
    r.par.resolutionw, r.par.resolutionh = 1280, 720
    last = r
    for i in range(blurs):
        b = new(blurTOP, "rb_blur%d" % i)
        b.par.size = 20
        b.inputConnectors[0].connect(last)
        last = b
    return last


def timed_record(name, src, path, frames):
    m = movie_out(name, src, path)
    project.realTime = False
    start = absTime.frame
    t = time.perf_counter()
    m.par.record = True
    state = {"m": m, "start": start, "t": t, "frames": frames, "name": name}
    return state


results = {}
jobs = [("instanced", 100, 0), ("blur", 30, 4)]


def run_job(i):
    if i >= len(jobs):
        return run_sync()
    name, n, blurs = jobs[i]
    src = scene(n, blurs)
    path = "%s/%s_720p_h264.mp4" % (OUT, name)
    st = timed_record("rb_out", src, path, FRAMES)

    def check():
        done = absTime.frame - st["start"]
        if done < FRAMES:
            run("args[0]()", check, delayFrames=1)
            return
        st["m"].par.record = False
        wall = time.perf_counter() - st["t"]
        results[name] = {"frames": done, "wall_s": wall, "fps": done / wall, "movie": path}
        print("BENCH %s %s" % (name, json.dumps(results[name])))
        run("args[0](args[1])", run_job, i + 1, delayFrames=5)

    run("args[0]()", check, delayFrames=1)


def run_sync():
    project.realTime = True
    for c in list(root.children):
        if c.name.startswith("rb_"):
            c.destroy()
    flash = new(constantTOP, "rb_flash")
    flash.par.resolutionw, flash.par.resolutionh = 320, 180
    flash.par.colorr.expr = flash.par.colorg.expr = flash.par.colorb.expr = "1 if (absTime.seconds % 1) < 0.1 else 0"
    flash.par.alpha = 1
    au = new(audiofileinCHOP, "rb_click")
    au.par.file = OUT + "/click.wav"
    setmenu(au.par.repeat, "off", "once")
    au.par.play = True
    path = OUT + "/sync600.mp4"
    m = movie_out("rb_syncout", flash, path, audio=au)
    t0 = absTime.seconds
    au.par.cuepulse.pulse()
    m.par.record = True

    def check():
        if absTime.seconds - t0 < SYNC_S:
            run("args[0]()", check, delayFrames=30)
            return
        m.par.record = False
        results["sync"] = {"movie": path, "seconds": SYNC_S}
        json.dump({"app": "TouchDesigner", "version": app.version + "." + str(app.build), "jobs": results},
                  open(OUT + "/td_bench.json", "w"), indent=1)
        print("BENCH done: %s/td_bench.json" % OUT)

    run("args[0]()", check, delayFrames=30)


os.makedirs(OUT, exist_ok=True)
run_job(0)
