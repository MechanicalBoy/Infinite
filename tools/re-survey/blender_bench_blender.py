# re-survey blender_bench, Blender side. Runs inside Blender, public bpy API only (no bundled scripts read):
#   Blender -b --factory-startup --python blender_bench_blender.py -- <scene> <size> <frames>
# scene: instance -> <size> x <size> grid points, a cube instanced on each, instance scale animated by scene time
#                    (geometry nodes: Grid -> Instance on Points; Scene Time -> Math -> Scale)
#        subdiv   -> a <size> x <size>-face grid, Subdivision Surface level 2, then Set Position along the normal
#                    by a 4D noise whose W is scene time (re-evaluates every frame)
#        cloth    -> a <size> x <size>-face grid with the Cloth modifier, one edge pinned, falling and swinging, stepped frame by frame
#                    from frame 1 (that is what Bake does: each step fills the point cache)
# Times scene.frame_set(f) for f = 1..frames: one full dependency-graph evaluation per frame, no drawing. This is
# the closest headless proxy for viewport fps; real viewport fps adds GPU drawing and needs the GUI.
# Prints:  BENCH {"scene": ..., "frame_ms": [...], "elements": {...}, "version": "..."}
import bpy, sys, time, json

argv = sys.argv[sys.argv.index("--") + 1:]
scene_kind, size, frames = argv[0], int(argv[1]), int(argv[2])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 60
sc.frame_start, sc.frame_end = 1, frames


def gn_object(name):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    ob.modifiers.new("gn", "NODES").node_group = ng
    return ob, ng


def scene_time_sin(ng, rate):
    t = ng.nodes.new("GeometryNodeInputSceneTime")
    m = ng.nodes.new("ShaderNodeMath")
    m.operation = "MULTIPLY"
    m.inputs[1].default_value = rate
    ng.links.new(t.outputs["Seconds"], m.inputs[0])
    s = ng.nodes.new("ShaderNodeMath")
    s.operation = "SINE"
    ng.links.new(m.outputs[0], s.inputs[0])
    return s.outputs[0]


elements = {}
if scene_kind == "instance":
    ob, ng = gn_object("inst")
    grid = ng.nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = 10
    grid.inputs["Size Y"].default_value = 10
    grid.inputs["Vertices X"].default_value = size
    grid.inputs["Vertices Y"].default_value = size
    cube = ng.nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = (0.06, 0.06, 0.06)
    inst = ng.nodes.new("GeometryNodeInstanceOnPoints")
    sc_map = ng.nodes.new("ShaderNodeMath")
    sc_map.operation = "MULTIPLY_ADD"
    sc_map.inputs[1].default_value = 0.5
    sc_map.inputs[2].default_value = 1.0
    ng.links.new(scene_time_sin(ng, 3.0), sc_map.inputs[0])
    ng.links.new(grid.outputs["Mesh"], inst.inputs["Points"])
    ng.links.new(cube.outputs["Mesh"], inst.inputs["Instance"])
    ng.links.new(sc_map.outputs[0], inst.inputs["Scale"])
    ng.links.new(inst.outputs["Instances"], ng.nodes.new("NodeGroupOutput").inputs[0])
elif scene_kind == "subdiv":
    ob, ng = gn_object("subdiv")
    grid = ng.nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = 2
    grid.inputs["Size Y"].default_value = 2
    grid.inputs["Vertices X"].default_value = size + 1
    grid.inputs["Vertices Y"].default_value = size + 1
    sub = ng.nodes.new("GeometryNodeSubdivisionSurface")
    sub.inputs["Level"].default_value = 2
    noise = ng.nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 6.0
    t = ng.nodes.new("GeometryNodeInputSceneTime")
    tw = ng.nodes.new("ShaderNodeMath")
    tw.operation = "MULTIPLY"
    tw.inputs[1].default_value = 0.2
    ng.links.new(t.outputs["Seconds"], tw.inputs[0])
    ng.links.new(tw.outputs[0], noise.inputs["W"])
    nrm = ng.nodes.new("GeometryNodeInputNormal")
    sc_v = ng.nodes.new("ShaderNodeVectorMath")
    sc_v.operation = "SCALE"
    amt = ng.nodes.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    amt.inputs[1].default_value = 0.3
    ng.links.new(noise.outputs["Fac"], amt.inputs[0])
    ng.links.new(nrm.outputs[0], sc_v.inputs[0])
    ng.links.new(amt.outputs[0], sc_v.inputs["Scale"])
    setp = ng.nodes.new("GeometryNodeSetPosition")
    ng.links.new(grid.outputs["Mesh"], sub.inputs["Mesh"])
    ng.links.new(sub.outputs["Mesh"], setp.inputs["Geometry"])
    ng.links.new(sc_v.outputs[0], setp.inputs["Offset"])
    ng.links.new(setp.outputs["Geometry"], ng.nodes.new("NodeGroupOutput").inputs[0])
elif scene_kind == "cloth":
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=size, y_subdivisions=size, size=2)
    ob = bpy.context.active_object
    vg = ob.vertex_groups.new(name="pin")
    top = max(v.co.y for v in ob.data.vertices)
    vg.add([v.index for v in ob.data.vertices if abs(v.co.y - top) < 1e-6], 1.0, "REPLACE")
    cl = ob.modifiers.new("cloth", "CLOTH")
    cl.settings.vertex_group_mass = "pin"
    cl.point_cache.frame_start, cl.point_cache.frame_end = 1, frames
    elements["quality_steps"] = cl.settings.quality
else:
    raise SystemExit("unknown scene " + scene_kind)

times = []
for f in range(1, frames + 1):
    t0 = time.perf_counter()
    sc.frame_set(f)
    times.append((time.perf_counter() - t0) * 1000.0)

dg = bpy.context.evaluated_depsgraph_get()
ev = ob.evaluated_get(dg)
if scene_kind == "instance":
    elements["instances"] = sum(1 for i in dg.object_instances if i.is_instance)
else:
    me = ev.to_mesh()
    elements["vertices"] = len(me.vertices)
    elements["faces"] = len(me.polygons)
    if scene_kind == "cloth":
        rest = ob.data.vertices
        elements["moved"] = max((me.vertices[i].co - rest[i].co).length for i in range(len(rest)))  # >0 once it falls
    ev.to_mesh_clear()
print("BENCH " + json.dumps({"scene": scene_kind, "size": size, "frame_ms": times, "elements": elements,
                             "version": bpy.app.version_string}))
