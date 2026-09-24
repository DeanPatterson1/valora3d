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


def make_glb(kind, out):
    """kind: 'rigged' (bone swings a cube 90 deg over frames 1-24), 'details' (glossy cube +
    small lamp) or 'scaled' (200-unit off-centre cube)."""
    code = {"rigged": _RIGGED, "details": _DETAILS, "scaled": _SCALED}[kind]
    script = Path(out).with_suffix(".py")
    script.write_text(code, encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script), "--", str(out)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and Path(out).exists(), proc.stderr[-2000:]
    return Path(out)
