"""Run inside Blender: material contracts, not a substitute for visual review.

blender -b --factory-startup --python-exit-code 1 --python check_surface_materials.py
"""
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_materials import calibrate_materials
from surface_detail import thin_lens
import component_materials
import film_camera
import rain_look
import rain_scene
from mathutils import Vector


def make(name, coat, color=(.25, .04, .12, 1)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Coat Weight'].default_value = coat
    mesh = bpy.data.meshes.new(name)
    mesh.materials.append(mat)
    return bpy.data.objects.new(name, mesh), shader


gloss, gs = make('mv-unified-paint', 1)
matte, ms = make('mv-unified-paint', 0)
unknown, us = make('Authored satin pearl', .4)
glass, ws = make('mv-window-tint', 1)
rubber, rs = make('Rubber', 0)
before = {s: tuple(s.inputs['Base Color'].default_value) for s in (gs, ms, us, ws, rs)}
matte_roughness = ms.inputs['Roughness'].default_value
unknown_nodes = len(us.id_data.nodes)
report = calibrate_materials([gloss, matte, unknown, glass, rubber], wet=True)
assert all(tuple(s.inputs['Base Color'].default_value) == value for s, value in before.items())
assert gs.inputs['Coat Normal'].is_linked and gs.inputs['Coat Roughness'].is_linked
assert not ms.inputs['Coat Normal'].is_linked
assert ms.inputs['Roughness'].default_value == matte_roughness
assert len(us.id_data.nodes) == unknown_nodes
assert ws.inputs['Alpha'].default_value == 1 and ws.inputs['Transmission Weight'].default_value == 0
assert rs.inputs['Normal'].is_linked and rs.inputs['Roughness'].is_linked
# Thin lens substitution must not swallow partial opacity or authored volume.
lens, ls = make('mv-smoke-lens', 0)
ls.inputs['Transmission Weight'].default_value = 1
ls.inputs['Alpha'].default_value = .4
assert not thin_lens(ls)
ls.inputs['Alpha'].default_value = 1
volume = ls.id_data.nodes.new('ShaderNodeVolumeAbsorption')
output = ls.id_data.nodes.get('Material Output')
link = ls.id_data.links.new(volume.outputs[0], output.inputs['Volume'])
assert not thin_lens(ls)
ls.id_data.links.remove(link)
assert thin_lens(ls)
assert output.inputs['Surface'].links[0].from_node.type == 'MIX_SHADER'

# One browser smoke rule covered both the shell and the internal lenses.
# Only the inspected asset may split those roles; shared sources stay intact.
cover, cs = make('mv-smoke-lens', 0, (.35, .40, .42, 1))
cover.name = 'headlight-l-lens-9'
inside = bpy.data.objects.new('headlight-l-lens-5', cover.data.copy())
cs.inputs['Transmission Weight'].default_value = 1
outer_color = tuple(cs.inputs['Base Color'].default_value)
assert component_materials.prepare([cover, inside], 'another-car', wet=True) == []
assert cover.data.materials[0] == inside.data.materials[0]
roles = component_materials.prepare([cover, inside], component_materials.MANTHEY_992, wet=True)
assert [r['role'] for r in roles] == ['cover', 'internal-optic']
assert cover.data.materials[0] != inside.data.materials[0]
assert tuple(cover.data.materials[0].node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value) == outer_color
assert cover.data.materials[0]['mv_wet_surface']
assert not inside.data.materials[0].get('mv_wet_surface', False)
assert tuple(cs.inputs['Base Color'].default_value) == outer_color

caliper, bs = make('Brakes', 0)
caliper.name = 'caliper-front-l'
bs.inputs['Metallic'].default_value = .8
bs.inputs['Roughness'].default_value = 1
caliper_color = tuple(bs.inputs['Base Color'].default_value)
assert component_materials.prepare([caliper], component_materials.MANTHEY_992)[0]['role'] == 'painted-caliper'
corrected = caliper.data.materials[0].node_tree.nodes.get('Principled BSDF')
assert corrected.inputs['Metallic'].default_value == 0
assert tuple(corrected.inputs['Base Color'].default_value) == caliper_color
assert bs.inputs['Metallic'].default_value > .79  # Shared source untouched.

# Flat disc faces can be repaired without re-smoothing walls or moving vertices.
bpy.ops.mesh.primitive_cube_add(size=1)
rotor = bpy.context.object
rotor.scale = (.02, 1, 1)
bpy.context.view_layer.update()
for face in rotor.data.polygons:
    face.use_smooth = True
wrong = tuple(Vector((.5, .5, .7071)).normalized())
rotor.data.normals_split_custom_set([wrong] * len(rotor.data.loops))
positions = [tuple(v.co) for v in rotor.data.vertices]
before_normals = [tuple(n.vector) for n in rotor.data.corner_normals]
assert component_materials.rotor_face_normals(rotor) == 2
assert [tuple(v.co) for v in rotor.data.vertices] == positions
for face in rotor.data.polygons:
    for index in face.loop_indices:
        n = rotor.data.corner_normals[index].vector
        if abs(face.normal.x) > .999:
            assert n.dot(face.normal) > .999
        else:
            assert (n - Vector(before_normals[index])).length < .0001

# The new unequal shot intervals remain valid for short smoke jobs too.
for total in (1, 2, 3, 7, 12, 144, 150):
    previous = -1
    for offset in range(total):
        index, t = film_camera.shot_at(offset, total)
        assert 0 <= index < len(film_camera.SHOT_NAMES) and 0 <= t <= 1
        assert index >= previous
        previous = index
print('PASS: colors, matte finish, unknown materials, privacy opacity, physical surface detail and lens safeguards')
print('PASS: asset-scoped optical roles, original cover tint, caliper pigment/shared materials, unequal camera cuts')

# The rainy look is an explicit art treatment; conservative calibration above
# must remain available for other scenes and unsupported source materials.
yellow, ys = make('mv-unified-paint', 1, (.687, .761, .068, 1))
blue, blues = make('mv-unified-paint', 1, (.02, .08, .4, 1))
flat, flats = make('mv-unified-paint', 0, (.687, .761, .068, 1))
tinted, ts = make('mv-window-tint', 0, (.003, .003, .0037, 1))
mapped, maps = make('mv-unified-paint', 1, (.687, .761, .068, 1))
metallic, metals = make('mv-unified-paint', 1, (.687, .761, .068, 1))
metals.inputs['Metallic'].default_value = .75
authored_glass, ags = make('mv-window-tint', 0, (.003, .003, .0037, 1))
ags.inputs['Transmission Weight'].default_value = .5
tex = maps.id_data.nodes.new('ShaderNodeTexImage')
maps.id_data.links.new(tex.outputs['Color'], maps.inputs['Base Color'])
subjects = [yellow, blue, flat, tinted, mapped, metallic, authored_glass]
assert rain_look.car_materials(subjects, 'unsupported-car', 1) == []
pigment = tuple(ys.inputs['Base Color'].default_value)
result = rain_look.car_materials(subjects, component_materials.MANTHEY_992, 1)
assert sorted(r['treatment'] for r in result) == ['lightly-tinted-window', 'muted-yellow-lacquer']
assert tuple(ys.inputs['Base Color'].default_value) == pigment
assert ys.inputs['Base Color'].links[0].from_node.type == 'HUE_SAT'
assert not blues.inputs['Base Color'].is_linked and not flats.inputs['Base Color'].is_linked
assert maps.inputs['Base Color'].links[0].from_node == tex
assert metals.inputs['Metallic'].default_value == .75 and not metals.inputs['Base Color'].is_linked
assert ags.inputs['Transmission Weight'].default_value == .5
assert ags.id_data.nodes.get('Material Output').inputs['Surface'].links[0].from_node == ags
assert ts.inputs['Transmission Weight'].default_value == 0  # original retained, disconnected
assert ts.id_data.nodes.get('Material Output').inputs['Surface'].links[0].from_node.type == 'MIX_SHADER'
assert rain_look.car_materials(subjects, component_materials.MANTHEY_992, 1) == []  # idempotent
print('PASS: rainy look car/color/finish/texture scope, explicit window override, original pigment, idempotence')

# Overcast daylight: the photographed sky is the only softbox. The real sky,
# backdrop and look code run here; the park, car and beads are not needed.
STRIPS = ('Rain — top front softbox', 'Rain — long side reflection', 'Rain — rear edge light')
CENTER, LOW, EXTENT = Vector((0, 0, .75)), Vector((-1, -2.4, 0)), Vector((2, 4.8, 1.5))
TOTAL = 144


def look_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rain_scene.environment(scene, Vector((0, 0, 0)), 1)
    rain_scene.park_ground(Vector((0, 0, 0)), 1)
    rain_look.environment(scene, CENTER, LOW, 1)
    rain_look.link_reflections(scene, [])
    return scene


def keys(owner):
    action = owner.animation_data.action
    return [key for layer in action.layers for strip in layer.strips for bag in strip.channelbags
            for curve in bag.fcurves for key in curve.keyframe_points]


assert rain_look.LOOK['strip_energy'] == 0
scene = look_scene()
background = scene.world.node_tree.nodes['Background']
assert not background.inputs['Strength'].is_linked and background.inputs['Strength'].default_value == 1
grade = background.inputs['Color'].links[0].from_node
assert grade.type == 'HUE_SAT' and grade.inputs['Color'].links[0].from_node.type == 'TEX_ENVIRONMENT'
# No strips, no bounce or fill rectangles, and no flag over the car: every one
# of them showed up as a studio reflection in wet paint and standing water.
assert not [obj.name for obj in scene.objects if obj.type == 'LIGHT']
assert not [obj.name for obj in bpy.data.objects if obj.name in STRIPS or 'flag' in obj.name.lower()]
assert sorted(obj.name for obj in scene.objects) == ['Rain — distant park background', 'Rain — light courtyard haze']

# A photographer meters each setup, and holds a reflector board beside the
# wheel for that one shot. Both change on the cut, never inside a shot.
assert rain_look.compositor(scene, 1)
board = rain_look.wheel_reflector(scene, [], CENTER, EXTENT, LOW, 1)
assert board.light_linking.receiver_collection is not None, 'The board must not light the wet road'
rain_look.animate_reflections(scene, 1, TOTAL)  # Nothing to animate without strips.
rain_look.animate_exposure(scene, 1, TOTAL)
meter = scene.compositing_node_group.nodes['Rain film — per-shot metering']
stops, fill = rain_look.LOOK['shot_exposure'], rain_look.LOOK['wheel_reflector']
assert len(stops) == len(film_camera.SHOT_NAMES) and len(set(stops)) > 1 and fill > 0
seen = set()
for frame in range(1, TOTAL + 1):
    scene.frame_set(frame)
    shot = film_camera.shot_at(frame - 1, TOTAL)[0]
    seen.add(shot)
    assert abs(meter.inputs['Exposure'].default_value - stops[shot]) < 1e-6, (frame, shot)
    assert abs(board.data.energy - (fill if shot == 2 else 0)) < 1e-4, (frame, shot, board.data.energy)
    previous = film_camera.shot_at(frame - 2, TOTAL)[0] if frame > 1 else shot
    if previous != shot:
        # The board changes in the closed-shutter gap between the two frames.
        for subframe, expected in ((frame - .75, previous), (frame - .25, shot)):
            scene.frame_set(int(subframe), subframe=subframe % 1)
            assert abs(board.data.energy - (fill if expected == 2 else 0)) < 1e-4, (subframe, board.data.energy)
assert seen == set(range(len(film_camera.SHOT_NAMES)))
for owner in (scene.compositing_node_group, board.data):
    assert {key.interpolation for key in keys(owner)} == {'CONSTANT'}
print('PASS: default look has sky strength 1.0 and no strips, fill rectangles or flag;',
      'per-shot metering', stops, 'and a car-only wheel reflector on shot 2 alone, constant keys')

# An art-directed job may still ask for the strips. They then step down
# exactly at the close-up cuts without ramps, and never light the road.
rain_look.configure({'strip_energy': 1.0})
try:
    scene = look_scene()
finally:
    rain_look.configure({'strip_energy': 0.0})
lights = {obj.name: obj.data for obj in scene.objects if obj.type == 'LIGHT'}
assert sorted(lights) == sorted(STRIPS)
assert all(scene.objects[name].light_linking.receiver_collection is not None for name in STRIPS)
full = {name: data.energy for name, data in lights.items()}
assert all(energy > 0 for energy in full.values())
rain_look.animate_reflections(scene, 1, TOTAL)
import math as _math
_wheel, _lamp = (_math.ceil(film_camera.SHOT_BOUNDARIES[i] * TOTAL) + 1 for i in (2, 3))  # first frame of each shot
_trim = rain_look.LOOK['key_per_shot']
for frame, factor in [(1, _trim[0]), (_wheel - 1, _trim[1]), (_wheel, _trim[2]), (_lamp - 1, _trim[2]), (_lamp, _trim[3]), (TOTAL, _trim[4])]:
    scene.frame_set(frame)
    for name, data in lights.items():
        assert abs(data.energy - full[name] * factor) < .001, (frame, name, data.energy)
    assert {key.interpolation for data in lights.values() for key in keys(data)} == {'CONSTANT'}
print('PASS: opt-in strip lights are car-only and follow editorial cuts at LOOK key_per_shot')
