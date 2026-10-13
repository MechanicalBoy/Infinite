# G Blender by category (geometry, curves, meshes, points, instancing, nodes, light, materials, environment, topology, sculpting): dossier

Status: written 2026-10-13 from Blender's public manual and public Python API reference (the copies bundled with the Blender MCP extension), and from Infinite's own node list. Nothing in Blender was run for this dossier and no Blender source was opened. Infinite's side is read from `--describe`. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/G.md`

## 1. What it is

- A category-by-category comparison of Blender against Infinite's 3D, geometry and visual nodes, extending Block D (which measured only render speed, H264 quality and AV sync on two scenes).
- Reference app: Blender (GPL; behaviour and public documentation only). Infinite is a live audio-visual instrument, Blender a content-creation suite. The question for each row is not "does Infinite have it" but "would a user of a live AV instrument miss it".
- Counts below are from the manual's own file layout: geometry nodes about 150 nodes in 16 groups, shader nodes about 90 in 7 groups, 30 sculpt brushes, 17 deform and 22 generate modifiers.

## 2. Method

- Blender side: the public manual's section list and node pages (`modeling/geometry_nodes`, `render/shader_nodes`, `render/lights`, `modeling/meshes`, `modeling/curves`, `sculpt_paint/sculpting`, `physics`), read as a feature inventory.
- Infinite side: `Infinite --describe "<type>"` for the parameters, options and slots of every node named in the table; node names from `.claude/skills/infinite-patch-authoring/SKILL.md` (319 types, 86 in 3D, 34 in Source, 37 in Compositing).
- A row is marked `lead` only where Infinite has more than Blender in that category, `parity` where both cover what a live user needs, `gap` where Blender has a feature a live user could plausibly want.
- Not done: no Blender session, no timing, no pixel comparison. Where a claim needs a run, the table says so.

## 3. Pillar map

