"""Render-only surface detail in car-relative metres; no asset geometry edits."""
import math
import bpy
from mathutils import Vector, Matrix


def noise(nodes, links, scale, frequency, detail=2):
    geometry = nodes.new('ShaderNodeNewGeometry')
    tex = nodes.new('ShaderNodeTexNoise')
    tex.label = 'Surface grain (physical scale)'
    tex.inputs['Scale'].default_value = frequency / scale
    tex.inputs['Detail'].default_value = detail
    links.new(geometry.outputs['Position'], tex.inputs['Vector'])
    return tex.outputs['Fac']


def variation(nodes, links, source, low, high):
    mapping = nodes.new('ShaderNodeMapRange')
    mapping.inputs['To Min'].default_value = low
    mapping.inputs['To Max'].default_value = high
    links.new(source, mapping.inputs['Value'])
    return mapping.outputs[0]


def bump(shader, source, distance, strength, socket='Normal'):
    nodes, links = shader.id_data.nodes, shader.id_data.links
    surface = nodes.new('ShaderNodeBump')
    surface.label = 'Microscopic surface relief'
    surface.inputs['Distance'].default_value = distance
    surface.inputs['Strength'].default_value = strength
    target = shader.inputs[socket]
    if target.is_linked:
        links.new(target.links[0].from_socket, surface.inputs['Normal'])
    links.new(source, surface.inputs['Height'])
    links.new(surface.outputs['Normal'], target)


def lacquer(shader, scale, wet):
    """A smooth resin layer with very slight orange peel, not metallic flakes.

    The pigment color/map, metallic finish and base normal stay authored.
    Apply only to known glossy paint; matte/satin finishes stay untouched.
    """
    nodes, links = shader.id_data.nodes, shader.id_data.links
    texture = noise(nodes, links, scale, 650)
    bump(shader, texture, 0.000012 * scale, 0.18, 'Coat Normal')
    rough = variation(nodes, links, texture, 0.022 if wet else 0.032,
                      0.034 if wet else 0.048)
    links.new(rough, shader.inputs['Coat Roughness'])


def metallic_flake(shader, scale):
    """Aluminium platelets under the lacquer, for a metallic finish only.

    Each platelet is about a third of a millimetre across and lies a few
    degrees off the panel. Close up they glitter; from a hero distance they
    average into the broad bright base lobe that separates metallic from
    solid paint. The lacquer above stays smooth: Coat Normal is not touched.
    """
    nodes, links = shader.id_data.nodes, shader.id_data.links
    geometry = nodes.new('ShaderNodeNewGeometry')
    cells = nodes.new('ShaderNodeTexVoronoi')
    cells.name = cells.label = 'Metallic flake platelets'
    cells.feature = 'F1'
    cells.inputs['Scale'].default_value = 3200 / scale
    links.new(geometry.outputs['Position'], cells.inputs['Vector'])
    tilt = nodes.new('ShaderNodeVectorMath')
    tilt.operation = 'SUBTRACT'
    tilt.inputs[1].default_value = (.5, .5, .5)
    links.new(cells.outputs['Color'], tilt.inputs[0])
    spread = nodes.new('ShaderNodeVectorMath')
    spread.operation = 'SCALE'
    spread.inputs['Scale'].default_value = .24
    links.new(tilt.outputs[0], spread.inputs[0])
    lean = nodes.new('ShaderNodeVectorMath')
    lean.operation = 'ADD'
    target = shader.inputs['Normal']
    links.new(target.links[0].from_socket if target.is_linked else geometry.outputs['Normal'], lean.inputs[0])
    links.new(spread.outputs[0], lean.inputs[1])
    unit = nodes.new('ShaderNodeVectorMath')
    unit.operation = 'NORMALIZE'
    links.new(lean.outputs[0], unit.inputs[0])
    links.new(unit.outputs[0], target)


