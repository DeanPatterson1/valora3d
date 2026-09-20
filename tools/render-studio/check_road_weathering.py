"""CPU/no-render Blender contracts for the driven-in-the-rain material pass.

blender -b --factory-startup --python-exit-code 1 --python check_road_weathering.py
Reads the baseline GLB; never saves or renders. Covers road_weathering.py, the
lacquered caliper, used tyre rubber and the metallic-flake gate.
"""
from array import array
from contextlib import redirect_stdout
import hashlib
import io
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import component_materials
import rain_look
import road_weathering
import surface_detail
from render_materials import calibrate_materials

CAR = component_materials.MANTHEY_992


def fingerprint(mesh):
    coordinates = array('f', [0]) * (3 * len(mesh.vertices))
    mesh.vertices.foreach_get('co', coordinates)
    vertices = array('i', [0]) * len(mesh.loops)
    mesh.loops.foreach_get('vertex_index', vertices)
    return hashlib.sha256(coordinates.tobytes() + vertices.tobytes()).hexdigest()


def snapshot():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with redirect_stdout(io.StringIO()):
        bpy.ops.import_scene.gltf(filepath=str(ROOT / 'checks/black-final/snapshot.glb'))
    bpy.context.view_layer.update()
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return meshes, max(high - low) / 4.8, low, high


def principled(material):
    return next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def same(color, reference):
    """Sockets store float32; module constants are Python floats."""
    return all(abs(a - b) < 1e-6 for a, b in zip(color, reference))


def upstream(socket, found=None):
    found = {} if found is None else found
    for link in socket.links:
        if link.from_node.name not in found:
            found[link.from_node.name] = link.from_node
            for source in link.from_node.inputs:
                upstream(source, found)
    return found


def evaluate(socket, position):
    """A scalar socket at a world position. Unknown node types are an error."""
    if not socket.is_linked:
        return socket.default_value
    link = socket.links[0]
    node = link.from_node
    if node.type == 'SEPXYZ':
        assert node.inputs[0].links[0].from_node.type == 'NEW_GEOMETRY'
        return position[list(node.outputs).index(link.from_socket)]
    if node.type == 'MATH':
        a, b = (evaluate(node.inputs[index], position) for index in (0, 1))
        result = {'ADD': lambda: a + b, 'SUBTRACT': lambda: a - b, 'MULTIPLY': lambda: a * b,
                  'MAXIMUM': lambda: max(a, b), 'EXPONENT': lambda: math.exp(a)}.get(node.operation)
        assert result is not None, 'Uninterpreted math operation: ' + node.operation
        value = result()
        return min(1, max(0, value)) if node.use_clamp else value
    if node.type == 'MAP_RANGE':
        value, start, end, at_start, at_end = (evaluate(node.inputs[name], position) for name in
                                               ('Value', 'From Min', 'From Max', 'To Min', 'To Max'))
        assert node.interpolation_type == 'SMOOTHSTEP', node.interpolation_type
        t = min(1, max(0, (value - start) / (end - start)))
        return at_start + t * t * (3 - 2 * t) * (at_end - at_start)
    raise AssertionError('Spray envelope uses an uninterpreted node: ' + node.bl_idname)


def prepared():
    meshes, scale, low, high = snapshot()
    component_materials.prepare(meshes, CAR, wet=True, scale=scale)
    calibrate_materials(meshes, wet=True, scale=scale)
    surface_detail.tire_sidewalls(meshes, scale, wet=True)
    rain_look.car_materials(meshes, CAR, scale)
    return meshes, scale, low, high


# A layer set to zero leaves no trace: no group, no node, no flag.
meshes, scale, low, high = prepared()
counts = {m.name: len(m.node_tree.nodes) for m in bpy.data.materials if m.use_nodes}
assert road_weathering.apply(meshes, low, high, scale, {'road_film': 0, 'brake_dust': 0}) == {'roadFilm': [], 'brakeDust': []}
assert road_weathering.MASK_GROUP not in bpy.data.node_groups
assert all(len(m.node_tree.nodes) == counts[m.name] for m in bpy.data.materials if m.use_nodes)
print('PASS: both weathering layers scale to nothing at strength 0')

