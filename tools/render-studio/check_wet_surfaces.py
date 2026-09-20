"""CPU/no-render Blender contracts for the rain detail treatment.

blender -b --factory-startup --python-exit-code 1 --python check_wet_surfaces.py
Reads the baseline GLB; never saves or renders the baseline scene.
"""
from array import array
from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import rain_scene
import surface_detail
import wet_detail
from render_materials import BEAD_LIMIT, add_water_beads, calibrate_materials


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
    scale = max(max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)) / 4.8
    return meshes, scale


# Unrequested dry-scene appearance remains the established molding treatment.
meshes, scale = snapshot()
calibrate_materials(meshes, wet=False, scale=scale)
before = {obj.name: fingerprint(obj.data) for obj in meshes}
assert surface_detail.tire_sidewalls(meshes, scale) == 4
assert not any(obj.get('mv_render_detail') for obj in bpy.data.objects)
for material in bpy.data.materials:
    if material.name.startswith('Render tire sidewall'):
        assert not material.node_tree.nodes.get('Light irregular tire road residue')
assert all(fingerprint(obj.data) == before[obj.name] for obj in meshes)
print('PASS: dry behavior unchanged; four full tires selected and small rubber pieces rejected')

# Wet tire material/text additions preserve all source vertex/topology data.
meshes, scale = snapshot()
calibrate_materials(meshes, wet=True, scale=scale)
before = {obj.name: fingerprint(obj.data) for obj in meshes}
assert surface_detail.tire_sidewalls(meshes, scale, wet=True) == 4
letters = [obj for obj in bpy.data.objects if obj.get('mv_render_detail') == 'generic_molded_tire_lettering']
assert len(letters) == 4, [obj.name for obj in letters]
assert all(len(obj.data.vertices) > 200 and obj.get('words') == 'PERFORMANCE / ROAD TIRE' for obj in letters)
for obj in letters:
    tire = bpy.data.objects[obj['source_tire']]
    bounds = [tire.matrix_world @ Vector(corner) for corner in tire.bound_box]
    low = Vector(tuple(min(p[i] for p in bounds) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in bounds) for i in range(3)))
    # Letters must sit on the tire envelope; no label around a small attachment.
    assert all(low[i] - .002 * scale <= v.co[i] <= high[i] + .002 * scale
               for v in obj.data.vertices for i in range(3)), obj.name
    mat = tire.data.materials[0]
    assert mat.node_tree.nodes.get('Tire dampness falls away from ground contact')
assert all(fingerprint(obj.data) == before[obj.name] for obj in meshes)
print('PASS: four conformed generic tire inscriptions; wet treatment only; all source geometry intact')

# Actual car water includes multiple physical size populations and sparse trails.
count = add_water_beads(meshes, scale)
cloud = bpy.data.objects.get('Rain — surface water beads')
assert cloud is not None
populations = {key: cloud[key] for key in ('bead_count', 'mist_count', 'merged_count', 'runoff_count')}
assert sum(populations.values()) == count
# BEAD_LIMIT is a safety net, not the allocator. Candidates are spread over the
# whole car first; a count that reaches the cap means sorted object traversal
# ran out and left the later panels dry. Measured 38,037 on this GLB
# (2026-09-17); under 20,000 means wet surfaces lost their flag or half the
# density went missing.
assert 20000 < count < BEAD_LIMIT, (count, BEAD_LIMIT)
# add_water_beads draws one uniform `chance` per accepted point: mist below
# .34, merged drops above .965, runoff above .985 on sloped panels only.
# Measured mist share .338 to .341 over four seeds (binomial sigma .0024) and
# merged + runoff .0356.
mist_share = populations['mist_count'] / count
large_share = (populations['merged_count'] + populations['runoff_count']) / count
assert .31 < mist_share < .37, mist_share
assert .025 < large_share < .045, large_share
assert populations['merged_count'] > 0 and 0 < populations['runoff_count'] < .02 * count
# (width, length, height) maxima per metre of car scale, from the same code.
# A radius r gives width <= 1.12 r, length <= 1.30 r, height <= .74 r, and
# drops of 2.2 mm and over sag to .78 of that height.
LIMITS = {
    3: (.0006 * 1.12, .0006 * 1.30, .0006 * .74),                          # mist, r <= 0.6 mm
    0: (.008 * 1.12, .008 * 1.30, .008 * .74 * .78),                       # beads, r <= 8 mm (rare pooled drops)
    1: (.008 * 1.12 * 1.25, .008 * 1.30 * 2.5, .008 * .74 * .78 * .8),     # merged: 26 mm long
    2: (.00065, .012, .00022),                                             # runoff trails
}
kinds = array('i', [0]) * count
cloud.data.attributes['bead_kind'].data.foreach_get('value', kinds)
sizes = array('f', [0]) * (3 * count)
cloud.data.attributes['bead_scale'].data.foreach_get('vector', sizes)
largest = {kind: [0, 0, 0] for kind in LIMITS}
for index, kind in enumerate(kinds):
    for axis in range(3):
        component = sizes[3 * index + axis]
        # The thinnest water in the model is a 0.1 mm runoff film.
        assert component >= .0001 * scale * (1 - 1e-5), (kind, axis, component)
        largest[kind][axis] = max(largest[kind][axis], component)