def rubber(shader, scale, wet):
    nodes, links = shader.id_data.nodes, shader.id_data.links
    # Existing authored maps take priority over generic detail.
    texture = noise(nodes, links, scale, 1600)
    if not shader.inputs['Normal'].is_linked:
        bump(shader, texture, 0.00016 * scale, 0.3)
    if not shader.inputs['Roughness'].is_linked:
        rough = variation(nodes, links, texture, 0.48 if wet else 0.56,
                          0.64 if wet else 0.72)
        links.new(rough, shader.inputs['Roughness'])


def thin_lens(shader):
    """Thin-sheet approximation for browser lenses with no volume extension.

    A ray crosses both interfaces of a thin cover, so its outgoing direction
    is approximately unchanged. A single solid-glass interface bends it as if
    the entire cavity were filled with glass. Preserve smoke tint and opacity.
    """
    nodes, links = shader.id_data.nodes, shader.id_data.links
    transmission = shader.inputs['Transmission Weight']
    if transmission.is_linked or transmission.default_value < 0.99:
        return False
    alpha = shader.inputs['Alpha']
    if alpha.is_linked or alpha.default_value < 0.999:
        return False
    # Do not replace a layered/custom material network or an authored volume.
    destinations = [link.to_socket for link in shader.outputs['BSDF'].links]
    if not destinations or any(s.node.type != 'OUTPUT_MATERIAL' for s in destinations):
        return False
    if any(s.node.inputs['Volume'].is_linked for s in destinations):
        return False
    fresnel = nodes.new('ShaderNodeFresnel')
    fresnel.inputs['IOR'].default_value = shader.inputs['IOR'].default_value
    reflection = nodes.new('ShaderNodeMath')
    reflection.operation = 'MULTIPLY'
    reflection.inputs[1].default_value = 2
    links.new(fresnel.outputs[0], reflection.inputs[0])
    denominator = nodes.new('ShaderNodeMath')
    denominator.operation = 'ADD'
    denominator.inputs[1].default_value = 1
    links.new(fresnel.outputs[0], denominator.inputs[0])
    factor = nodes.new('ShaderNodeMath')
    factor.operation = 'DIVIDE'
    links.new(reflection.outputs[0], factor.inputs[0])
    links.new(denominator.outputs[0], factor.inputs[1])
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    color = shader.inputs['Base Color']
    if color.is_linked:
        links.new(color.links[0].from_socket, transparent.inputs['Color'])
    else:
        transparent.inputs['Color'].default_value = color.default_value
    reflection = nodes.new('ShaderNodeBsdfAnisotropic')
    reflection.inputs['Roughness'].default_value = 0.018
    normal = shader.inputs['Normal']
    if normal.is_linked:
        links.new(normal.links[0].from_socket, fresnel.inputs['Normal'])
        links.new(normal.links[0].from_socket, reflection.inputs['Normal'])
    mix = nodes.new('ShaderNodeMixShader')
    mix.label = 'Thin cover: transmission and two Fresnel interfaces'
    links.new(factor.outputs[0], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(reflection.outputs[0], mix.inputs[2])
    for socket in destinations:
        links.new(mix.outputs[0], socket)
    return True


def _used_rubber(shader, scale, radius):
    """New rubber is an even black. A driven tyre is not.

    Antiozonant blooms the sidewall brown in soft half-hand patches, and the
    tread face is scrubbed to a paler, drier grey than the sidewall.
    """
    ns, ls = shader.id_data.nodes, shader.id_data.links
    color, roughness = shader.inputs['Base Color'], shader.inputs['Roughness']
    patches = variation(ns, ls, noise(ns, ls, scale, 7, 2), -.35, .75)
    bloom = ns.new('ShaderNodeMixRGB')
    bloom.name = 'Sidewall antiozonant bloom'
    bloom.use_clamp = True
    ls.new(color.links[0].from_socket, bloom.inputs[1])
    bloom.inputs[2].default_value = (.078, .060, .043, 1)
    ls.new(patches, bloom.inputs[0])
    band = ns.new('ShaderNodeMapRange')
    band.name = 'Tread face, by normalized wheel radius'
    band.interpolation_type = 'SMOOTHSTEP'
    band.inputs['From Min'].default_value = .955
    band.inputs['From Max'].default_value = .99
    band.inputs['To Max'].default_value = .6
    ls.new(radius, band.inputs['Value'])
    scrub = ns.new('ShaderNodeMixRGB')
    scrub.name = 'Road-scrubbed tread face'
    ls.new(band.outputs[0], scrub.inputs[0])
    ls.new(bloom.outputs[0], scrub.inputs[1])
    scrub.inputs[2].default_value = (.098, .090, .079, 1)
    ls.new(scrub.outputs[0], color)
    dry = ns.new('ShaderNodeMapRange')
    dry.name = 'Scrubbed tread is drier than the sidewall'
    ls.new(band.outputs[0], dry.inputs['Value'])
    dry.inputs['From Max'].default_value = .6
    ls.new(roughness.links[0].from_socket, dry.inputs['To Min'])
    dry.inputs['To Max'].default_value = .84
    ls.new(dry.outputs[0], roughness)


def _wet_tire_treatment(shader, obj, scale, radius):
    """Irregular rubbed rubber and light road residue, with low wet sheen."""
    ns, ls = shader.id_data.nodes, shader.id_data.links
    grain = noise(ns, ls, scale, 38, 3)
    scuff = variation(ns, ls, grain, .04, .34)
    color = shader.inputs['Base Color']
    dust = ns.new('ShaderNodeMixRGB')
    dust.name = 'Light irregular tire road residue'
    if color.is_linked:
        ls.new(color.links[0].from_socket, dust.inputs[1])
    else:
        dust.inputs[1].default_value = color.default_value
    dust.inputs[2].default_value = (.085, .075, .062, 1)
    ls.new(scuff, dust.inputs[0])
    ls.new(dust.outputs[0], color)
    roughness = shader.inputs['Roughness']
    wear = ns.new('ShaderNodeMixRGB')
    wear.name = 'Irregular tire wear roughness'
    ls.new(scuff, wear.inputs[0])
    if roughness.is_linked:
        ls.new(roughness.links[0].from_socket, wear.inputs[1])
    else:
        wear.inputs[1].default_value = (roughness.default_value,) * 3 + (1,)
    wear.inputs[2].default_value = (.73, .73, .73, 1)
    ls.new(wear.outputs[0], roughness)
    geometry = ns.new('ShaderNodeNewGeometry')
    xyz = ns.new('ShaderNodeSeparateXYZ')
    ls.new(geometry.outputs['Position'], xyz.inputs[0])
    low = min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)
    ground = ns.new('ShaderNodeMapRange')
    ground.name = 'Tire dampness falls away from ground contact'
    ground.interpolation_type = 'SMOOTHSTEP'
    ground.inputs['From Min'].default_value = low + .015 * scale
    ground.inputs['From Max'].default_value = low + .23 * scale
    ground.inputs['To Min'].default_value = .62
    ground.inputs['To Max'].default_value = .035
    ls.new(xyz.outputs['Z'], ground.inputs['Value'])
    breakup = variation(ns, ls, grain, .56, 1)
    sheen = ns.new('ShaderNodeMath')
    sheen.operation = 'MULTIPLY'
    ls.new(ground.outputs[0], sheen.inputs[0])
    ls.new(breakup, sheen.inputs[1])
    ls.new(sheen.outputs[0], shader.inputs['Coat Weight'])
    shader.inputs['Coat IOR'].default_value = 1.333
    shader.inputs['Coat Roughness'].default_value = .19
    _used_rubber(shader, scale, radius)