- P7: Meshes and primitives. Blender's add menu has about ten primitives (plane, cube, circle, UV sphere, icosphere, cylinder, cone, torus, grid, monkey). Infinite's 3D category has 30-odd generators: Cube, Rounded Cube, Sphere, Icosphere, Plane, Disc, Cylinder, Cone, Capsule, Tube, Torus, Torus Knot, Prism, Pyramid, the five Platonic solids, Helix, Klein Bottle, Mobius Strip, Supershape, Star 3D, Gear 3D, Arrow 3D, Text 3D, plus Metaballs. Each takes a texture input.
- P7: Mesh editing. Blender is an interactive modeller (extrude region and manifold, inset, bevel, loop cut, knife, poly build, spin, bridge, fill, merge, 50-odd edit operators). Infinite has the procedural subset as nodes: Extrude, Extrude Selected, Subdivide, Solidify, Screw, Mirror, Array, Triangulate, Decimate, Merge by Distance, Wireframe, Delete, Select, Smooth, and Union, Difference and Intersect booleans. Missing as nodes: Bevel, Inset, Remesh, Weld by angle, Edge Split.
- P7: Curves. Blender has Bezier, NURBS and poly curves with a full edit mode, curve-to-mesh with a profile, resample, fillet, trim, and hair curves. Infinite has a Curve node, Curve Ops (Resample, Simplify, Smooth, Offset), Tube and Helix. Missing: a profile sweep (curve to mesh with a chosen cross-section), fillet, trim.
- P7: Points and instancing. Blender: Distribute Points on Faces, in Grid, in Volume; Instance on Points; Realize Instances; Instances to Points; Randomize Transforms; per-instance rotate, scale, translate. Infinite: Distribute Points in Grid, Distribute Points on Faces, Image to Points, Mesh to Points, Points to Vertices, Instance on Points, Particle System, and Field Modifier for per-element transforms driven by expressions, with audio inputs. Missing: Distribute in Volume, a Realize step, a Poisson-disk option to check.
- P4: Geometry nodes against Field. Blender's model is attributes on domains, evaluated by fields, with zones (Simulation, Repeat, For Each Element), bundles and closures. Infinite's model is the Field language (Field Primitive, Field Modifier, Formula, Field Graph) with state as delay sugar and rate inferred. Different shapes of the same idea. Blender's strength is a library of about 150 named operations; Infinite's is that a kernel runs per frame in real time, reads audio and modulation directly, and is text. Missing in Infinite: named-attribute capture and store across nodes, a repeat zone with a count, and a built-in blur-attribute or attribute-statistic operation.
- P7: Lighting. Blender: point, sun, spot, area lights; world lighting; shadows with soft size; light linking; IES profiles. Infinite's Light node: Directional, Point, Sun, Ambient, Spot with angle and penumbra, falloff, orbit per beat. Missing: area light (soft box), light linking, IES. Shadows to be checked in `render_bench` scenes before a verdict.
- P7: Materials and shaders. Blender: Principled BSDF plus about 25 other shader nodes (glass, hair, toon, sheen, volume), 20 texture nodes, node-graph materials. Infinite's Material node already carries the Principled parameter set: metallic, roughness, opacity, emission, ior, transmission, specular, clearcoat, subsurface, sheen, iridescence, anisotropy, dispersion, normal bump. That is parity for one-material-per-node use; Blender's graph (mix two shaders by a texture) has no equivalent except stacking Material nodes with masks, not tested.
- P7: Procedural textures. Blender: brick, checker, gabor, gradient, magic, musgrave, noise, voronoi, wave, white noise. Infinite: Noise, Texture, Ramp, Formula, FieldPixel (any of the ten is a short kernel), Reaction Diffusion, Voronoi Cells in 3D. Parity by capability; a preset for each missing named texture would cost one Field kernel each.
- P7: Environment. Blender: world color, HDRI environment, sky texture (Nishita), volume scatter. Infinite: HDRI node (path, intensity, rotation), Ambient light. Missing: a procedural sky; ignore until a user asks.
- P7: Topology and UV. Blender: retopology tools, Remesh (voxel and quad), Decimate, UV unwrap with seams, UV packing. Infinite: Decimate, Merge by Distance, Delaunay Mesh, Voronoi Cells, Mapping (triplanar). No UV unwrap: Infinite maps textures procedurally and by triplanar projection, which suits generated geometry.
- P7: Sculpting. Blender has 30 brushes, masks, face sets, multires, dyntopo. Infinite has none. Infinite's Displacement, Smooth, Wrap, Twist, Explode and Audio Displacement cover procedural deformation. Interactive sculpting is outside a live instrument.
- P7: Volumes and physics. Blender: OpenVDB volumes, cloth, soft body, rigid body, fluid, smoke, dynamic paint, hair. Infinite: Cloth, Particle System, Ocean, Reaction Diffusion, Metaballs. Missing: rigid body, fluid, volumes.
- P8: Evaluation speed is the one place Infinite is measured: 70 to 300 times faster renders (Block D). A Blender geometry-node tree re-evaluates in the viewport, but no viewport timing was taken here.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P7 | Primitives (about 10) | `src/nodes/Geometry3DNodes.cpp` | lead | ignore: about 25 parametric 3D primitives (Cube, Torus Knot, Klein Bottle, Supershape, Metaballs ...) | `src/nodes/Geometry3DNodes.cpp` |
| P7 | Procedural mesh operators (extrude, subdivide, solidify, array, mirror, booleans, decimate) | `src/nodes/GeometryOpNodes.cpp` | parity | ignore: Extrude, Subdivide, Solidify, Array, Mirror, Decimate, Union/Intersect/Difference present | `src/nodes/GeometryOpNodes.cpp` |
| P7 | Bevel, inset, remesh, weld-by-angle | none | gap | ignore: Merge by Distance welds by distance only; a bevel node is the one candidate, wait for a user to ask; the rest are interactive-modeller tools | census: no Bevel/Inset/Remesh |
| P7 | Curve to mesh with a profile, fillet, trim | `src/nodes/CurveOpsNode.h` | gap | ignore: Tube, Curve Ops; Tube covers the round profile; revisit if a patch needs a custom profile | `src/nodes/CurveOpsNode.h` |
| P7 | Distribute and instance points (faces, grid, volume, realize, randomize) | `src/nodes/GeometryOpNodes.h` | parity | ignore: Distribute Points on Faces / in Grid, Instance on Points; volume and realize missing, Field Modifier covers per-element variation | `src/nodes/GeometryOpNodes.h` |
| P4 | Geometry nodes: fields, attributes, zones, about 150 operations | `src/nodes/FieldElementNode.h` | parity | ignore: Field Modifier; different model; Infinite is real-time, audio-driven and text | `src/nodes/FieldElementNode.h` |
| P7 | Light types (point, sun, spot, area), light linking, IES | `src/nodes/SceneNodes.h` | gap | quality-gap: Light: directional, point, sun, ambient, spot; an area light (soft box) is the one a visual look needs; linking and IES ignored | `src/nodes/SceneNodes.h` |
| P7 | Principled BSDF and the shader graph | `src/nodes/UtilityNodes.h` | parity | ignore: Material; Material has the full Principled set; graph mixing not tested | `src/nodes/UtilityNodes.h` |
| P7 | Procedural textures (10) | `src/nodes/TextureNode.h` | parity | ignore: Texture, Noise, FieldPixel; Texture and Noise cover the common set, anything else is a short FieldPixel kernel | `src/nodes/TextureNode.h` |
| P7 | World and sky (HDRI, Nishita sky) | `src/nodes/EnvironmentNode.h` | gap | ignore: HDRI; HDRI covers the live use; no physical sky | `src/nodes/EnvironmentNode.h` |
| P7 | UV unwrap, retopology | `src/nodes/UtilityNodes.h` | gap | ignore: Mapping (triplanar); no unwrap or retopology; triplanar Mapping suits generated geometry | `src/nodes/UtilityNodes.h` |
| P7 | Sculpting (30 brushes, masks, multires) | none | gap | ignore: interactive authoring, outside a live instrument | census: no sculpt node |
| P7 | Volumes, rigid body, fluid | `src/nodes/SimulationNodes.h` | gap | ignore: Cloth, Particle System only; not live-instrument work; revisit on evidence | `src/nodes/SimulationNodes.h` |
| P8 | Render + encode speed (viewport evaluation not measured) | `src/core/HeadlessJob.cpp` | lead | ignore: headless render; render + encode measured 68 to 300 times Blender in Block D | `dossiers/D.md` |

