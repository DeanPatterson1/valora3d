"""Render-only road weathering: the car was driven here through the rain.

A showroom-clean body on a soaked road is one of the strongest CG tells.
Tyres throw a grey-brown film onto the sills, the panels behind each arch and
the tail; wheels hold a little dust in their recesses. Everything here is a
world-position shader layer. No source mesh, UV or browser material is edited,
and both layers scale to zero through rain_look.LOOK.
"""
import bpy
from mathutils import Vector

MASK_GROUP = 'Rain — road spray film mask'
ENVELOPE = 'Spray envelope before streaks'
FILM_COLOR = (.058, .053, .046, 1)
DUST_COLOR = (.070, .058, .046, 1)


def _op(tree, operation, a, b=None, label=''):
    node = tree.nodes.new('ShaderNodeMath')
    node.operation = operation
    node.label = label
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            tree.links.new(value, node.inputs[index])
    return node.outputs[0]


def _smooth(tree, value, start, end, at_start, at_end, label=''):
    node = tree.nodes.new('ShaderNodeMapRange')
    node.interpolation_type = 'SMOOTHSTEP'
    node.label = label
    for name, number in [('From Min', start), ('From Max', end), ('To Min', at_start), ('To Max', at_end)]:
        node.inputs[name].default_value = number
    tree.links.new(value, node.inputs['Value'])
    return node.outputs[0]


def wheel_centres(meshes, scale):
    """Full tyres only, by the same size and roundness test as the sidewalls."""
    centres = []
    for obj in meshes:
        if not obj.name.lower().startswith(('tire-', 'tyre-')):
            continue
        corners = [Vector(p) for p in obj.bound_box]
        dims = sorted(max(p[i] for p in corners) - min(p[i] for p in corners) for i in range(3))
        if dims[1] < .25 * scale or dims[1] / dims[2] < .9:
            continue
        centres.append(obj.matrix_world @ (sum(corners, Vector()) / 8))
    return centres


def film_mask(wheels, low, high, scale, strength):
    """Where spray lands on a car whose nose points along -Y.

    Sills everywhere, a taller plume trailing each wheel, and the tail, which
    sits in the wake and collects the most. Streaks run along the car.
    """
    tree = bpy.data.node_groups.new(MASK_GROUP, 'ShaderNodeTree')
    tree.interface.new_socket(name='Film', in_out='OUTPUT', socket_type='NodeSocketFloat')
    geometry = tree.nodes.new('ShaderNodeNewGeometry')
    xyz = tree.nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(geometry.outputs['Position'], xyz.inputs[0])
    x, y, z = xyz.outputs
    height = _op(tree, 'MULTIPLY', _op(tree, 'SUBTRACT', z, low.z), 1 / scale, 'Metres above the road')
    sill = _op(tree, 'MULTIPLY', _smooth(tree, height, .06, .58, 1, 0, 'Sill film'), .8)
    plume_height = _smooth(tree, height, .20, .95, 1, 0, 'Plume height behind a wheel')
    plume = None
    for wheel in wheels:
        along = _op(tree, 'MULTIPLY', _op(tree, 'SUBTRACT', y, wheel.y + .62 * scale), 1 / (.60 * scale))
        across = _op(tree, 'MULTIPLY', _op(tree, 'SUBTRACT', x, wheel.x), 1 / (.30 * scale))
        distance = _op(tree, 'ADD', _op(tree, 'MULTIPLY', along, along), _op(tree, 'MULTIPLY', across, across))
        lobe = _op(tree, 'EXPONENT', _op(tree, 'MULTIPLY', distance, -1), label='Spray trailing one wheel')
        plume = lobe if plume is None else _op(tree, 'MAXIMUM', plume, lobe)
    tail = _op(tree, 'MULTIPLY', _smooth(tree, y, high.y - .50 * scale, high.y - .05 * scale, 0, .75, 'Tail sits in the wake'),
               _smooth(tree, height, .15, .90, 1, 0))
    film = _op(tree, 'MAXIMUM', sill, tail)
    if plume is not None:
        film = _op(tree, 'MAXIMUM', film, _op(tree, 'MULTIPLY', plume, plume_height))
    # Named so check_road_weathering.py can evaluate where spray lands
    # without the streak and speckle textures.
    film.node.name = ENVELOPE
    stretch = tree.nodes.new('ShaderNodeVectorMath')
    stretch.operation = 'MULTIPLY'
    stretch.inputs[1].default_value = (3.2 / scale, 1.0 / scale, 3.2 / scale)
    tree.links.new(geometry.outputs['Position'], stretch.inputs[0])
    streaks = tree.nodes.new('ShaderNodeTexNoise')
    streaks.label = 'Lengthwise spray streaks'
    streaks.inputs['Scale'].default_value = 1.6
    streaks.inputs['Detail'].default_value = 4
    streaks.inputs['Roughness'].default_value = .6
    tree.links.new(stretch.outputs[0], streaks.inputs['Vector'])
    breakup = _smooth(tree, streaks.outputs['Fac'], .34, .68, .25, 1)
    speckle = tree.nodes.new('ShaderNodeTexNoise')
    speckle.label = 'Dried droplet speckle'
    speckle.inputs['Scale'].default_value = 60 / scale
    speckle.inputs['Detail'].default_value = 1
    tree.links.new(geometry.outputs['Position'], speckle.inputs['Vector'])
    film = _op(tree, 'MULTIPLY', film, breakup)
    film = _op(tree, 'MULTIPLY', film, _smooth(tree, speckle.outputs['Fac'], .40, .66, .65, 1))
    result = tree.nodes.new('ShaderNodeMath')
    result.operation = 'MULTIPLY'
    result.use_clamp = True
    result.inputs[1].default_value = strength
    tree.links.new(film, result.inputs[0])
    output = tree.nodes.new('NodeGroupOutput')
    tree.links.new(result.outputs[0], output.inputs['Film'])
    return tree


