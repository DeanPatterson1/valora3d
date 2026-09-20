"""Render-only rain detail: localized, faint impact rings in shallow water."""
import bpy


def puddle_normal(material, position, puddles, base_normal, scale):
    """Small expanding wave packets, staggered per irregular impact cell.

    The normal is confined to the puddle mask. Rings fade before the next
    impact, never displace the road, and never become a full-surface wave grid.
    """
    nodes, links = material.node_tree.nodes, material.node_tree.links

    def op(operation, a, b=None, label=''):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        node.label = label
        for index, value in enumerate((a, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                node.inputs[index].default_value = value
            else:
                links.new(value, node.inputs[index])
        return node.outputs[0]

    time = nodes.new('ShaderNodeValue')
    time.name = 'Rain impact time seconds'
    time.label = 'Elapsed seconds — animated at job frame rate'
    time.outputs[0].default_value = 0
    material['mv_animated_puddles'] = True
    cell = nodes.new('ShaderNodeTexVoronoi')
    cell.name = 'Sparse irregular rain impact centers'
    cell.voronoi_dimensions = '2D'
    cell.inputs['Scale'].default_value = 2.4 / scale
    links.new(position, cell.inputs['Vector'])
    separate = nodes.new('ShaderNodeSeparateColor')
    links.new(cell.outputs['Color'], separate.inputs['Color'])
    # Independent phase, lifetime and sparse occupancy prevent synchronized
    # circles. Distance is converted back to car-relative metres.
    frequency = op('ADD', op('MULTIPLY', separate.outputs['Green'], .24), .52)
    phase = op('ADD', op('MULTIPLY', time.outputs[0], frequency), separate.outputs['Red'])
    age = op('FRACT', phase)
    distance = op('MULTIPLY', cell.outputs['Distance'], 1 / 2.4)
    # Drops differ, so rings do: each impact cell draws its own reach, from
    # about half to one and two thirds of the base, decorrelated from its phase.
    variety = op('FRACT', op('ADD', op('MULTIPLY', separate.outputs['Red'], 7.31),
                                op('MULTIPLY', separate.outputs['Green'], 3.17)))
    variety = op('ADD', .55, op('MULTIPLY', variety, 1.1))
    radius = op('MULTIPLY', op('MULTIPLY', age, variety), .17, 'Ring reach metres')
    front = op('SUBTRACT', distance, radius)
    envelope = op('MAXIMUM', op('SUBTRACT', 1, op('MULTIPLY', op('ABSOLUTE', front), 40, 'Ring envelope sharpness')), 0)
    envelope = op('MULTIPLY', envelope, envelope)
    wave = op('SINE', op('MULTIPLY', front, 230, 'Ring wave number'))
    fade_in = op('MINIMUM', op('MULTIPLY', age, 8), 1)
    fade_out = op('SUBTRACT', 1, age)
    fade = op('MULTIPLY', fade_in, op('MULTIPLY', fade_out, fade_out))
    sparse = op('GREATER_THAN', separate.outputs['Blue'], .60)
    height = op('MULTIPLY', wave, op('MULTIPLY', envelope, fade))
    height = op('MULTIPLY', height, op('MULTIPLY', sparse, puddles))
    bump = nodes.new('ShaderNodeBump')
    bump.name = 'Localized shallow-water ripple normal'
    bump.inputs['Distance'].default_value = .00026 * scale
    bump.inputs['Strength'].default_value = .35
    links.new(height, bump.inputs['Height'])
    links.new(base_normal, bump.inputs['Normal'])
    return bump.outputs['Normal']


def configure_ripple_animation(scene, first, total):
    """Linear time for any job length, FPS, start frame, or motion-blur sample."""
    fps = scene.render.fps / scene.render.fps_base
    end = first + max(1, total - 1)
    count = 0
    for material in bpy.data.materials:
        if not material.use_nodes or not material.get('mv_animated_puddles'):
            continue
        node = material.node_tree.nodes.get('Rain impact time seconds')
        if node is None:
            continue
        # Reconfiguring a proof at another duration/start must remove old
        # timing keys while preserving any unrelated material animation.
        animation = material.node_tree.animation_data
        if animation and animation.action:
            for layer in animation.action.layers:
                for strip in layer.strips:
                    for channelbag in strip.channelbags:
                        for curve in list(channelbag.fcurves):
                            if node.name in curve.data_path:
                                channelbag.fcurves.remove(curve)
        socket = node.outputs[0]
        socket.default_value = 0
        socket.keyframe_insert(data_path='default_value', frame=first)
        socket.default_value = (end - first) / fps
        socket.keyframe_insert(data_path='default_value', frame=end)
        action = material.node_tree.animation_data.action
        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in strip.channelbags:
                    for curve in channelbag.fcurves:
                        if node.name not in curve.data_path:
                            continue
                        curve.extrapolation = 'LINEAR'
                        for key in curve.keyframe_points:
                            key.interpolation = 'LINEAR'
        count += 1
    scene.frame_set(first)
    return count