for kind, limits in LIMITS.items():
    for axis, limit in enumerate(limits):
        assert largest[kind][axis] <= limit * scale * (1 + 1e-5), (kind, axis, largest[kind][axis], limit * scale)
water = bpy.data.materials['Rain — clean water IOR 1.333'].node_tree.nodes.get('Principled BSDF')
assert abs(water.inputs['IOR'].default_value - 1.333) < 1e-5
assert water.inputs['Transmission Weight'].default_value == 1
assert all(fingerprint(obj.data) == before[obj.name] for obj in meshes)
print('PASS: IOR 1.333 water, source preservation, cap not reached, per-population size limits;',
      'counts:', populations, 'mist share', round(mist_share, 4),
      'longest drop mm', round(max(values[1] for values in largest.values()) / scale * 1000, 2))

# Vertical panels previously fell through the old runoff slope condition.
mesh = bpy.data.meshes.new('Contract vertical wet panel')
mesh.from_pydata([(0, -1, 0), (0, 1, 0), (0, 1, 2), (0, -1, 2)], [], [(0, 1, 2, 3)])
panel = bpy.data.objects.new(mesh.name, mesh)
bpy.context.scene.collection.objects.link(panel)
material = bpy.data.materials.new('Contract wet panel')
material['mv_wet_surface'] = True
mesh.materials.append(material)
old_clouds = set(bpy.data.objects)
add_water_beads([panel], 1)
vertical_cloud = next(obj for obj in bpy.data.objects if obj not in old_clouds)
assert vertical_cloud['runoff_count'] > 0
for kind, rotation in zip(vertical_cloud.data.attributes['bead_kind'].data,
                          vertical_cloud.data.attributes['bead_rotation'].data):
    if kind.value == 2:
        from mathutils import Euler
        down = Euler(rotation.vector).to_matrix() @ Vector((0, 1, 0))
        assert down.dot(Vector((0, 0, -1))) > .999
print('PASS: vertical runoff follows gravity')

# Rained-on asphalt: a water film everywhere, standing water where the road is
# low. The graph is read, not rendered; check_puddle_fields.py bakes the same
# fields through Cycles.
assert (rain_scene.ASSETS / 'asphalt_02_Displacement_2k.exr').is_file(), \
    'Scanned relief missing: run prepare_assets.py, or shorelines fall back to plain noise'
road = rain_scene.wet_asphalt(scale)
bpy.ops.mesh.primitive_plane_add(size=4)
bpy.context.object.data.materials.append(road)
shader = road.node_tree.nodes.get('Principled BSDF')


def upstream(socket, found=None):
    """Every node that can influence a socket, by name."""
    found = {} if found is None else found
    for link in socket.links:
        if link.from_node.name not in found:
            found[link.from_node.name] = link.from_node
            for source in link.from_node.inputs:
                upstream(source, found)
    return found


def evaluate(socket, depth, texture):
    """A socket's value for a forced standing-water depth and texture sample.

    Interprets only the node types the water optics are built from. Anything
    else is an error, never a guess.
    """
    if not socket.is_linked:
        return socket.default_value
    node = socket.links[0].from_node
    if node.name == 'Standing water depth':
        return depth
    if node.type in ('TEX_IMAGE', 'TEX_NOISE'):
        return texture
    if node.type == 'MATH':
        a, b = (evaluate(node.inputs[index], depth, texture) for index in (0, 1))
        result = {'ADD': a + b, 'SUBTRACT': a - b, 'MULTIPLY': a * b,
                  'MAXIMUM': max(a, b), 'MINIMUM': min(a, b)}.get(node.operation)
        assert result is not None, 'Uninterpreted math operation: ' + node.operation
        return min(1, max(0, result)) if node.use_clamp else result
    if node.type == 'MAP_RANGE' and node.data_type == 'FLOAT':
        value, low, high, start, end = (evaluate(node.inputs[name], depth, texture) for name in
                                        ('Value', 'From Min', 'From Max', 'To Min', 'To Max'))
        t = (value - low) / (high - low)
        assert node.interpolation_type in ('LINEAR', 'SMOOTHSTEP'), node.interpolation_type
        if node.interpolation_type == 'SMOOTHSTEP' or node.clamp:
            t = min(1, max(0, t))
        if node.interpolation_type == 'SMOOTHSTEP':
            t = t * t * (3 - 2 * t)
        return start + t * (end - start)
    raise AssertionError('Water optics use an uninterpreted node: ' + node.bl_idname)


