"""Runs INSIDE Blender (public bpy API only) and prints node trees as JSON on one line.

Written for re-survey from Blender's public Python API docs; contains no Blender code.
Called by `readers.py blender`:
  Blender -b [file.blend] --factory-startup --python tools/re-survey/blender_dump.py -- [--make-fixture]
Output line starts with RE_SURVEY_JSON= so the caller can find it among Blender's own logging.
"""

import json
import sys

import bpy  # noqa: F401  (only exists inside Blender)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def make_fixture():
    """A tiny Geometry Nodes setup so the reader's self-test has something known to read."""
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    mod = obj.modifiers.new("GN", "NODES")
    tree = bpy.data.node_groups.new("re_fixture", "GeometryNodeTree")
    mod.node_group = tree
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nin = tree.nodes.new("NodeGroupInput")
    nout = tree.nodes.new("NodeGroupOutput")
    pts = tree.nodes.new("GeometryNodeDistributePointsOnFaces")
    inst = tree.nodes.new("GeometryNodeInstanceOnPoints")
    pos = tree.nodes.new("GeometryNodeInputPosition")
    setp = tree.nodes.new("GeometryNodeSetPosition")
    tree.links.new(nin.outputs[0], pts.inputs[0])
    tree.links.new(pts.outputs[0], inst.inputs[0])
    tree.links.new(nin.outputs[0], inst.inputs["Instance"])
    tree.links.new(inst.outputs[0], setp.inputs[0])
    tree.links.new(pos.outputs[0], setp.inputs["Offset"])
    tree.links.new(setp.outputs[0], nout.inputs[0])


def socket(s):
    d = {"name": s.name, "type": s.type, "linked": s.is_linked}
    # Field vs single value: the shape is public on sockets in recent Blender (display_shape).
    shape = getattr(s, "display_shape", None)
    if shape:
        d["shape"] = shape
    return d


def dump_tree(tree):
    nodes = []
    for n in tree.nodes:
        d = {"name": n.name, "type": n.bl_idname, "label": n.bl_label,
             "inputs": [socket(s) for s in n.inputs if s.enabled],
             "outputs": [socket(s) for s in n.outputs if s.enabled]}
        dom = getattr(n, "domain", None)
        if dom:
            d["domain"] = dom
        dt = getattr(n, "data_type", None)
        if dt:
            d["data_type"] = dt
        if getattr(n, "node_tree", None) is not None:
            d["group"] = n.node_tree.name
        nodes.append(d)
    links = [{"from": l.from_node.name, "from_socket": l.from_socket.name, "from_type": l.from_socket.type,
              "to": l.to_node.name, "to_socket": l.to_socket.name, "to_type": l.to_socket.type}
             for l in tree.links]
    return {"name": tree.name, "tree_type": tree.bl_idname, "users": tree.users, "nodes": nodes, "links": links}


def main():
    if "--make-fixture" in ARGS:
        make_fixture()
    out = {"blender": bpy.app.version_string, "file": bpy.data.filepath, "trees": [], "modifiers": [], "materials": []}
    for t in bpy.data.node_groups:
        out["trees"].append(dump_tree(t))
    for o in bpy.data.objects:
        for m in o.modifiers:
            out["modifiers"].append({"object": o.name, "type": m.type,
                                     "group": getattr(getattr(m, "node_group", None), "name", None)})
    for m in bpy.data.materials:
        if m.node_tree is not None:
            t = dump_tree(m.node_tree)
            t["name"] = "material:" + m.name
            out["materials"].append(t)
    print("RE_SURVEY_JSON=" + json.dumps(out))


main()
