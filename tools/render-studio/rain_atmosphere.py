"""Sparse falling water with continuous subframe motion and car interception."""
import math
import random

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def build(scene, meshes, center, low, scale, first, total, seed=20260916, size=1.0, reach=1.0, backlight=1.0, glow=0.0):
    """size scales drop radius, reach the rained-on area (columns scale with it), backlight the rain-only lamp."""
    rng = random.Random(seed)
    vertices, faces = [], []
    for obj in meshes:
        start = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        faces.extend(tuple(start+i for i in p.vertices) for p in obj.data.polygons)
    collider = BVHTree.FromPolygons(vertices, faces)
    velocity = 6.5 * scale
    height = (8 + total / scene.render.fps * 6.5) * scale
    points, radii, stops = [], [], []
    intercepted = 0
    for _ in range(round(850 * reach * reach)):
        x, y = center.x + rng.uniform(-7, 7)*reach*scale, center.y + rng.uniform(-8, 8)*reach*scale
        hit, _, _, _ = collider.ray_cast(Vector((x, y, low.z + 10*scale)), Vector((0, 0, -1)), 12*scale)
        stop = hit.z + .004*scale if hit is not None else low.z + .005*scale
        intercepted += hit is not None
        # Enough height for the whole clip: there is no modulo/wrap jump
        # for Cycles to interpret as an enormous motion vector.
        for _ in range(math.ceil(height / (1.7*scale))):
            points.append((x, y, low.z + rng.uniform(0, height)))
            radii.append(rng.uniform(.00065, .00125)*size*scale)
            stops.append(stop)
    cloud = bpy.data.meshes.new('Rainfall initial positions')
    cloud.from_pydata(points, [], [])
    for name, values in [('rain_radius', radii), ('rain_stop_height', stops)]:
        attribute = cloud.attributes.new(name, 'FLOAT', 'POINT')
        attribute.data.foreach_set('value', values)
    obj = bpy.data.objects.new('Rain — falling droplets', cloud)
    scene.collection.objects.link(obj)
    obj['drop_count'] = len(points)
    obj['intercepted_columns'] = intercepted
    obj['speed_m_per_s'] = 6.5
    obj['has_temporal_wrap'] = False
    water = bpy.data.materials.new('Rain — airborne water')
    water.use_nodes = True
    shader = water.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.94, .98, 1, 1)
    shader.inputs['Roughness'].default_value = .02
    shader.inputs['Transmission Weight'].default_value = 1
    shader.inputs['IOR'].default_value = 1.333
    # The film clamps indirect light, and a lamp seen through a drop is indirect:
    # no backlight strength can lift a streak past that clamp. A streak covers a
    # few percent of its pixels, so a small emission stands in for the sky light
    # the drop scatters toward the lens. Camera rays see it unclamped.
    shader.inputs['Emission Color'].default_value = (.85, .92, 1, 1)
    shader.inputs['Emission Strength'].default_value = glow
    tree = bpy.data.node_groups.new('Continuous rain trajectory', 'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    ns, ls = tree.nodes, tree.links
    source, output = ns.new('NodeGroupInput'), ns.new('NodeGroupOutput')
    time = ns.new('GeometryNodeInputSceneTime')
    elapsed = ns.new('ShaderNodeMath'); elapsed.operation = 'SUBTRACT'
    elapsed.inputs[1].default_value = first / scene.render.fps
    ls.new(time.outputs['Seconds'], elapsed.inputs[0])
    travel = ns.new('ShaderNodeMath'); travel.operation = 'MULTIPLY'
    travel.inputs[1].default_value = -velocity
    ls.new(elapsed.outputs[0], travel.inputs[0])
    delta = ns.new('ShaderNodeCombineXYZ')
    ls.new(travel.outputs[0], delta.inputs['Z'])
    move = ns.new('GeometryNodeSetPosition')
    ls.new(source.outputs['Geometry'], move.inputs['Geometry'])
    ls.new(delta.outputs[0], move.inputs['Offset'])
    position = ns.new('GeometryNodeInputPosition')
    split = ns.new('ShaderNodeSeparateXYZ')
    ls.new(position.outputs[0], split.inputs[0])
    stop = ns.new('GeometryNodeInputNamedAttribute'); stop.data_type = 'FLOAT'
    stop.inputs['Name'].default_value = 'rain_stop_height'
    above = ns.new('ShaderNodeMath'); above.operation = 'SUBTRACT'
    ls.new(split.outputs['Z'], above.inputs[0]); ls.new(stop.outputs['Attribute'], above.inputs[1])
    fade = ns.new('ShaderNodeMapRange')
    fade.clamp = True
    fade.inputs['From Min'].default_value = 0
    fade.inputs['From Max'].default_value = .06*scale
    ls.new(above.outputs[0], fade.inputs['Value'])
    radius = ns.new('GeometryNodeInputNamedAttribute'); radius.data_type = 'FLOAT'
    radius.inputs['Name'].default_value = 'rain_radius'
    size = ns.new('ShaderNodeMath'); size.operation = 'MULTIPLY'
    ls.new(radius.outputs['Attribute'], size.inputs[0]); ls.new(fade.outputs[0], size.inputs[1])
    shape = ns.new('ShaderNodeCombineXYZ')
    ls.new(size.outputs[0], shape.inputs['X']); ls.new(size.outputs[0], shape.inputs['Y'])
    length = ns.new('ShaderNodeMath'); length.operation = 'MULTIPLY'; length.inputs[1].default_value = 1.8
    ls.new(size.outputs[0], length.inputs[0]); ls.new(length.outputs[0], shape.inputs['Z'])
    sphere = ns.new('GeometryNodeMeshIcoSphere'); sphere.inputs['Subdivisions'].default_value = 1
    assign = ns.new('GeometryNodeSetMaterial'); assign.inputs['Material'].default_value = water
    ls.new(sphere.outputs['Mesh'], assign.inputs['Geometry'])
    instance = ns.new('GeometryNodeInstanceOnPoints')
    ls.new(move.outputs['Geometry'], instance.inputs['Points'])
    ls.new(assign.outputs['Geometry'], instance.inputs['Instance'])
    ls.new(shape.outputs[0], instance.inputs['Scale'])
    ls.new(instance.outputs['Instances'], output.inputs['Geometry'])
    modifier = obj.modifiers.new('Subframe falling water', 'NODES'); modifier.node_group = tree
    # Backlight only the airborne drops. Lighting the whole road/car at this
    # energy washed the black paint out; receiver linking keeps that rig apart.
    receivers = bpy.data.collections.new('Rain — airborne light receivers')
    receivers.objects.link(obj)
    light_data = bpy.data.lights.new('Rain — falling-water backlight', 'AREA')
    light_data.energy = 3200 * backlight * scale * scale
    light_data.shape = 'RECTANGLE'
    light_data.size, light_data.size_y = 7*reach*scale, 3*reach*scale
    light_data.color = (.8, .9, 1)
    light_data.volume_factor = 0
    light = bpy.data.objects.new(light_data.name, light_data)
    scene.collection.objects.link(light)
    light.location = center + Vector((-2, 4, 4))*scale
    light.rotation_euler = (center + Vector((0, -2, .7))*scale-light.location).to_track_quat('-Z', 'Y').to_euler()
    light.light_linking.receiver_collection = receivers
    return {'drops': len(points), 'interceptedColumns': intercepted, 'speedMetresPerSecond': 6.5, 'temporalWrap': False}


def drips(scene, meshes, center, extent, low, scale, first, seed=20260920, count=70, size=1.0, glow=0.0):
    """Water gathering on the car's lower edges and falling off, drop by drop.

    Emitters are found, not authored: rays cast up from the road hit the
    underside, and a hit whose outward neighbour misses the car is an edge a
    drop can hang from (sills, bumper lips, splitter, mirrors, wing plates).
    Each emitter swells a drop for half its period, lets go, and the drop falls
    under gravity until the road. Periods and phases differ, so nothing pulses.
    The cycle wraps only while the drop has zero size: no streak on the wrap.
    """
    rng = random.Random(seed)
    bead = size
    vertices, faces = [], []
    for obj in meshes:
        start = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        faces.extend(tuple(start+i for i in p.vertices) for p in obj.data.polygons)
    collider = BVHTree.FromPolygons(vertices, faces)
    up = Vector((0, 0, 1))
    points, radii, periods, phases, hangs, grounds, falls = [], [], [], [], [], [], []
    tries = 0
    while len(points) < count and tries < 40000:
        tries += 1
        x = center.x + rng.uniform(-.56, .56) * extent.x
        y = center.y + rng.uniform(-.53, .53) * extent.y
        origin = Vector((x, y, low.z - .02 * scale))
        hit, _normal, _index, _distance = collider.ray_cast(origin, up, 1.4 * scale)
        if hit is None or hit.z - low.z < .07 * scale:
            continue
        outward = Vector((x - center.x, y - center.y, 0))
        if outward.length < 1e-6:
            continue
        outward.normalize()
        beside, _n, _i, _d = collider.ray_cast(origin + outward * (.035 * scale), up, (hit.z - low.z) + .05 * scale)
        if beside is not None:
            continue                                        # not an edge: water would run on, not fall
        fall = math.sqrt(2 * (hit.z - low.z) / (9.81 * scale))
        period = rng.uniform(fall / .45 + 1.0, fall / .45 + 2.4)     # always longer than hang + fall + landing ring
        points.append((hit.x, hit.y, hit.z - .002 * scale))
        radii.append(rng.uniform(.0017, .0026) * bead * scale)
        periods.append(period)
        phases.append(rng.random())
        hangs.append(period * .4)
        falls.append(fall)
        grounds.append(low.z + .004 * scale)
    cloud = bpy.data.meshes.new('Drip emitters')
    cloud.from_pydata(points, [], [])
    for name, values in (('drip_radius', radii), ('drip_period', periods), ('drip_phase', phases),
                         ('drip_hang', hangs), ('drip_ground', grounds), ('drip_fall', falls)):
        cloud.attributes.new(name, 'FLOAT', 'POINT').data.foreach_set('value', values)
    obj = bpy.data.objects.new('Rain — drips off the car', cloud)
    scene.collection.objects.link(obj)
    # Own material: a hanging bead must not glow, a falling streak may (see build).
    water = bpy.data.materials.new('Rain — drip water')
    water.use_nodes = True
    shader = water.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.94, .98, 1, 1)
    shader.inputs['Roughness'].default_value = .02
    shader.inputs['Transmission Weight'].default_value = 1
    shader.inputs['IOR'].default_value = 1.333
    shader.inputs['Emission Color'].default_value = (.85, .92, 1, 1)
    speed = water.node_tree.nodes.new('ShaderNodeAttribute')
    speed.attribute_type, speed.attribute_name = 'INSTANCER', 'drip_glow'
    lit = water.node_tree.nodes.new('ShaderNodeMath')
    lit.operation = 'MULTIPLY'
    lit.inputs[1].default_value = glow
    water.node_tree.links.new(speed.outputs['Fac'], lit.inputs[0])
    water.node_tree.links.new(lit.outputs[0], shader.inputs['Emission Strength'])
    tree = bpy.data.node_groups.new('Drips — swell, release, fall', 'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    ns, ls = tree.nodes, tree.links

    def op(operation, a, b=None, clamp=False):
        node = ns.new('ShaderNodeMath')
        node.operation = operation
        node.use_clamp = clamp
        for index, value in enumerate((a, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                node.inputs[index].default_value = value
            else:
                ls.new(value, node.inputs[index])
        return node.outputs[0]

    def attribute(name):
        node = ns.new('GeometryNodeInputNamedAttribute')
        node.data_type = 'FLOAT'
        node.inputs['Name'].default_value = name
        return node.outputs['Attribute']

    source, output = ns.new('NodeGroupInput'), ns.new('NodeGroupOutput')
    clock = ns.new('GeometryNodeInputSceneTime')
    elapsed = op('SUBTRACT', clock.outputs['Seconds'], first / scene.render.fps)
    period, hang = attribute('drip_period'), attribute('drip_hang')
    cycle = op('FRACT', op('ADD', op('DIVIDE', elapsed, period), attribute('drip_phase')))
    since = op('MULTIPLY', cycle, period)
    falling = op('MAXIMUM', op('SUBTRACT', since, hang), 0)
    drop = op('MULTIPLY', op('MULTIPLY', falling, falling), -.5 * 9.81 * scale)
    swell = op('DIVIDE', since, hang, clamp=True)
    swell = op('POWER', swell, .6)                              # fills fast, then hangs
    place = ns.new('GeometryNodeInputPosition')
    split = ns.new('ShaderNodeSeparateXYZ')
    ls.new(place.outputs[0], split.inputs[0])
    height = op('ADD', split.outputs['Z'], drop)
    airborne = op('GREATER_THAN', height, attribute('drip_ground'))
    size = op('MULTIPLY', op('MULTIPLY', attribute('drip_radius'), swell), airborne)
    # A hanging drop is a bead; once it lets go it stretches a little.
    stretch = op('ADD', 1.15, op('MULTIPLY', op('MINIMUM', op('MULTIPLY', falling, 6), 1), .7))
    offset = ns.new('ShaderNodeCombineXYZ')
    ls.new(drop, offset.inputs['Z'])
    move = ns.new('GeometryNodeSetPosition')
    ls.new(source.outputs['Geometry'], move.inputs['Geometry'])
    ls.new(offset.outputs[0], move.inputs['Offset'])
    shape = ns.new('ShaderNodeCombineXYZ')
    ls.new(size, shape.inputs['X']); ls.new(size, shape.inputs['Y'])
    ls.new(op('MULTIPLY', size, stretch), shape.inputs['Z'])
    sphere = ns.new('GeometryNodeMeshIcoSphere')
    sphere.inputs['Subdivisions'].default_value = 2
    assign = ns.new('GeometryNodeSetMaterial')
    assign.inputs['Material'].default_value = water
    ls.new(sphere.outputs['Mesh'], assign.inputs['Geometry'])
    instance = ns.new('GeometryNodeInstanceOnPoints')
    ls.new(move.outputs['Geometry'], instance.inputs['Points'])
    ls.new(assign.outputs['Geometry'], instance.inputs['Instance'])
    ls.new(shape.outputs[0], instance.inputs['Scale'])
    moving = ns.new('GeometryNodeStoreNamedAttribute')
    moving.data_type, moving.domain = 'FLOAT', 'INSTANCE'
    moving.inputs['Name'].default_value = 'drip_glow'
    ls.new(instance.outputs['Instances'], moving.inputs['Geometry'])
    ls.new(op('MINIMUM', op('MULTIPLY', falling, 8), 1), moving.inputs['Value'])
    instance = moving
    # Where a drop lands in the standing water it throws two low rings that
    # spread and flatten within about half a second. Raised water, not a shader
    # trick, so they refract and mirror like the puddle around them.
    landed = op('SUBTRACT', op('SUBTRACT', since, hang), attribute('drip_fall'))
    ground = ns.new('ShaderNodeCombineXYZ')
    ls.new(split.outputs['X'], ground.inputs['X']); ls.new(split.outputs['Y'], ground.inputs['Y'])
    ls.new(attribute('drip_ground'), ground.inputs['Z'])
    floor = ns.new('GeometryNodeSetPosition')
    ls.new(source.outputs['Geometry'], floor.inputs['Geometry'])
    ls.new(ground.outputs[0], floor.inputs['Position'])
    path, profile = ns.new('GeometryNodeCurvePrimitiveCircle'), ns.new('GeometryNodeCurvePrimitiveCircle')
    path.inputs['Resolution'].default_value, path.inputs['Radius'].default_value = 64, 1
    profile.inputs['Resolution'].default_value, profile.inputs['Radius'].default_value = 8, .1
    torus = ns.new('GeometryNodeCurveToMesh')
    ls.new(path.outputs['Curve'], torus.inputs['Curve']); ls.new(profile.outputs['Curve'], torus.inputs['Profile Curve'])
    wet = ns.new('GeometryNodeSetMaterial')
    wet.inputs['Material'].default_value = water
    ls.new(torus.outputs['Mesh'], wet.inputs['Geometry'])
    join = ns.new('GeometryNodeJoinGeometry')
    ls.new(instance.outputs[0], join.inputs['Geometry'])
    for delay, reach, crest in ((0, .15, .0016), (.09, .10, .0011)):
        age = op('DIVIDE', op('SUBTRACT', landed, delay), .55)
        alive = op('MULTIPLY', op('GREATER_THAN', age, 0), op('LESS_THAN', age, 1))
        age = op('MINIMUM', op('MAXIMUM', age, 0), 1)
        # A bigger drop throws a wider ring: reach scales with the bead radius.
        heft = op('DIVIDE', attribute('drip_radius'), .00215 * bead * scale)
        spread = op('MULTIPLY', op('ADD', .012, op('MULTIPLY', op('POWER', age, .7), op('MULTIPLY', reach, heft))), op('MULTIPLY', alive, scale))
        calm = op('SUBTRACT', 1, age)
        tall = op('MULTIPLY', op('MULTIPLY', op('MULTIPLY', calm, calm), crest / .1 * bead * scale), alive)
        form = ns.new('ShaderNodeCombineXYZ')
        ls.new(spread, form.inputs['X']); ls.new(spread, form.inputs['Y']); ls.new(tall, form.inputs['Z'])
        ring = ns.new('GeometryNodeInstanceOnPoints')
        ls.new(floor.outputs['Geometry'], ring.inputs['Points'])
        ls.new(wet.outputs['Geometry'], ring.inputs['Instance'])
        ls.new(form.outputs[0], ring.inputs['Scale'])
        ls.new(ring.outputs['Instances'], join.inputs['Geometry'])
    ls.new(join.outputs['Geometry'], output.inputs['Geometry'])
    obj.modifiers.new('Drips off the car', 'NODES').node_group = tree
    heights = [p[2] - low.z for p in points]
    return {'emitters': len(points), 'where': [[round((p[0]-center.x)/scale, 2), round((p[1]-center.y)/scale, 2), round((p[2]-low.z)/scale, 2)] for p in points],
            'lowestMetres': round(min(heights) / scale, 2) if heights else None,
            'highestMetres': round(max(heights) / scale, 2) if heights else None}