def _molded_tire_letters(obj, scale, axle, radial_axes, dims, car_center):
    """Generic, shallow relief on actual sidewall hits; no brand or size claim.

    Text is separate render geometry. Each glyph is projected onto the existing
    sidewall, with its vertices conformed to that surface; the tire stays intact.
    """
    corners = [Vector(p) for p in obj.bound_box]
    center = sum(corners, Vector()) / 8
    matrix = obj.matrix_world
    inverse = matrix.inverted()
    normal_matrix = matrix.to_3x3().inverted().transposed()
    axis = Vector(tuple(1 if i == axle else 0 for i in range(3)))
    world_axis = (matrix.to_3x3() @ axis).normalized()
    side = 1 if ((matrix @ center) - car_center).dot(world_axis) >= 0 else -1
    outward = axis * side
    # A world-up reference makes molded words readable on either side.
    up = inverse.to_3x3() @ Vector((0, 0, 1))
    up -= axis * up.dot(axis)
    if up.length < .01:
        return 0
    up.normalize()
    right = up.cross(outward).normalized()
    radius = min(dims[i] for i in radial_axes) * .5
    ray_start = dims[axle] * .65
    vertices, faces = [], []
    # Only neutral construction-style words, never counterfeit brand/size text.
    for word, angle_center, direction, radial_fraction in [
            ('PERFORMANCE', 0, 1, .81), ('ROAD TIRE', math.pi, -1, .89)]:
        step = .042
        for index, character in enumerate(word):
            if character == ' ':
                continue
            angle = angle_center + direction * (index - (len(word) - 1) / 2) * step
            radial = up * math.cos(angle) + right * math.sin(angle)
            tangent = (right * math.cos(angle) - up * math.sin(angle)) * direction
            origin = center + radial * radius * radial_fraction + outward * ray_start
            hit, location, normal, _ = obj.ray_cast(origin, -outward, distance=dims[axle] * 1.3)
            if not hit or normal.dot(outward) < .65:
                continue
            normal = (normal_matrix @ normal).normalized()
            tangent = (matrix.to_3x3() @ tangent).normalized()
            tangent -= normal * tangent.dot(normal)
            tangent.normalize()
            vertical = normal.cross(tangent).normalized()
            rotation = Matrix((tangent, vertical, normal)).transposed().to_4x4()
            rotation.translation = matrix @ location
            curve = bpy.data.curves.new('Generic molded letter', 'FONT')
            curve.body = character
            curve.size = .018 * scale
            curve.align_x = 'CENTER'
            curve.extrude = .00022 * scale
            curve.bevel_depth = .00008 * scale
            curve.bevel_resolution = 1
            curve.resolution_u = 3
            glyph = bpy.data.objects.new('Molded letter temporary', curve)
            bpy.context.collection.objects.link(glyph)
            glyph.matrix_world = rotation
            evaluated = glyph.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            start = len(vertices)
            for vertex in mesh.vertices:
                world = rotation @ vertex.co
                # Preserve the tiny extrusion while conforming the glyph base
                # to the tire curvature instead of floating a planar label.
                local = inverse @ world
                origin = local.copy()
                origin[axle] = center[axle] + side * ray_start
                hit, location, _, _ = obj.ray_cast(origin, -outward, distance=dims[axle] * 1.3)
                if hit:
                    world = matrix @ location + normal * (vertex.co.z + .00010 * scale)
                vertices.append(world)
            faces.extend(tuple(start + i for i in face.vertices) for face in mesh.polygons)
            evaluated.to_mesh_clear()
            bpy.data.objects.remove(glyph, do_unlink=True)
            bpy.data.curves.remove(curve)
    if not vertices:
        return 0
    name = 'Rain — molded sidewall lettering — ' + obj.name
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    lettering = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(lettering)
    lettering['mv_render_detail'] = 'generic_molded_tire_lettering'
    lettering['source_tire'] = obj.name
    lettering['words'] = 'PERFORMANCE / ROAD TIRE'
    material = bpy.data.materials.get('Rain — molded tire rubber')
    if material is None:
        material = bpy.data.materials.new('Rain — molded tire rubber')
        material.use_nodes = True
        shader = material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (.012, .012, .011, 1)
        shader.inputs['Roughness'].default_value = .52
        shader.inputs['Coat Weight'].default_value = .16
        shader.inputs['Coat Roughness'].default_value = .24
        shader.inputs['Coat IOR'].default_value = 1.333
    mesh.materials.append(material)
    return 1


