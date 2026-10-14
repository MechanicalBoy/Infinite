#!/usr/bin/env python3
"""Tasks v2: each goal now names the node types / words its oracle requires, so a valid alternative
(a Star node for a star, a Ramp node for a gradient) is not failed by an oracle that wanted another node.
One rule for all 30 tasks, applied identically to every arm; no oracle, start patch or solution changes.
Found by the pilot (PILOT.md); held-out goals get the same rule and were not run."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks", "tasks.json")
ADD = {
 "b01": "Use a Shape node with its shape type set to Star.",
 "b04": "Use two Shape nodes with different shape types and a Blend node.",
 "b08": "Use a Circle node.",
 "t06": "The replacement is a Circle node.",
 "f01": "Use a Field Pixel node that reads uv.x.",
 "f02": "Use a Field Pixel node, with floor and 8.",
 "f03": "Use a Field Synth whose code uses sin, freq and gate.",
 "f04": "Use a Field Effect node whose code reads in.",
 "f05": "Use a Field Modifier node that writes P.y with sin and t.",
 "f06": "Use a Field Notes node that calls note(...).",
 "f07": "Use a Field Pixel node that reads uv.y.",
 "f08": "Use a Field Synth whose code uses sin and gate.",
 "f09": "Use a Field Effect node that sets out = -in.",
 "f10": "Use a Field Modifier node that writes P.y with length.",
}
d = json.load(open(P))
for t in d["tasks"]:
    if t["id"] in ADD and ADD[t["id"]] not in t["goal_text"]:
        t["goal_text"] = t["goal_text"].rstrip() + " " + ADD[t["id"]]
d["version"] = 2
json.dump(d, open(P, "w"), indent=1)
print(json.dumps({"ok": True, "version": 2, "revised": sorted(ADD)}))