assert abs(shader.inputs['Coat IOR'].default_value - 1.333) < 1e-5
# Separate stone and water normals, with the impact rings on the water only.
assert shader.inputs['Normal'].is_linked and shader.inputs['Coat Normal'].is_linked
stone_normal = shader.inputs['Normal'].links[0].from_node
ripple = shader.inputs['Coat Normal'].links[0].from_node
assert stone_normal.type == 'NORMAL_MAP' and ripple.type == 'BUMP'
film_normal = ripple.inputs['Normal'].links[0].from_node
assert film_normal.type == 'NORMAL_MAP' and film_normal != stone_normal
stone_sources = upstream(shader.inputs['Normal'])
assert ripple.name not in stone_sources and 'Rain impact time seconds' not in stone_sources
# Water stands where PUDDLE_LEVEL is above noise + scanned relief, so stones
# break the shoreline. Impacts animate the rings, never the pools.
mask = road.node_tree.nodes['Soft puddle to damp asphalt transition']
assert mask.type == 'MAP_RANGE' and mask.interpolation_type == 'SMOOTHSTEP'
mask_sources = upstream(mask.inputs['Value'])
level = mask_sources['Standing water depth']
assert level.operation == 'SUBTRACT' and not level.inputs[0].is_linked
assert abs(level.inputs[0].default_value - rain_scene.PUDDLE_LEVEL) < 1e-6
assert sum(node.type == 'TEX_NOISE' for node in mask_sources.values()) >= 2
assert any(node.type == 'TEX_IMAGE' and node.image and 'Displacement' in node.image.name
           for node in mask_sources.values())
assert 'Rain impact time seconds' not in mask_sources
ripple_sources = upstream(ripple.inputs['Height'])
assert mask.name in ripple_sources and 'Rain impact time seconds' in ripple_sources
# The optics those nodes produce, from a dry crown (depth -1) to a deep pool.
DRY, POOLED, SAMPLES = (-1, -.075, -.04, 0), (.022, .16, 1), (0, 1)
film_strength = film_normal.inputs['Strength']
weights = [evaluate(shader.inputs['Coat Weight'], depth, 0) for depth in DRY]
assert abs(min(weights) - .62) < 1e-6 and abs(max(weights) - .88) < 1e-6, weights
assert weights == sorted(weights), 'The film thickens toward a pool'
for depth in POOLED:
    for texture in SAMPLES:
        assert abs(evaluate(shader.inputs['Coat Weight'], depth, texture) - 1) < 1e-6
        assert evaluate(shader.inputs['Coat Roughness'], depth, texture) <= .005
        assert evaluate(film_strength, depth, texture) <= .005
stone = [evaluate(shader.inputs['Roughness'], depth, texture) for depth in DRY + POOLED for texture in SAMPLES]
film = [evaluate(shader.inputs['Coat Roughness'], depth, texture) for depth in DRY for texture in SAMPLES]
# Standing water is smoother than the broken film, which is smoother than stone.
assert .005 < min(film) and max(film) < min(stone) and max(stone) < 1, (film, stone)
assert all(evaluate(film_strength, depth, 0) > .2 for depth in DRY), 'The film follows the aggregate'
scene = bpy.context.scene
for first, total, fps in [(1, 1, 24), (1, 2, 24), (1, 7, 30), (1, 144, 24), (101, 150, 30)]:
    scene.render.fps = fps
    assert wet_detail.configure_ripple_animation(scene, first, total) == 1
    for offset in (0, (total - 1) / 2, total - 1):
        frame = first + offset
        scene.frame_set(int(frame), subframe=frame % 1)
        seconds = road.node_tree.nodes['Rain impact time seconds'].outputs[0].default_value
        assert abs(seconds - offset / fps) < 1e-5, (first, total, fps, frame, seconds)
print('PASS: IOR 1.333 water film 0.62–0.88 with optically flat pools; separate stone and film normals;',
      'coat-only ripples off a scanned-relief shoreline; linear subframe timing for arbitrary jobs')