## 5. Measurements

- Only Block D's numbers apply (`dossiers/D.md`). This dossier measured nothing new.
- Counts used: Blender geometry nodes by group (attribute 6, color 7, curve 6 sub-groups, geometry 9, instances 13, mesh 6 sub-groups, point 9, texture 11, utilities 14); Blender shader nodes (color 14, displacement 4, input 19, output 4, shader 24, textures 13, utilities 8); Infinite 319 node types.

| Not measured | Why | What it needs |
|---|---|---|
| Shadow quality and cost of Infinite's Light node against EEVEE | no shadow scene in `render_bench` | a lit scene in both apps through the same harness |
| Viewport evaluation time of a geometry-node tree | needs a Blender session | `render_bench_blender.py` extended with a timed depsgraph update |
| Mixing two materials by a texture in Infinite | not tried | one patch, stacked Material nodes and a mask |

## 6. Outcomes

- Quests: none.
- Quality gaps: an area (soft box) light in the Light node; every other gap is ignored with a reason in the table.
- Ignored, with reason: sculpting, UV unwrap, volumes, rigid body and fluid (interactive-modeller or simulation-suite features outside a live instrument); bevel and curve profiles (wait for a user who asks).
- Owner sittings needed: none.

## 7. Storage

- Nothing written to ~/re-output by this dossier.
