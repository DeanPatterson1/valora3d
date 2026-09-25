"""Generate small test GLBs inside headless Blender. Test-only; never shipped."""
import subprocess
from pathlib import Path

from engine.ingest.run import BLENDER

_RIGGED = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0.8))
cube = bpy.context.object
arm_data = bpy.data.armatures.new("Rig")
arm = bpy.data.objects.new("Rig", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
b = arm_data.edit_bones.new("Bone"); b.head = (0, 0, 0); b.tail = (0, 0, 1)
bpy.ops.object.mode_set(mode="OBJECT")
vg = cube.vertex_groups.new(name="Bone"); vg.add(list(range(len(cube.data.vertices))), 1.0, "REPLACE")
mod = cube.modifiers.new("Armature", "ARMATURE"); mod.object = arm
pb = arm.pose.bones["Bone"]; pb.rotation_mode = "XYZ"
pb.rotation_euler = (0, 0, 0); pb.keyframe_insert("rotation_euler", frame=1)
pb.rotation_euler = (1.5708, 0, 0); pb.keyframe_insert("rotation_euler", frame=24)
bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=True)
'''

_DETAILS = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    for k, v in kw.items(): n.inputs[k].default_value = v
    return m
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
body = bpy.context.object; body.data.materials.append(mat("gloss", Metallic=1.0, Roughness=0.1))
# A 6x6 grid, not a single quad: a detail cluster needs >= 3 samples.
bpy.ops.mesh.primitive_grid_add(x_subdivisions=6, y_subdivisions=6, size=0.1, location=(0.3, -0.501, 0.8), rotation=(1.5708, 0, 0))
lamp = bpy.context.object
lamp.data.materials.append(mat("lamp", **{"Emission Color": (1, 1, 1, 1), "Emission Strength": 5.0}))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''


# A 200-unit cube authored off-centre. measure.infer_units tries mm before cm, so ingest
# reads it as millimetres (scaleFactor 0.001, a 0.2 m subject).
# Task 19 uses it to prove placement handles a non-unit scale and a non-zero source centre.
_SCALED = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=200, location=(30, -40, 100))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''

_MATS = r'''
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    for k, v in kw.items(): n.inputs[k].default_value = v
    return m
'''

# A car-like block on four separate wheels (tyre torus + rim + an off-axis caliper), axle along x.
# Tyre outer radius 0.35, inner 0.21 (tyreBand ~0.6), tube 0.14 wide. Body 1.4 x 4.0, z 0.20-1.25: the
# wheel top (0.70) must sit inside wheels()' vote band (z <= 0.6 H), as on a real car, H / L 0.31 (sport).
_WHEELED = r'''
import bpy, sys, math
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
''' + _MATS + r'''
rubber, metal, paint = mat("rubber", Roughness=0.9), mat("rim", Metallic=1.0, Roughness=0.3), mat("paint", Metallic=0.0, Roughness=0.2)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.625)); b = bpy.context.object  # ride 0.1 m = 0.29 r: sport
b.scale = (1.4, 4.0, 1.05); b.data.materials.append(paint)
bpy.ops.object.transform_apply(scale=True)
for x in (-0.8, 0.8):
    for y in (-1.3, 1.3):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.28, minor_radius=0.07, major_segments=64, minor_segments=16,
                                         location=(x, y, 0.35), rotation=(0, math.pi / 2, 0))
        bpy.context.object.data.materials.append(rubber)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.21, depth=0.12, vertices=48, location=(x, y, 0.35),
                                            rotation=(0, math.pi / 2, 0))
        bpy.context.object.data.materials.append(metal)
        bpy.ops.mesh.primitive_cube_add(size=0.08, location=(x, y + 0.12, 0.47))  # caliper: inside the wheel, off the axle
        bpy.context.object.data.materials.append(metal)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''

# A camera-sized box on a pedestal with a thin strap hanging from its side (top touches the box).
_STRAP = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
''' + _MATS + r'''
body = mat("body", Roughness=0.5)
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.30, location=(0, 0, 0.15)); bpy.context.object.data.materials.append(body)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.36)); c = bpy.context.object
c.scale = (0.20, 0.10, 0.12); bpy.ops.object.transform_apply(scale=True); c.data.materials.append(body)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.104, 0, 0.345)); s = bpy.context.object
s.scale = (0.004, 0.012, 0.15); bpy.ops.object.transform_apply(scale=True); s.data.materials.append(mat("strap", Roughness=0.9))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''

# A soft round cushion-like object: fabric-rough, 0.3 m, resting on its base.
_PLUSH = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
''' + _MATS + r'''
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, segments=48, ring_count=24, location=(0, 0, 0.15))
bpy.context.object.data.materials.append(mat("felt", Roughness=0.95, **{"Sheen Weight": 1.0}))  # cloth: sheen
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''


def make_glb(kind, out):
    """kind: 'rigged' (bone swings a cube 90 deg over frames 1-24), 'details' (glossy cube +
    small lamp), 'scaled' (200-unit off-centre cube), 'wheeled' (a block on four separate wheels),
    'strap' (a box on a pedestal with a hanging strap) or 'plush' (a soft fabric sphere)."""
    code = {"rigged": _RIGGED, "details": _DETAILS, "scaled": _SCALED,
            "wheeled": _WHEELED, "strap": _STRAP, "plush": _PLUSH}[kind]
    script = Path(out).with_suffix(".py")
    script.write_text(code, encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script), "--", str(out)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and Path(out).exists(), proc.stderr[-2000:]
    return Path(out)