# Scope, preservation and idempotence on the real car.
meshes, scale, low, high = prepared()
before = {obj.name: fingerprint(obj.data) for obj in meshes}
car_materials = {m for obj in meshes for m in obj.data.materials if m and m.use_nodes}
pigment = {}
for material in car_materials:
    color = principled(material).inputs['Base Color']
    pigment[material.name] = color.links[0].from_node.name if color.is_linked else tuple(color.default_value)
report = road_weathering.apply(meshes, low, high, scale, rain_look.LOOK)
assert len([g for g in bpy.data.node_groups if g.name.startswith(road_weathering.MASK_GROUP)]) == 1
mask = bpy.data.node_groups[road_weathering.MASK_GROUP]
filmed = set(report['roadFilm'])
for material in car_materials:
    name = material.name.lower()
    groups = [n for n in material.node_tree.nodes if n.type == 'GROUP' and n.node_tree == mask]
    wanted = ((name.startswith(('mv-unified-paint', 'mv-carbon-weave')) and 'interior' not in name)
              or material.get('mv_rain_look') in ('satin-trim', 'semi-gloss-trim'))
    assert (material.name in filmed) == wanted == (len(groups) == 1), material.name
    if not wanted:
        continue
    shader = principled(material)
    sources = upstream(shader.inputs['Base Color'])
    # The film mixes toward a pigment; the authored colour stays upstream.
    original = pigment[material.name]
    if isinstance(original, str):
        assert original in sources, material.name
    else:
        assert tuple(sources['Rain — road film pigment'].inputs[1].default_value) == original
    assert same(sources['Rain — road film pigment'].inputs[2].default_value, road_weathering.FILM_COLOR)
    lacquered = shader.inputs['Coat Weight'].is_linked or shader.inputs['Coat Weight'].default_value > .01
    assert shader.inputs['Coat Roughness'].is_linked == lacquered or not lacquered, material.name
assert any(n.startswith('mv-unified-paint') for n in filmed) and any(n.startswith('mv-carbon-weave') for n in filmed)
assert not any(n.lower().startswith(('mv-window-tint', 'mv-smoke-lens', 'rubber', 'rims', 'render tire')) for n in filmed)
assert report['brakeDust'] == ['Rims'], report['brakeDust']
rims = bpy.data.materials['Rims']
assert any(n.type == 'AMBIENT_OCCLUSION' for n in rims.node_tree.nodes)
assert same(rims.node_tree.nodes['Rain — brake dust pigment'].inputs[2].default_value, road_weathering.DUST_COLOR)
counts = {m.name: len(m.node_tree.nodes) for m in car_materials}
assert road_weathering.apply(meshes, low, high, scale, rain_look.LOOK) == {'roadFilm': [], 'brakeDust': []}
assert all(len(m.node_tree.nodes) == counts[m.name] for m in car_materials)
assert all(fingerprint(obj.data) == before[obj.name] for obj in meshes)
print('PASS: one shared film mask on', len(filmed), 'exterior paint, carbon and trim materials; glass, lenses, rubber,',
      'interior and wheels excluded; authored pigment upstream; idempotent; all source geometry intact')

# Where spray lands. The envelope is the mask before its streak and speckle
# textures, evaluated here with the same node math Cycles runs.
envelope = mask.nodes[road_weathering.ENVELOPE].outputs[0]
wheels = road_weathering.wheel_centres(meshes, scale)
assert len(wheels) == 4, wheels
front = min((w for w in wheels if w.x > 0), key=lambda w: w.y)
side = high.x
at = lambda x, y, metres: evaluate(envelope, (x, y, low.z + metres * scale))
assert at(0, 0, (high.z - low.z) / scale) == 0 and at(side, 0, 1.0) == 0
assert at(side, (low.y + high.y) / 2, .12) > .6
behind, ahead = at(front.x, front.y + .62 * scale, .5), at(front.x, front.y - .62 * scale, .5)
door = at(front.x, front.y + 1.9 * scale, .7)
assert behind > 2 * ahead and at(front.x, front.y + .62 * scale, .7) > 2 * door, (behind, ahead, door)
assert at(0, high.y - .02 * scale, .5) > 3 * at(0, low.y + .02 * scale, .5)
samples = [at(x * side, low.y + t * (high.y - low.y), h) for x in (-1, 0, 1) for t in (0, .25, .5, .75, 1) for h in (0, .3, .6, .9, 1.4)]
assert all(0 <= value <= 1 for value in samples)
print('PASS: spray sits on the sills, climbs behind each wheel rather than ahead of it, coats the tail more than the',
      'nose and never reaches the roof; behind/ahead of the front wheel at 0.5 m:', round(behind, 3), round(ahead, 3))

