"""Conservative offline equivalents for known ModVision browser materials.

Authored unknown materials/textures and every per-panel color remain intact.
In particular, mv-window-tint represents deliberate opaque privacy glass.
"""
import math
import random

import bpy
from mathutils import Vector, Matrix
import surface_detail
from material_classes import classify


def set_input(shader, name, value):
    socket = shader.inputs.get(name)
    if socket is not None:
        for link in list(socket.links):
            shader.id_data.links.remove(link)
        socket.default_value = value


def _slots_by_material(meshes):
    """Material name -> ModVision slot ids of the meshes using it (from the
    `mvSlot` glTF extra the site writes; empty on an untagged snapshot)."""
    result = {}
    for obj in meshes:
        try:
            slot = obj.get('mvSlot')
        except (AttributeError, TypeError):
            slot = None
        if not isinstance(slot, str):
            continue
        for mat in obj.data.materials:
            if mat:
                result.setdefault(mat.name, set()).add(slot)
    return result


def _blend_to_glass(shader):
    """An alpha-blended lens (authored `MV_HeadlightGlass` at alpha .18, artist
    "Headlight Glass") fades the reflector behind it instead of covering it with
    glass. Turn it into a transmissive cover so thin_lens can take it: keep the
    authored tint, drop the fade."""
    alpha = shader.inputs['Alpha']
    transmission = shader.inputs['Transmission Weight']
    if alpha.is_linked or transmission.is_linked or alpha.default_value >= 0.999:
        return False
    set_input(shader, 'Alpha', 1.0)
    set_input(shader, 'Transmission Weight', 1.0)
    return True


def calibrate_materials(meshes, wet=False, scale=1.0):
    report = []
    materials = {m for obj in meshes for m in obj.data.materials if m}
    slots_of = _slots_by_material(meshes)
    for mat in sorted(materials, key=lambda m: m.name):
        if not mat.use_nodes:
            continue
        shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if shader is None:
            continue
        name = mat.name.lower()
        alpha_socket, trans_socket, metal_socket = shader.inputs['Alpha'], shader.inputs['Transmission Weight'], shader.inputs['Metallic']
        kind = classify(mat.name, slots_of.get(mat.name, ()),
                        alpha=None if alpha_socket.is_linked else alpha_socket.default_value,
                        transmission=1.0 if trans_socket.is_linked else trans_socket.default_value,
                        metallic=0.0 if metal_socket.is_linked else metal_socket.default_value)
        category = None
        if kind == 'carbon':
            # The browser's charcoal texture/tint was calibrated against a
            # different environment. Keep its actual weave and UVs, lower the
            # diffuse reflectance to carbon instead of silver/gray plastic.
            socket = shader.inputs['Base Color']
            tint = mat.node_tree.nodes.new('ShaderNodeMixRGB')
            tint.blend_type = 'MULTIPLY'
            tint.inputs[0].default_value = 1
            tint.inputs[2].default_value = (0.065, 0.068, 0.075, 1)
            if socket.is_linked:
                mat.node_tree.links.new(socket.links[0].from_socket, tint.inputs[1])
            else:
                tint.inputs[1].default_value = socket.default_value
            mat.node_tree.links.new(tint.outputs[0], socket)
            set_input(shader, 'Metallic', 0.0)
            set_input(shader, 'Specular IOR Level', 0.2)
            set_input(shader, 'Roughness', 0.35)
            set_input(shader, 'Coat Weight', 1.0)
            set_input(shader, 'Coat Roughness', 0.025 if wet else 0.04)
            # Existing normal maps describe the fabric UNDER smooth resin.
            set_input(shader, 'Coat Normal', (0, 0, 0))
            category = 'carbon'
        elif kind == 'paint':
            # Do not replace Base Color: different panels can have different
            # user-selected colors, finishes and textures in the same build.
            set_input(shader, 'IOR', 1.5)
            if shader.inputs['Coat Weight'].default_value > 0.5:
                # Browser solid paint uses a diffuse pigment under lacquer.
                # Avoid an extra broad white base highlight washing it out.
                set_input(shader, 'Specular IOR Level', 0.15)
                surface_detail.lacquer(shader, scale, wet)
                # The browser's metallic finish exports metalness .60; solid,
                # gloss, satin and frozen export .10 or less.
                metal = shader.inputs['Metallic']
                if not metal.is_linked and metal.default_value >= .4:
                    surface_detail.metallic_flake(shader, scale)
                    mat['mv_metallic_flake'] = True
            category = 'paint'
        elif kind == 'privacy-glass':
            set_input(shader, 'IOR', 1.52)
            set_input(shader, 'Roughness', 0.018)
            set_input(shader, 'Coat Weight', 0.0)
            set_input(shader, 'Specular IOR Level', 0.5)
            # Preserve deliberate opacity, tint and transmission from snapshot.
            category = 'privacy-glass'
        elif kind == 'lamp-lens':
            # Light covers use transmission; avoid two stacked reflective coats.
            set_input(shader, 'Coat Weight', 0.0)
            set_input(shader, 'Roughness', 0.025)
            _blend_to_glass(shader)
            surface_detail.thin_lens(shader)
            category = 'lamp-lens'
        elif kind == 'rubber':
            surface_detail.rubber(shader, scale, wet)
            category = 'rubber'
        if wet and category in ('paint', 'carbon', 'privacy-glass'):
            mat['mv_wet_surface'] = True
        if category:
            report.append({'material': mat.name, 'category': category})
    return report


