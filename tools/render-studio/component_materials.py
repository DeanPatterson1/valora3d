"""Measured component overrides for the inspected 992 Manthey asset only.

Mesh names alone are not enough to apply these corrections to other cars.
Keep the outer smoke tint, all light states, paint colors and authored maps.
"""
import re
from mathutils import Vector
import surface_detail


MANTHEY_992 = '2024-porsche-911-gt3-rs-manthey-992'


def weathered_rotors(meshes, car_id, scale):
    """Matching used carbon-ceramic friction faces, distinct from aero covers."""
    if car_id != MANTHEY_992:
        return []
    report = []
    for obj in meshes:
        if not re.fullmatch(r'rotor-[fr][lr]', obj.name):
            continue
        for i, original in enumerate(list(obj.data.materials)):
            if not original or not original.use_nodes or original.name.split('.')[0] != 'Brake Disc':
                continue
            if any(n.type == 'TEX_IMAGE' for n in original.node_tree.nodes):
                continue
            mat = original.copy(); mat.name = 'Rain — used ceramic rotor — ' + obj.name
            obj.data.materials[i] = mat
            mat['mv_rain_rotor'] = True
            ns, ls = mat.node_tree.nodes, mat.node_tree.links
            shader = next(n for n in ns if n.type == 'BSDF_PRINCIPLED')
            tex = surface_detail.noise(ns, ls, scale, 1100, 2)
            grain = ns.new('ShaderNodeValToRGB')
            grain.name = 'Ceramic aggregate and brake dust'
            grain.color_ramp.elements[0].position = .24
            grain.color_ramp.elements[0].color = (.19, .20, .20, 1)
            grain.color_ramp.elements[1].position = .76
            grain.color_ramp.elements[1].color = (.70, .71, .72, 1)
            ls.new(tex, grain.inputs[0])
            tint = ns.new('ShaderNodeMixRGB'); tint.blend_type = 'MULTIPLY'
            tint.inputs[0].default_value = 1
            color = shader.inputs['Base Color']
            if color.is_linked:
                ls.new(color.links[0].from_socket, tint.inputs[1])
            else:
                tint.inputs[1].default_value = color.default_value
            ls.new(grain.outputs[0], tint.inputs[2]); ls.new(tint.outputs[0], color)
            rough = surface_detail.variation(ns, ls, tex, .39, .56)
            ls.new(rough, shader.inputs['Roughness'])
            surface_detail.bump(shader, tex, .000025*scale, .18)
            shader.inputs['Metallic'].default_value = .4
            shader.inputs['Coat Weight'].default_value = 0
            _swept_face(obj, shader, scale)
            report.append({'mesh': obj.name, 'role': 'weathered-ceramic-rotor'})
    return report


def _swept_face(obj, shader, scale):
    """Pads polish a used disc in concentric bands; the unswept rims stay dull.

    Radius comes from the disc's own bounds, so it follows any wheel offset.
    Bands are 1D noise along that radius: every revolution lays the same
    track, which is why real wear is circular and never blotchy.
    """
    ns, ls = shader.id_data.nodes, shader.id_data.links
    corners = [Vector(p) for p in obj.bound_box]
    dims = [max(p[i] for p in corners) - min(p[i] for p in corners) for i in range(3)]
    axle = min(range(3), key=lambda i: dims[i])
    coords = ns.new('ShaderNodeTexCoord')
    centre = ns.new('ShaderNodeVectorMath'); centre.operation = 'SUBTRACT'
    centre.inputs[1].default_value = (.5, .5, .5)
    ls.new(coords.outputs['Generated'], centre.inputs[0])
    plane = ns.new('ShaderNodeVectorMath'); plane.operation = 'MULTIPLY'
    plane.inputs[1].default_value = tuple(0 if i == axle else 2 for i in range(3))
    ls.new(centre.outputs[0], plane.inputs[0])
    radius = ns.new('ShaderNodeVectorMath'); radius.operation = 'LENGTH'
    radius.name = 'Disc radius, 0 hub to 1 rim'
    ls.new(plane.outputs[0], radius.inputs[0])

    def track(frequency, detail):
        tex = ns.new('ShaderNodeTexNoise'); tex.noise_dimensions = '1D'
        tex.inputs['Scale'].default_value = frequency
        tex.inputs['Detail'].default_value = detail
        ls.new(radius.outputs['Value'], tex.inputs['W'])
        return tex.outputs['Fac']

    bands, scoring = track(34, 3), track(420, 2)
    swept = ns.new('ShaderNodeMapRange'); swept.name = 'Pad-swept annulus'
    swept.interpolation_type = 'SMOOTHSTEP'
    swept.inputs['From Min'].default_value = .955
    swept.inputs['From Max'].default_value = .985
    swept.inputs['To Min'].default_value = 1
    swept.inputs['To Max'].default_value = 0
    ls.new(radius.outputs['Value'], swept.inputs['Value'])
    color, rough = shader.inputs['Base Color'], shader.inputs['Roughness']
    wear = ns.new('ShaderNodeMapRange'); wear.name = 'Concentric pad wear bands'
    wear.inputs['From Min'].default_value = .3
    wear.inputs['From Max'].default_value = .7
    wear.inputs['To Min'].default_value = .62
    wear.inputs['To Max'].default_value = 1.08
    ls.new(bands, wear.inputs['Value'])
    shade = ns.new('ShaderNodeMixRGB'); shade.blend_type = 'MULTIPLY'; shade.inputs[0].default_value = 1
    ls.new(color.links[0].from_socket, shade.inputs[1])
    ls.new(wear.outputs[0], shade.inputs[2])
    ls.new(shade.outputs[0], color)
    # Swept face is burnished (.20 to .34); the unswept rim keeps the dusty .39 to .56.
    polish = ns.new('ShaderNodeMapRange'); polish.name = 'Burnished tracks'
    polish.inputs['To Min'].default_value = .20
    polish.inputs['To Max'].default_value = .34
    ls.new(scoring, polish.inputs['Value'])
    mix = ns.new('ShaderNodeMixRGB'); mix.name = 'Swept face against dusty rim'
    ls.new(swept.outputs[0], mix.inputs[0])
    ls.new(rough.links[0].from_socket, mix.inputs[1])
    ls.new(polish.outputs[0], mix.inputs[2])
    ls.new(mix.outputs[0], rough)
    surface_detail.bump(shader, scoring, .00006*scale, .35)