# An authored wheel map carries its own wear.
mapped = bpy.data.materials.new('Rims')
mapped.use_nodes = True
mapped.node_tree.nodes.new('ShaderNodeTexImage')
mesh = bpy.data.meshes.new('wheel-contract')
mesh.materials.append(mapped)
wheel = bpy.data.objects.new('wheel-contract', mesh)
assert road_weathering.brake_dust([wheel], 1, .5) == []
print('PASS: image-mapped wheels keep their authored finish')

# Painted calipers: pigment under clear lacquer, colour untouched.
calipers = [m for m in bpy.data.materials if m.name.startswith('Render caliper coating')]
source = principled(bpy.data.materials['Brakes']).inputs['Base Color']
assert len(calipers) == 4
for material in calipers:
    shader = principled(material)
    assert shader.inputs['Metallic'].default_value == 0 and shader.inputs['Coat Weight'].default_value == 1
    assert shader.inputs['Coat Normal'].is_linked and shader.inputs['Coat Roughness'].is_linked
    assert not shader.inputs['Base Color'].is_linked and not source.is_linked
    assert tuple(shader.inputs['Base Color'].default_value) == tuple(source.default_value)
print('PASS: four calipers are dielectric pigment under orange-peel lacquer in their selected colour')

# A driven tyre: brown sidewall bloom and a drier scrubbed tread face, wet only.
tyres = [m for m in bpy.data.materials if m.name.startswith('Render tire sidewall')]
assert len(tyres) == 4
for material in tyres:
    nodes = material.node_tree.nodes
    band = nodes['Tread face, by normalized wheel radius']
    assert nodes.get('Sidewall antiozonant bloom') and nodes.get('Road-scrubbed tread face')
    assert band.inputs['From Min'].default_value > .94, 'tread band must start outside the .76 to .94 sidewall band'
    assert 'Road-scrubbed tread face' in upstream(principled(material).inputs['Base Color'])
meshes, scale, low, high = snapshot()
calibrate_materials(meshes, wet=False, scale=scale)
surface_detail.tire_sidewalls(meshes, scale)
assert not any(m.node_tree.nodes.get('Sidewall antiozonant bloom') for m in bpy.data.materials if m.use_nodes)
print('PASS: used-rubber colour and a dry tread face on four wet tyres; dry scenes unchanged')


# Flake belongs to a metallic finish under lacquer, and never tilts the lacquer.
def paint(metallic, coat):
    material = bpy.data.materials.new('mv-unified-paint')
    material.use_nodes = True
    shader = principled(material)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Coat Weight'].default_value = coat
    mesh = bpy.data.meshes.new('paint-contract')
    mesh.materials.append(material)
    return bpy.data.objects.new('paint-contract', mesh), shader


cases = {'metallic': paint(.6, 1), 'solid': paint(.04, 1), 'gloss': paint(.08, 1), 'frozen': paint(.10, .30), 'matte metal': paint(.6, 0)}
calibrate_materials([obj for obj, _ in cases.values()], wet=True, scale=1)
for label, (_, shader) in cases.items():
    flake = shader.id_data.nodes.get('Metallic flake platelets')
    assert bool(flake) == (label == 'metallic'), label
metallic = cases['metallic'][1]
assert 'Metallic flake platelets' in upstream(metallic.inputs['Normal'])
assert metallic.inputs['Coat Normal'].is_linked and 'Metallic flake platelets' not in upstream(metallic.inputs['Coat Normal'])
cells = metallic.id_data.nodes['Metallic flake platelets']
assert .0002 < 1 / cells.inputs['Scale'].default_value < .0005, 'platelets are a fraction of a millimetre'
print('PASS: flake only on a lacquered metallic finish (browser metalness .60), under a smooth coat')