BEAD_LIMIT = 60000


def add_water_beads(meshes, scale, seed=20260915):
    """Area-weighted clusters, fine mist, merged drops and vertical runoff.

    One geometry-nodes instance cloud rather than thousands of Blender objects.
    Radius distribution favors sub-mm beads. Larger merged forms are sparse;
    runoff follows projected gravity rather than a random direction.
    No live build mesh is changed.
    """
    from mathutils.noise import noise as spatial_noise

    rng = random.Random(seed)
    vertices, rotations, sizes, kinds = [], [], [], []
    triangles, expected_total = [], 0
    for obj in sorted(meshes, key=lambda o: o.name):
        wet_slots = {i for i, m in enumerate(obj.data.materials) if m and m.get('mv_wet_surface')}
        if not wet_slots:
            continue
        obj.data.calc_loop_triangles()
        matrix = obj.matrix_world
        normal_matrix = matrix.to_3x3().inverted().transposed()
        for tri in obj.data.loop_triangles:
            if tri.material_index not in wet_slots:
                continue
            normal = (normal_matrix @ tri.normal).normalized()
            if normal.z < -0.05:
                continue
            a, b, c = [matrix @ obj.data.vertices[i].co for i in tri.vertices]
            area = (b - a).cross(c - a).length * 0.5
            expected = area / (scale * scale) * (9000 if normal.z > 0.3 else 3600)
            triangles.append((a, b, c, normal, expected))
            expected_total += expected
    # Allocate candidates across the complete car before sampling. A hard cap
    # during sorted object traversal used to leave later panels relatively dry.
    allocation = min(1, 150000 / max(expected_total, 1))
    for a, b, c, normal, expected in triangles:
        expected *= allocation
        count = int(expected) + (rng.random() < expected % 1)
        for _ in range(count):
            if len(vertices) >= BEAD_LIMIT:
                break
            u, v = math.sqrt(rng.random()), rng.random()
            point = a * (1 - u) + b * (u * (1 - v)) + c * (u * v)
            metres = point / scale
            # Nested irregular patches make wet clusters separated by calmer
            # paint, with smaller mist beads between the larger droplets.
            broad = .5 + .5 * spatial_noise(metres * 8.5, noise_basis='PERLIN_ORIGINAL')
            cluster = max(0, min(1, (broad - .30) / .40)) ** 2.2
            fine = .5 + .5 * spatial_noise(metres * 37 + Vector((13, 4, 7)), noise_basis='PERLIN_ORIGINAL')
            patch = .04 + .92 * cluster * (.45 + .55 * fine)
            if rng.random() > patch:
                continue
            chance = rng.random()
            down = Vector((0, 0, -1)) - normal * normal.dot(Vector((0, 0, -1)))
            # A waxed panel beads water into 1.5 to 5 mm domes with a few
            # 6 to 10 mm ones; that range is what reads at a hero distance.
            # Sub-millimetre mist only fills the gaps between them.
            if chance < .34:
                kind = 3  # Mist beads, 0.5–1.2 mm across.
                radius = scale * rng.uniform(.00025, .0006)
            elif chance < .84:
                kind = 0
                radius = scale * (.0007 + rng.random() ** 2 * .0017)
            else:
                kind = 0
                radius = scale * (.0022 + rng.random() ** 2.6 * .0058)  # rare pooled drops to 8 mm
            width = radius * rng.uniform(.86, 1.12)
            length = radius * rng.uniform(.85, 1.30)
            # High contact angle on lacquer; large drops sag under gravity.
            height = radius * rng.uniform(.50, .74) * (1 if radius < .0022 * scale else .78)
            if chance > .965:
                kind = 1
                width *= 1.25
                length *= rng.uniform(1.6, 2.5)
                height *= .8
            if chance > .985 and normal.z < .94 and down.length > .28:
                kind = 2  # 6–24 mm long; includes genuinely vertical panels.
                width = scale * rng.uniform(.00028, .00065)
                length = scale * rng.uniform(.003, .012)
                height = scale * rng.uniform(.00010, .00022)
            if down.length < .02 or kind in (0, 3):
                angle = rng.random() * math.tau
                down = normal.to_track_quat('Z', 'Y') @ Vector((math.sin(angle), math.cos(angle), 0))
                down -= normal * down.dot(normal)
            down.normalize()
            across = down.cross(normal).normalized()
            vertices.append(point + normal * height * .22)
            rotations.append(Matrix((across, down, normal)).transposed().to_euler())
            sizes.append((width, length, height))
            kinds.append(kind)
    if not vertices:
        return 0
    cloud = bpy.data.meshes.new('Rain bead positions')
    cloud.from_pydata(vertices, [], [])
    for name, values in [('bead_rotation', rotations), ('bead_scale', sizes)]:
        attribute = cloud.attributes.new(name, 'FLOAT_VECTOR', 'POINT')
        attribute.data.foreach_set('vector', [value for vector in values for value in vector])
    obj = bpy.data.objects.new('Rain — surface water beads', cloud)
    bpy.context.collection.objects.link(obj)
    obj['bead_count'] = kinds.count(0)
    obj['merged_count'] = kinds.count(1)
    obj['runoff_count'] = kinds.count(2)
    obj['mist_count'] = kinds.count(3)
    kind_attribute = cloud.attributes.new('bead_kind', 'INT', 'POINT')
    kind_attribute.data.foreach_set('value', kinds)
    water = bpy.data.materials.new('Rain — clean water IOR 1.333')
    water.use_nodes = True
    shader = water.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (0.97, 0.99, 1, 1)
    shader.inputs['Roughness'].default_value = 0.0
    shader.inputs['IOR'].default_value = 1.333
    shader.inputs['Transmission Weight'].default_value = 1
    tree = bpy.data.node_groups.new('Surface water bead instances', 'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes, links = tree.nodes, tree.links
    source, output = nodes.new('NodeGroupInput'), nodes.new('NodeGroupOutput')
    sphere = nodes.new('GeometryNodeMeshUVSphere')
    sphere.inputs['Segments'].default_value = 16
    sphere.inputs['Rings'].default_value = 10
    sphere.inputs['Radius'].default_value = 1
    # A small smooth radial distortion breaks the perfect oval silhouette;
    # height/width and orientation remain physical per-instance attributes.
    position = nodes.new('GeometryNodeInputPosition')
    normal = nodes.new('GeometryNodeInputNormal')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1.7
    noise.inputs['Detail'].default_value = 1
    links.new(position.outputs[0], noise.inputs['Vector'])
    offset = nodes.new('ShaderNodeMapRange')
    offset.inputs['To Min'].default_value = -.12
    offset.inputs['To Max'].default_value = .12
    links.new(noise.outputs['Fac'], offset.inputs['Value'])
    vector = nodes.new('ShaderNodeVectorMath')
    vector.operation = 'SCALE'
    links.new(normal.outputs[0], vector.inputs[0])
    links.new(offset.outputs[0], vector.inputs[3])
    warp = nodes.new('GeometryNodeSetPosition')
    links.new(sphere.outputs['Mesh'], warp.inputs['Geometry'])
    links.new(vector.outputs[0], warp.inputs['Offset'])
    smooth = nodes.new('GeometryNodeSetShadeSmooth')
    links.new(warp.outputs[0], smooth.inputs['Geometry'])
    assign = nodes.new('GeometryNodeSetMaterial')
    assign.inputs['Material'].default_value = water
    links.new(smooth.outputs['Geometry'], assign.inputs['Geometry'])
    instance = nodes.new('GeometryNodeInstanceOnPoints')
    links.new(source.outputs['Geometry'], instance.inputs['Points'])
    links.new(assign.outputs['Geometry'], instance.inputs['Instance'])
    for name, socket in [('bead_rotation', 'Rotation'), ('bead_scale', 'Scale')]:
        attr = nodes.new('GeometryNodeInputNamedAttribute')
        attr.data_type = 'FLOAT_VECTOR'
        attr.inputs['Name'].default_value = name
        links.new(attr.outputs['Attribute'], instance.inputs[socket])
    links.new(instance.outputs['Instances'], output.inputs['Geometry'])
    modifier = obj.modifiers.new('Instanced water beads', 'NODES')
    modifier.node_group = tree
    return len(vertices)
