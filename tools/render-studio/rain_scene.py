"""Deterministic wet park courtyard: real HDR illumination and modeled context."""
import math
import os
from pathlib import Path
import random

import bpy
from mathutils import Vector
import scene_plants

ASSETS = Path(os.environ.get('RENDER_STUDIO_ASSETS') or Path(__file__).resolve().parent / 'assets')
HDRI_FILES = ('cloudy_vondelpark_hdri_8k.hdr', 'cloudy_vondelpark_hdri_4k.hdr')


def hdri_path():
    """Sharpest pinned HDRI available. At 78 mm a 4k panorama is magnified
    about 6.6x in the backplate and smears every paint reflection; 8k halves
    that. The 4k file stays a valid fallback for an older asset checkout."""
    for name in HDRI_FILES:
        if (ASSETS / name).is_file():
            return ASSETS / name
    raise RuntimeError('Rain scene assets missing. Run tools/render-studio/prepare_assets.py once.')


def simple_material(name, color, roughness=0.5, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return mat


def textured_stone():
    mat = simple_material('Courtyard — rain-darkened concrete', (0.12, 0.135, 0.13), 0.48)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 65
    noise.inputs['Detail'].default_value = 3
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Distance'].default_value = 0.008
    bump.inputs['Strength'].default_value = 0.3
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    shader.inputs['Coat Weight'].default_value = 0.22
    shader.inputs['Coat Roughness'].default_value = 0.18
    return mat


def box(name, position, size, mat, bevel=0.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new('Soft manufactured edges', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 2
        obj.modifiers.new('Weighted face normals', 'WEIGHTED_NORMAL')
    return obj


# Water stands wherever this level is above the summed surface height.
# The three height terms average about 0.73 with a deviation near 0.13, so
# 0.69 floods roughly a third of the court.
PUDDLE_LEVEL = 0.69


def wet_asphalt(scale):
    """Rained-on asphalt: a water film everywhere, standing water where low.

    Height is metre-scale depressions + half-metre patches + the scanned
    aggregate relief. Thresholding that sum, rather than one smooth noise,
    puts stones through the shoreline: pools get ragged banks and satellite
    wet spots instead of a single soft-edged blob. The road is never dry in
    this scene, so the film keeps a broken sky reflection outside the pools.
    """
    from wet_detail import puddle_normal

    mat = simple_material('Courtyard — asphalt aggregate and shallow puddles', (0.025, 0.028, 0.03))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    geometry = nodes.new('ShaderNodeNewGeometry')
    mapping = nodes.new('ShaderNodeVectorMath')
    mapping.operation = 'SCALE'
    mapping.inputs[3].default_value = 1 / (3 * scale)  # scanned patch = 3 m
    links.new(geometry.outputs['Position'], mapping.inputs[0])
    textures = {}
    for key, file in (('Diffuse', 'asphalt_02_Diffuse_2k.jpg'), ('nor_gl', 'asphalt_02_nor_gl_2k.jpg'),
                      ('Rough', 'asphalt_02_Rough_2k.jpg'), ('Displacement', 'asphalt_02_Displacement_2k.exr')):
        if not (ASSETS / file).is_file():
            if key == 'Displacement':
                continue  # Older asset checkout: shorelines fall back to the noise terms.
            raise RuntimeError('Rain scene assets missing. Run tools/render-studio/prepare_assets.py once.')
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str(ASSETS / file), check_existing=True)
        if key != 'Diffuse':
            tex.image.colorspace_settings.name = 'Non-Color'
        tex.extension = 'REPEAT'
        links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
        textures[key] = tex

    def math(operation, a, b=None, name=''):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        if name:
            node.name = node.label = name
        for index, value in enumerate((a, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                node.inputs[index].default_value = value
            else:
                links.new(value, node.inputs[index])
        return node.outputs[0]

    def smoothstep(value, low, high, name):
        node = nodes.new('ShaderNodeMapRange')
        node.name = node.label = name
        node.interpolation_type = 'SMOOTHSTEP'
        node.inputs['From Min'].default_value = low
        node.inputs['From Max'].default_value = high
        links.new(value, node.inputs['Value'])
        return node.outputs[0]

    def mix_value(factor, a, b, name):
        node = nodes.new('ShaderNodeMapRange')
        node.name = node.label = name
        node.inputs['To Min'].default_value = a
        node.inputs['To Max'].default_value = b
        links.new(factor, node.inputs['Value'])
        return node.outputs[0]

    macro = nodes.new('ShaderNodeTexNoise')
    macro.name = 'Broad shallow depressions'
    macro.inputs['Scale'].default_value = 0.21 / scale
    macro.inputs['Detail'].default_value = 1
    macro.inputs['Roughness'].default_value = 0.50
    links.new(geometry.outputs['Position'], macro.inputs['Vector'])
    patches = nodes.new('ShaderNodeTexNoise')
    patches.name = 'Half-metre surface undulation'
    patches.inputs['Scale'].default_value = 1.35 / scale
    patches.inputs['Detail'].default_value = 3
    patches.inputs['Roughness'].default_value = 0.55
    links.new(geometry.outputs['Position'], patches.inputs['Vector'])
    height = math('ADD', macro.outputs['Fac'], math('MULTIPLY', patches.outputs['Fac'], .35))
    if 'Displacement' in textures:
        height = math('ADD', height, math('MULTIPLY', textures['Displacement'].outputs['Color'], .10))
    else:
        height = math('ADD', height, .08)
    depth = math('SUBTRACT', PUDDLE_LEVEL, height, 'Standing water depth')
    # Parking bays sit in a worn dip: a shallow sheet of water under and around
    # the car, so the road mirrors the body and the dark underside reads as a
    # contact shadow. Depth 0 (the default) leaves the court as surveyed;
    # car_apron() places and fills it once the car's footprint is known.
    apron_depth = nodes.new('ShaderNodeValue')
    apron_depth.name = apron_depth.label = 'Car apron depth'
    apron_depth.outputs[0].default_value = 0
    apron_shape = nodes.new('ShaderNodeCombineXYZ')       # centre x, centre y, unused
    apron_shape.name = apron_shape.label = 'Car apron centre'
    apron_radii = nodes.new('ShaderNodeCombineXYZ')       # 1/radius x, 1/radius y
    apron_radii.name = apron_radii.label = 'Car apron inverse radii'
    apron_radii.inputs[0].default_value = apron_radii.inputs[1].default_value = 1
    offset = nodes.new('ShaderNodeVectorMath')
    offset.operation = 'SUBTRACT'
    links.new(geometry.outputs['Position'], offset.inputs[0])
    links.new(apron_shape.outputs[0], offset.inputs[1])
    scaled = nodes.new('ShaderNodeVectorMath')
    scaled.operation = 'MULTIPLY'
    links.new(offset.outputs[0], scaled.inputs[0])
    links.new(apron_radii.outputs[0], scaled.inputs[1])
    reach = nodes.new('ShaderNodeVectorMath')
    reach.operation = 'LENGTH'
    links.new(scaled.outputs[0], reach.inputs[0])
    # Full depth under the car, gone by the rim; the half-metre undulation breaks the outline.
    rim = math('ADD', reach.outputs['Value'], math('MULTIPLY', math('SUBTRACT', patches.outputs['Fac'], .5), .55))
    basin = math('SUBTRACT', 1, smoothstep(rim, .45, 1.0, 'Car apron falloff'))
    depth = math('ADD', depth, math('MULTIPLY', basin, apron_depth.outputs[0]), 'Standing water depth with apron')
    puddle_mask = smoothstep(depth, 0, .022, 'Soft puddle to damp asphalt transition')
    damp_mask = smoothstep(depth, -.075, .0, 'Saturated bank around each pool')
    deep_mask = smoothstep(depth, .02, .16, 'Pool depth darkening')

    # Wet stone is roughly half as reflective as dry; saturated banks and the
    # bed of a pool are darker again. Metre-scale variation hides the 3 m tile.
    tint = mix_value(damp_mask, .56, .40, 'Wet to saturated albedo')
    tint = math('MULTIPLY', tint, mix_value(deep_mask, 1, .62, 'Pool bed albedo'))
    tint = math('MULTIPLY', tint, mix_value(patches.outputs['Fac'], .82, 1.16, 'Patchy wear albedo'))
    darken = nodes.new('ShaderNodeMix')
    darken.data_type = 'RGBA'
    darken.blend_type = 'MULTIPLY'
    darken.name = darken.label = 'Rain-darkened aggregate'
    darken.inputs[0].default_value = 1
    links.new(textures['Diffuse'].outputs['Color'], darken.inputs[6])
    grey = nodes.new('ShaderNodeCombineColor')
    for channel, cast in zip(('Red', 'Green', 'Blue'), (.96, 1.0, 1.05)):
        links.new(math('MULTIPLY', tint, cast), grey.inputs[channel])
    links.new(grey.outputs[0], darken.inputs[7])
    links.new(darken.outputs[2], shader.inputs['Base Color'])

    # Base = wet stone. Coat = the water itself: a thin broken film outside
    # the pools, optically flat inside them.
    stone_rough = mix_value(textures['Rough'].outputs['Color'], .34, .62, 'Wet aggregate roughness')
    links.new(stone_rough, shader.inputs['Roughness'])
    shader.inputs['Specular IOR Level'].default_value = .35
    film = mix_value(damp_mask, .62, .88, 'Water film coverage')
    coat_weight = math('MAXIMUM', film, puddle_mask, 'Film to standing water')
    links.new(coat_weight, shader.inputs['Coat Weight'])
    film_rough = mix_value(textures['Rough'].outputs['Color'], .07, .20, 'Water film roughness')
    film_rough = math('MULTIPLY', film_rough, mix_value(damp_mask, 1, .55, 'Saturated film is smoother'))
    coat_rough = math('MULTIPLY', film_rough, math('SUBTRACT', 1, puddle_mask), 'Standing water is optically smooth')
    coat_rough = math('ADD', coat_rough, .004)
    links.new(coat_rough, shader.inputs['Coat Roughness'])
    shader.inputs['Coat IOR'].default_value = 1.333

    stone_normal = nodes.new('ShaderNodeNormalMap')
    stone_normal.name = stone_normal.label = 'Aggregate relief'
    stone_normal.inputs['Strength'].default_value = 1.0
    links.new(textures['nor_gl'].outputs['Color'], stone_normal.inputs['Color'])
    links.new(stone_normal.outputs['Normal'], shader.inputs['Normal'])
    film_normal = nodes.new('ShaderNodeNormalMap')
    film_normal.name = film_normal.label = 'Water film follows softened relief'
    links.new(textures['nor_gl'].outputs['Color'], film_normal.inputs['Color'])
    film_strength = math('MULTIPLY', mix_value(damp_mask, .46, .24, 'Film relief'),
                         math('SUBTRACT', 1, puddle_mask))
    links.new(math('ADD', film_strength, .004), film_normal.inputs['Strength'])
    ripples = puddle_normal(mat, geometry.outputs['Position'], puddle_mask,
                            film_normal.outputs['Normal'], scale)
    links.new(ripples, shader.inputs['Coat Normal'])
    return mat


def car_apron(center, extent, scale, depth):
    """Fill the dip the car is parked in. depth is in height-field units (0 to about .2)."""
    for mat in bpy.data.materials:
        if not mat.use_nodes or 'Car apron depth' not in mat.node_tree.nodes:
            continue
        nodes = mat.node_tree.nodes
        nodes['Car apron depth'].outputs[0].default_value = depth
        nodes['Car apron centre'].inputs[0].default_value = center.x
        nodes['Car apron centre'].inputs[1].default_value = center.y
        nodes['Car apron inverse radii'].inputs[0].default_value = 1 / (extent.x / 2 + 2.6 * scale)
        nodes['Car apron inverse radii'].inputs[1].default_value = 1 / (extent.y / 2 + 2.2 * scale)
        nodes['Car apron inverse radii'].inputs[2].default_value = 0


def environment(scene, center, scale):
    path = hdri_path()
    world = bpy.data.worlds.new('Rain — overcast park HDRI')
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    tex = nodes.new('ShaderNodeTexEnvironment')
    tex.image = bpy.data.images.load(str(path), check_existing=True)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Rotation'].default_value[2] = math.radians(110)
    coordinates = nodes.new('ShaderNodeTexCoord')
    links.new(coordinates.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], tex.inputs['Vector'])
    links.new(tex.outputs['Color'], nodes.get('Background').inputs['Color'])
    nodes.get('Background').inputs['Strength'].default_value = 1.0
    scene.world = world
    # A camera-only environment sphere gives distant foliage a physical depth
    # for DOF. Other rays still see the unclipped HDR environment.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=90 * scale, location=center)
    dome = bpy.context.object
    dome.name = 'Rain — distant park background'
    dome.visible_shadow = dome.visible_diffuse = dome.visible_glossy = dome.visible_transmission = False
    mat = bpy.data.materials.new('Rain — background photograph')
    mat.use_nodes = True
    ns, ls = mat.node_tree.nodes, mat.node_tree.links
    ns.clear()
    out, emission = ns.new('ShaderNodeOutputMaterial'), ns.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = 1.0
    image = ns.new('ShaderNodeTexEnvironment')
    image.image = tex.image
    geo = ns.new('ShaderNodeNewGeometry')
    subtract = ns.new('ShaderNodeVectorMath')
    subtract.operation = 'SUBTRACT'
    subtract.inputs[1].default_value = center
    rotate = ns.new('ShaderNodeMapping')
    rotate.inputs['Rotation'].default_value[2] = math.radians(110)
    ls.new(geo.outputs['Position'], subtract.inputs[0])
    ls.new(subtract.outputs[0], rotate.inputs['Vector'])
    ls.new(rotate.outputs['Vector'], image.inputs['Vector'])
    ls.new(image.outputs[0], emission.inputs['Color'])
    ls.new(emission.outputs[0], out.inputs['Surface'])
    dome.data.materials.append(mat)


def park_ground(center, scale):
    """Project the photographed distant ground onto a plane, continuous with
    the HDR backdrop. Near asphalt, curbs, planting beds and grass remain 3D.
    This avoids an untextured artificial horizon at the end of the court.
    """
    mat = bpy.data.materials.new('Rain — projected distant park ground')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    geometry = nodes.new('ShaderNodeNewGeometry')
    subtract = nodes.new('ShaderNodeVectorMath')
    subtract.operation = 'SUBTRACT'
    subtract.inputs[1].default_value = center + Vector((0, 0, 1.6 * scale))
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Rotation'].default_value[2] = math.radians(110)
    texture = nodes.new('ShaderNodeTexEnvironment')
    texture.image = bpy.data.images.load(str(hdri_path()), check_existing=True)
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = 1.0
    output = nodes.new('ShaderNodeOutputMaterial')
    links.new(geometry.outputs['Position'], subtract.inputs[0])
    links.new(subtract.outputs[0], mapping.inputs['Vector'])
    links.new(mapping.outputs[0], texture.inputs['Vector'])
    links.new(texture.outputs[0], emission.inputs['Color'])
    links.new(emission.outputs[0], output.inputs['Surface'])
    return mat


def foliage_materials():
    """Wet autumn litter from the same park: yellow through rust to brown."""
    palette = [(0.42, 0.27, 0.030), (0.34, 0.16, 0.022), (0.20, 0.085, 0.018),
               (0.30, 0.24, 0.045), (0.105, 0.070, 0.022)]
    mats = []
    for i, color in enumerate(palette):
        mat = simple_material(f'Rain — autumn leaf {i}', color, 0.46)
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Subsurface Weight'].default_value = 0.10
        shader.inputs['Coat Weight'].default_value = 0.65
        shader.inputs['Coat Roughness'].default_value = 0.12
        shader.inputs['Coat IOR'].default_value = 1.333
        mats.append(mat)
    return mats


# Half outline of a pointed ovate leaf: (position along the midrib, half width).
LEAF_PROFILE = ((0.0, 0.0), (.12, .55), (.32, .92), (.55, 1.0), (.76, .72), (.92, .34), (1.0, 0.0))


def leaf_mesh(name, leaves, mats, rng=None):
    """Folded, curled ovate leaves lying on the road, one mesh for all."""
    rng = rng or random.Random(20260917)
    vertices, faces, indices = [], [], []
    for position, direction, width, length, index in leaves:
        direction = Vector(direction)
        direction.z = 0
        if direction.length < 0.01:
            direction = Vector((1, 0, 0))
        direction.normalize()
        up = Vector((0, 0, 1))
        side = direction.cross(up).normalized()
        fold = rng.uniform(.05, .32)      # V-fold along the midrib
        curl = rng.uniform(-.10, .28)     # tips lift off the road
        twist = rng.uniform(-.10, .10)
        start = len(vertices)
        p = Vector(position)
        rows = []
        for along, half in LEAF_PROFILE:
            spine = p + direction * (along - .5) * length
            lift = curl * length * (2 * along - 1) ** 2
            row = []
            for sign in (-1, 0, 1):
                offset = side * (sign * half * width)
                rise = abs(sign) * half * width * (fold + twist * sign) + lift
                row.append(len(vertices))
                vertices.append(spine + offset + up * (rise + .0015))
            rows.append(row)
        for a, b in zip(rows, rows[1:]):
            for k in (0, 1):
                faces.append((a[k], a[k + 1], b[k + 1], b[k]))
                indices.append(index)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for mat in mats:
        mesh.materials.append(mat)
    mesh.polygons.foreach_set('material_index', indices)
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build(scene, center, low, scale, plant_seed=20260919):
    rng = random.Random(20260915)
    # Let the asphalt meet the tire contact surface; a visible air gap makes
    # the car look weightless even when it is only a few millimetres high.
    origin = Vector((center.x, center.y, low.z + 0.002 * scale))
    environment(scene, origin, scale)
    bpy.ops.mesh.primitive_plane_add(size=1, location=origin)
    ground = bpy.context.object
    ground.name = 'Rain — wet asphalt court'
    ground.scale = (14 * scale, 32 * scale, 1)
    ground.data.materials.append(wet_asphalt(scale))
    soil = simple_material('Rain — dark earth', (0.018, 0.023, 0.011), 0.94)
    # At grazing angles a flat dielectric becomes a gray mirror. Soil needs
    # broken microgeometry and low specularity; it is not another puddle.
    ns, ls = soil.node_tree.nodes, soil.node_tree.links
    earth_shader = ns.get('Principled BSDF')
    earth_shader.inputs['Specular IOR Level'].default_value = 0.07
    earth_noise = ns.new('ShaderNodeTexNoise')
    earth_noise.inputs['Scale'].default_value = 1.5 / scale
    earth_noise.inputs['Detail'].default_value = 4
    position = ns.new('ShaderNodeNewGeometry')
    ls.new(position.outputs['Position'], earth_noise.inputs['Vector'])
    earth_color = ns.new('ShaderNodeValToRGB')
    earth_color.color_ramp.elements[0].color = (0.008, 0.010, 0.004, 1)
    earth_color.color_ramp.elements[1].color = (0.045, 0.050, 0.013, 1)
    ls.new(earth_noise.outputs['Fac'], earth_color.inputs[0])
    ls.new(earth_color.outputs[0], earth_shader.inputs['Base Color'])
    bump = ns.new('ShaderNodeBump')
    bump.inputs['Distance'].default_value = 0.06 * scale
    bump.inputs['Strength'].default_value = 0.65
    ls.new(earth_noise.outputs['Fac'], bump.inputs['Height'])
    ls.new(bump.outputs['Normal'], earth_shader.inputs['Normal'])
    bpy.ops.mesh.primitive_plane_add(size=180 * scale, location=origin - Vector((0, 0, 0.025 * scale)))
    bpy.context.object.name = 'Rain — park ground'
    bpy.context.object.data.materials.append(park_ground(origin, scale))
    bpy.context.object.visible_diffuse = False
    stone = textured_stone()
    foliage = foliage_materials()
    tree_prototype = scene_plants.shape_variants(scene_plants.prototypes('tree_small_02')[0], seed=plant_seed)
    grass_prototypes = scene_plants.prototypes('grass_medium_01')
    metal = simple_material('Rain — graphite furniture', (0.025, 0.033, 0.029), 0.30, 0.75)
    wood = simple_material('Rain — dark bench slats', (0.060, 0.039, 0.018), 0.42)
    def pos(x, y, z=0):
        return origin + Vector((x, y, z)) * scale
    # Continuous curbs bound the court, with joints visible in near views.
    for x in (-4.8, 4.8):
        for j in range(-14, 15):
            box('Rain — curb stone', pos(x, j, 0.065), (0.28*scale, 0.982*scale, 0.13*scale), stone, 0.012*scale)
        for y in (-7, -1, 6, 12):
            # Near trees supply real, parallax-correct canopy reflections on
            # the hood/glass. Keep trunks in planting beds outside the curb.
            near = y < 0
            p = pos(x + math.copysign(0.9 if near else 2.7, x), y, 0.06)
            box('Rain — tree bed edging', p, (1.8*scale, 2.5*scale, 0.14*scale), stone, 0.025*scale)
            box('Rain — tree bed soil', p + Vector((0, 0, 0.08*scale)), (1.62*scale, 2.32*scale, 0.06*scale), soil, 0)
            height = rng.uniform(4.4, 5.7) * (1.6 if near else 1) * scale
            scene_plants.plant_tree(tree_prototype, p, height, rng)
    scene_plants.plant_grass(grass_prototypes, origin, scale, rng)
    depth_rng = random.Random(20260917)
    scene_plants.plant_depth_layers(tree_prototype, origin, scale, depth_rng)
    scene_plants.plant_foreground_grass(grass_prototypes, origin, scale, depth_rng)
    # No punctual rig here. The overcast sky is the softbox: every added
    # rectangle shows up as a studio reflection in wet paint and standing
    # water, which is what made earlier passes read as a showroom in a park.
    for x, y in [(-5.8, 2.3), (5.8, -4)]:
        for support in (-0.65, 0.65):
            box('Rain — bench leg', pos(x, y+support, 0.23), (0.5*scale, 0.05*scale, 0.46*scale), metal)
        for i in range(5):
            box('Rain — bench seat', pos(x-0.24+i*0.12, y, 0.48), (0.10*scale, 1.8*scale, 0.035*scale), wood)
        for i in range(3):
            box('Rain — bench back', pos(x+0.24, y, 0.7+i*0.12), (0.05*scale, 1.8*scale, 0.09*scale), wood)
    # Small grate provides a tangible scale cue and something for puddles to meet.
    for y in (-5, 5):
        for i in range(30):
            box('Rain — drainage grate', pos(4.1, y+i*0.028, 0.003), (0.26*scale, 0.014*scale, 0.009*scale), metal, 0)
    # Litter gathers along the curbs and thins toward the open court; a few
    # leaves still reach the middle. None sit under the parked car.
    litter = []
    for _ in range(620):
        if rng.random() < .62:
            x = math.copysign(4.55 - abs(rng.gauss(0, .55)), rng.uniform(-1, 1))
        else:
            x = rng.uniform(-4.5, 4.5)
        y = rng.uniform(-13, 13)
        if abs(x) < 1.25 and abs(y) < 2.8:
            continue
        p = pos(x, y, 0.0)
        litter.append((p, (rng.uniform(-1, 1), rng.uniform(-1, 1), 0),
                       rng.uniform(0.016, 0.034)*scale, rng.uniform(0.055, 0.105)*scale, rng.randrange(5)))
    leaf_mesh('Rain — fallen leaves', litter, foliage, rng)
    # A few leaves are not stuck down yet: separate objects, so the wind can
    # lift and push them (wind.py). Own generator; the litter above is unchanged.
    loose_rng = random.Random(20260918)
    for number in range(90):
        x = math.copysign(4.5 - abs(loose_rng.gauss(0, .9)), loose_rng.uniform(-1, 1)) if loose_rng.random() < .5 else loose_rng.uniform(-4.4, 4.4)
        y = loose_rng.uniform(-12, 10)
        if abs(x) < 1.4 and abs(y) < 3.4:
            continue
        width = loose_rng.uniform(0.018, 0.034) * scale
        leaf = leaf_mesh('Rain — loose leaf %03d' % number, [((0, 0, 0), (1, 0, 0), width, loose_rng.uniform(0.055, 0.10) * scale,
                                                              loose_rng.randrange(5))], foliage, loose_rng)
        leaf.location = pos(x, y, 0.0)
        leaf.rotation_euler[2] = loose_rng.uniform(0, math.tau)
        leaf['mv_half_width'] = width / 2
    return {'environment': 'cloudy_vondelpark', 'ground': 'asphalt_02',
            'foliage': ['tree_small_02', 'grass_medium_01'], 'seed': 20260915}