def rotor_face_normals(obj):
    """Stop hole-wall normals pulling flat rotor faces into triangular dents.

    Change only corner normals on planar faces aligned with the axle. Keep
    vertices, topology, bevel/hole walls and all other car normals intact.
    """
    corners = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    dims = [max(v[i] for v in corners) - min(v[i] for v in corners) for i in range(3)]
    axle = min(range(3), key=lambda i: dims[i])
    if dims[axle] > max(dims) * .15:
        return 0
    normals = [tuple(n.vector) for n in obj.data.corner_normals]
    transform = obj.matrix_world.to_3x3().inverted().transposed()
    count = 0
    for face in obj.data.polygons:
        world_normal = (transform @ face.normal).normalized()
        if abs(world_normal[axle]) < .999:
            continue
        for index in face.loop_indices:
            normals[index] = tuple(face.normal)
        count += 1
    if count:
        obj.data.normals_split_custom_set(normals)
    return count


def prepare(meshes, car_id, wet=False, scale=1.0):
    if car_id != MANTHEY_992:
        return []
    report = []
    for obj in meshes:
        if re.fullmatch(r'rotor-[fr][lr]', obj.name) and any(m and m.name.split('.')[0] == 'Brake Disc' for m in obj.data.materials):
            corrected = rotor_face_normals(obj)
            if corrected:
                report.append({'mesh': obj.name, 'role': 'planar-rotor-normals', 'faces': corrected})
        match = re.fullmatch(r'headlight-[lr]-lens-(\d+)', obj.name)
        caliper = re.fullmatch(r'caliper-(front|rear)-[lr]', obj.name)
        for index, original in enumerate(list(obj.data.materials)):
            if not original or not original.use_nodes:
                continue
            shader = next((n for n in original.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if shader is None:
                continue
            if match and original.name.startswith('mv-smoke-lens'):
                # 1/3–8 are small internal optical pieces. 9 is the outer
                # cover; 2 is a side marker despite the source mesh name.
                role = 'cover' if int(match[1]) in (2, 9) else 'internal-optic'
                if (shader.inputs['Transmission Weight'].is_linked or
                        shader.inputs['Transmission Weight'].default_value < .99 or
                        shader.inputs['Alpha'].is_linked or shader.inputs['Alpha'].default_value < .999):
                    continue
                if any(n.type == 'OUTPUT_MATERIAL' and n.inputs['Volume'].is_linked for n in original.node_tree.nodes):
                    continue
                mat = original.copy()
                obj.data.materials[index] = mat
                mat['mv_optical_role'] = role
                if role == 'internal-optic':
                    # The viewer applied one smoke rule to every glass piece.
                    # Do not multiply that tint through successive internals.
                    p = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                    if not p.inputs['Base Color'].is_linked:
                        p.inputs['Base Color'].default_value = (.98, .98, .98, 1)
                elif wet:
                    mat['mv_wet_surface'] = True
                report.append({'mesh': obj.name, 'role': role})
            elif caliper and original.name.split('.')[0] == 'Brakes':
                # This source has a colored caliper with metal=.8, roughness=1.
                # A real caliper is pigment under a glossy clear lacquer, the
                # same construction as body paint. Leave customized/map-
                # driven finishes and its selected color untouched.
                if any(shader.inputs[k].is_linked for k in ('Metallic', 'Roughness')):
                    continue
                if abs(shader.inputs['Metallic'].default_value - .8) > .001 or abs(shader.inputs['Roughness'].default_value - 1) > .001:
                    continue
                mat = original.copy()
                mat.name = 'Render caliper coating — ' + obj.name
                obj.data.materials[index] = mat
                p = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                for key, value in {'Metallic': 0, 'Roughness': .24, 'Coat Weight': 1, 'Coat Roughness': .04,
                                   'Specular IOR Level': .2}.items():
                    p.inputs[key].default_value = value
                surface_detail.lacquer(p, scale, wet)
                report.append({'mesh': obj.name, 'role': 'painted-caliper'})
    return report