def _toward_color(material, socket, color, factor, label):
    tree = material.node_tree
    mix = tree.nodes.new('ShaderNodeMixRGB')
    mix.name = mix.label = label
    if socket.is_linked:
        tree.links.new(socket.links[0].from_socket, mix.inputs[1])
    else:
        mix.inputs[1].default_value = socket.default_value
    mix.inputs[2].default_value = color
    tree.links.new(factor, mix.inputs[0])
    tree.links.new(mix.outputs[0], socket)


def _toward_value(material, socket, target, factor, label):
    """factor 0 keeps the authored value or map; factor 1 reaches target."""
    tree = material.node_tree
    blend = tree.nodes.new('ShaderNodeMapRange')
    blend.name = blend.label = label
    if socket.is_linked:
        tree.links.new(socket.links[0].from_socket, blend.inputs['To Min'])
    else:
        blend.inputs['To Min'].default_value = socket.default_value
    blend.inputs['To Max'].default_value = target
    tree.links.new(factor, blend.inputs['Value'])
    tree.links.new(blend.outputs[0], socket)


def _exterior_film_target(material):
    name = material.name.lower()
    if 'interior' in name:
        return False
    if name.startswith(('mv-unified-paint', 'mv-carbon-weave')):
        return True
    return material.get('mv_rain_look') in ('satin-trim', 'semi-gloss-trim')


def road_film(meshes, low, high, scale, strength):
    if strength <= 0:
        return []
    materials = {m for obj in meshes for m in obj.data.materials
                 if m and m.use_nodes and not m.get('mv_road_film') and _exterior_film_target(m)}
    if not materials:
        return []
    mask = film_mask(wheel_centres(meshes, scale), low, high, scale, strength)
    report = []
    for material in sorted(materials, key=lambda m: m.name):
        shader = next((n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if shader is None:
            continue
        group = material.node_tree.nodes.new('ShaderNodeGroup')
        group.node_tree = mask
        group.name = group.label = MASK_GROUP
        film = group.outputs['Film']
        tint = _op(material.node_tree, 'MULTIPLY', film, .6, 'Film covers, never replaces, the pigment')
        _toward_color(material, shader.inputs['Base Color'], FILM_COLOR, tint, 'Rain — road film pigment')
        _toward_value(material, shader.inputs['Roughness'], .62, film, 'Rain — road film base roughness')
        coat = shader.inputs['Coat Weight']
        if coat.is_linked or coat.default_value > .01:
            _toward_value(material, shader.inputs['Coat Roughness'], .32, film, 'Rain — road film dulls the lacquer')
        material['mv_road_film'] = True
        report.append(material.name)
    return report


def brake_dust(meshes, scale, strength):
    """A thin warm-grey film that gathers in the barrel and the spoke roots."""
    if strength <= 0:
        return []
    report = []
    materials = {m for obj in meshes if obj.name.lower().startswith('wheel-') for m in obj.data.materials
                 if m and m.use_nodes and m.name.lower().split('.')[0] == 'rims' and not m.get('mv_brake_dust')}
    for material in sorted(materials, key=lambda m: m.name):
        tree = material.node_tree
        # An authored wheel map carries its own wear.
        if any(n.type == 'TEX_IMAGE' for n in tree.nodes):
            continue
        shader = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if shader is None:
            continue
        geometry = tree.nodes.new('ShaderNodeNewGeometry')
        cloud = tree.nodes.new('ShaderNodeTexNoise')
        cloud.label = 'Uneven dust settling'
        cloud.inputs['Scale'].default_value = 28 / scale
        cloud.inputs['Detail'].default_value = 3
        tree.links.new(geometry.outputs['Position'], cloud.inputs['Vector'])
        settle = _smooth(tree, cloud.outputs['Fac'], .35, .72, .15, 1)
        occlusion = tree.nodes.new('ShaderNodeAmbientOcclusion')
        occlusion.label = 'Recesses hold dust'
        occlusion.samples = 8
        occlusion.inputs['Distance'].default_value = .05 * scale
        cavity = _smooth(tree, occlusion.outputs['AO'], .35, .95, 1, .30)
        dust = _op(tree, 'MULTIPLY', _op(tree, 'MULTIPLY', settle, cavity), strength, 'Rain — brake dust amount')
        dust.node.use_clamp = True
        _toward_color(material, shader.inputs['Base Color'], DUST_COLOR, dust, 'Rain — brake dust pigment')
        _toward_value(material, shader.inputs['Roughness'], .72, dust, 'Rain — brake dust roughness')
        _toward_value(material, shader.inputs['Metallic'], .15, dust, 'Rain — dust is dielectric over the metal')
        material['mv_brake_dust'] = True
        report.append(material.name)
    return report


def apply(meshes, low, high, scale, look):
    return {'roadFilm': road_film(meshes, low, high, scale, look['road_film']),
            'brakeDust': brake_dust(meshes, scale, look['brake_dust'])}