def tire_sidewalls(meshes, scale, wet=False):
    """Sub-mm concentric molding ridges on untextured tire sidewalls only.

    Uses each wheel's local bounds (so installed wheel offsets/rotations work).
    Dry scenes retain the original molding-only treatment. Rain scenes add
    neutral molded words, light wear and a sheen that fades above the ground.
    """
    count = 0
    centers = [obj.matrix_world.translation for obj in meshes
               if obj.name.lower().startswith(('tire-', 'tyre-'))]
    car_center = sum(centers, Vector()) / len(centers) if centers else Vector()
    for obj in meshes:
        if not obj.name.lower().startswith(('tire-', 'tyre-')):
            continue
        corners = [Vector(p) for p in obj.bound_box]
        dims = [max(p[i] for p in corners)-min(p[i] for p in corners) for i in range(3)]
        axle = min(range(3), key=lambda i: dims[i])
        radial_axes = [i for i in range(3) if i != axle]
        a, b = [dims[i] for i in radial_axes]
        # Reject small attached rubber pieces and non-circular meshes.
        if min(a, b) < .25 * scale or min(a, b) / max(a, b) < .9:
            continue
        for slot, mat in enumerate(list(obj.data.materials)):
            if not mat or not mat.use_nodes or mat.name.lower().split('.')[0] != 'rubber':
                continue
            # An authored tire normal/map carries more reliable detail.
            if any(n.type == 'TEX_IMAGE' for n in mat.node_tree.nodes):
                continue
            mat = mat.copy()
            mat.name = 'Render tire sidewall — ' + obj.name
            obj.data.materials[slot] = mat
            shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            ns, ls = mat.node_tree.nodes, mat.node_tree.links
            uv = ns.new('ShaderNodeTexCoord')
            center = ns.new('ShaderNodeVectorMath'); center.operation = 'SUBTRACT'
            center.inputs[1].default_value = (.5, .5, .5)
            ls.new(uv.outputs['Generated'], center.inputs[0])
            plane = ns.new('ShaderNodeVectorMath'); plane.operation = 'MULTIPLY'
            plane.inputs[1].default_value = tuple(0 if i == axle else 2 for i in range(3))
            ls.new(center.outputs[0], plane.inputs[0])
            radius = ns.new('ShaderNodeVectorMath'); radius.operation = 'LENGTH'
            ls.new(plane.outputs[0], radius.inputs[0])

            def math_node(operation, x, value):
                node = ns.new('ShaderNodeMath'); node.operation = operation
                ls.new(x, node.inputs[0]); node.inputs[1].default_value = value
                return node.outputs[0]

            inner = math_node('GREATER_THAN', radius.outputs['Value'], .76)
            outer = math_node('LESS_THAN', radius.outputs['Value'], .94)
            band = ns.new('ShaderNodeMath'); band.operation = 'MULTIPLY'
            ls.new(inner, band.inputs[0]); ls.new(outer, band.inputs[1])
            wave = math_node('MULTIPLY', radius.outputs['Value'], 1100)
            wave = math_node('SINE', wave, 0)
            relief = ns.new('ShaderNodeMath'); relief.operation = 'MULTIPLY'
            ls.new(wave, relief.inputs[0]); ls.new(band.outputs[0], relief.inputs[1])
            bump(shader, relief.outputs[0], (.00016 if wet else .000035) * scale, .5 if wet else .25)
            if wet:
                _wet_tire_treatment(shader, obj, scale, radius.outputs['Value'])
                _molded_tire_letters(obj, scale, axle, radial_axes, dims, car_center)
            count += 1
    return count
