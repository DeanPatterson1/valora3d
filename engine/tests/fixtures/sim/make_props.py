"""Headless Blender: write the phase-6 sim test props as GLBs (procedural, so CC0 by construction).

    blender --background --factory-startup --python make_props.py -- <out_dir>

Writes can.glb (closed cylinder 66 x 122 mm, metal caps + label band), glass.glb (single-sided open
tumbler 80 x 95 mm, a 0 mm wall, to exercise the thick shell), plate.glb (a 0.5 x 0.3 m x 4 mm prop
pane for shatter) and cube.glb (a 0.1 m cube). Props sit on z = 0. Regenerated when missing
(engine/tests/test_sim_api_probe_blender.py), never committed (var/ is gitignored)."""
import os
import sys

import bmesh
import bpy


def _mat(name, rgba, metallic, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    n.inputs["Base Color"].default_value = rgba
    n.inputs["Metallic"].default_value = metallic
    n.inputs["Roughness"].default_value = roughness
    return m


def _export(obj, path):
    for o in bpy.context.scene.objects:
        o.select_set(o is obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def can(path):
    _reset()
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.033, depth=0.122, location=(0, 0, 0.061))
    o = bpy.context.object
    o.name = "can"
    o.data.materials.append(_mat("metal", (0.8, 0.8, 0.82, 1), 1.0, 0.25))
    o.data.materials.append(_mat("label", (0.7, 0.1, 0.1, 1), 0.0, 0.4))
    for p in o.data.polygons:                     # caps are metal, the side band is the label
        p.material_index = 0 if abs(p.normal.z) > 0.9 else 1
    _export(o, path)


def glass(path):
    _reset()
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.04, depth=0.095, location=(0, 0, 0.0475))
    o = bpy.context.object
    o.name = "glass"
    bm = bmesh.new()
    bm.from_mesh(o.data)
    top = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.delete(bm, geom=top, context="FACES_ONLY")   # open top, single-sided walls
    bm.to_mesh(o.data)
    bm.free()
    o.data.materials.append(_mat("glass", (0.9, 0.95, 1.0, 1), 0.0, 0.05))
    _export(o, path)


def plate(path):
    _reset()
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.002))
    o = bpy.context.object
    o.name = "plate"
    o.scale = (0.5, 0.3, 0.004)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(_mat("pane", (0.9, 0.95, 1.0, 1), 0.0, 0.05))
    _export(o, path)


def cube(path):
    _reset()
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0.05))
    o = bpy.context.object
    o.name = "cube"
    _export(o, path)


PROPS = {"can.glb": can, "glass.glb": glass, "plate.glb": plate, "cube.glb": cube}


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(out, exist_ok=True)
    for name, make in PROPS.items():
        make(os.path.join(out, name))


if __name__ == "__main__":
    main()
