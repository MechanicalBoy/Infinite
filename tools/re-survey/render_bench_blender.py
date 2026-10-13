# re-survey render_bench, Blender side. Runs inside Blender (public bpy API only):
#   Blender -b --factory-startup --python render_bench_blender.py -- <job> <scene> <W> <H> <N> <out>
# job:   stills  -> renders frames 1..N as PNG one by one, prints BENCH {"frame_s": [...]} (render time per frame)
#        movie   -> renders the animation 1..N to <out> (H264 MP4 or ProRes 4444 MOV by extension)
#        pngseq  -> renders the animation 1..N as PNGs into the folder <out> (lossless reference for movie)
#        sync    -> VSE only: black, a white flash of 3 frames on every second, click.wav (<scene>) under it,
#                   N seconds long at 30 fps, H264 + AAC to <out>
# scene: instanced (10,000 cubes on a 100x100 grid, spinning) or blur (30x30 cubes + 4 compositor blurs)
import bpy, sys, time, json, math

argv = sys.argv[sys.argv.index("--") + 1:]
job, scene, W, H, N, out = argv[0], argv[1], int(argv[2]), int(argv[3]), int(argv[4]), argv[5]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100


def video_out(path):
    r.image_settings.media_type = "VIDEO"
    r.image_settings.file_format = "FFMPEG"
    if path.endswith(".mov"):
        r.ffmpeg.format = "QUICKTIME"
        r.ffmpeg.codec = "PRORES"
        r.ffmpeg.ffmpeg_prores_profile = "4444"
    else:
        r.ffmpeg.format = "MPEG4"
        r.ffmpeg.codec = "H264"  # Blender's defaults for quality (CRF) and preset, as a user gets them
    r.filepath = path


if job == "sync":
    r.fps = 30
    sc.frame_start, sc.frame_end = 1, N * 30
    se = sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    snd = strips.new_sound("click", scene, channel=1, frame_start=1)
    for s in range(N):
        f = 1 + s * 30
        c = strips.new_effect("flash%d" % s, "COLOR", channel=2, frame_start=f, length=3)
        c.color = (1, 1, 1)
    video_out(out)
    r.ffmpeg.audio_codec = "AAC"
    r.ffmpeg.audio_mixrate = 48000
    t = time.perf_counter()
    bpy.ops.render.render(animation=True)
    print("BENCH " + json.dumps({"job": job, "wall_s": time.perf_counter() - t}))
    sys.exit(0)

r.engine = "BLENDER_EEVEE"
r.fps = 60
sc.frame_start, sc.frame_end = 1, N
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = (0, -12, 8)
cam.rotation_euler = (math.radians(55), 0, 0)
lt = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sc.collection.objects.link(lt)
lt.rotation_euler = (0.6, 0.2, 0.3)


def gn_instances(n):
    me = bpy.data.meshes.new("base")
    ob = bpy.data.objects.new("grid", me)
    sc.collection.objects.link(ob)
    ng = bpy.data.node_groups.new("inst", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    grid = ng.nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = 10
    grid.inputs["Size Y"].default_value = 10
    grid.inputs["Vertices X"].default_value = n
    grid.inputs["Vertices Y"].default_value = n
    cube = ng.nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = (0.06, 0.06, 0.06)
    inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
    outn = ng.nodes.new("NodeGroupOutput")
    ng.links.new(grid.outputs["Mesh"], inst.inputs["Points"])
    ng.links.new(cube.outputs["Mesh"], inst.inputs["Instance"])
    ng.links.new(inst.outputs["Instances"], outn.inputs[0])
    ob.modifiers.new("gn", "NODES").node_group = ng
    ob.rotation_euler = (0, 0, 0)
    ob.keyframe_insert("rotation_euler", frame=1)
    ob.rotation_euler = (0, 0, math.radians(90))
    ob.keyframe_insert("rotation_euler", frame=max(N, 2))


if scene == "instanced":
    gn_instances(100)
else:
    gn_instances(30)
    ng = bpy.data.node_groups.new("comp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    prev = ng.nodes.new("CompositorNodeRLayers").outputs["Image"]
    for i in range(4):
        b = ng.nodes.new("CompositorNodeBlur")
        ins = {s.name: s for s in b.inputs}
        if "Size" in ins:
            try:
                ins["Size"].default_value = (20, 20)
            except Exception:
                ins["Size"].default_value = 20
        ng.links.new(prev, b.inputs[0])
        prev = b.outputs[0]
    ng.links.new(prev, ng.nodes.new("NodeGroupOutput").inputs[0])
    sc.compositing_node_group = ng

if job == "stills":
    r.image_settings.file_format = "PNG"
    times = []
    for f in range(1, N + 1):
        sc.frame_set(f)
        r.filepath = "%s/f%04d.png" % (out, f)
        t = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        times.append(time.perf_counter() - t)
    print("BENCH " + json.dumps({"job": job, "frame_s": times}))
elif job == "pngseq":
    r.image_settings.file_format = "PNG"
    r.filepath = out.rstrip("/") + "/f"
    bpy.ops.render.render(animation=True)
    print("BENCH " + json.dumps({"job": job}))
else:
    video_out(out)
    t = time.perf_counter()
    bpy.ops.render.render(animation=True)
    print("BENCH " + json.dumps({"job": job, "wall_s": time.perf_counter() - t}))
