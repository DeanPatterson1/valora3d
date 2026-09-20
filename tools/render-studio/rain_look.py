"""Art-directed rainy-film look, separate from faithful snapshot calibration.

The user requested muted paint and translucent window tint for this scene.
Those overrides live only in the offline render; the browser build is unchanged.
"""
import bpy
from mathutils import Vector

from render_materials import set_input
import surface_detail
import film_camera
from component_materials import MANTHEY_992

# One place for the art direction. The sky stays at its photographed level
# and exposure sets the mood, so lamps, sky and reflections keep a physical
# relationship. A CLI proof job may override keys through its "look" object;
# API jobs cannot (jobs.py rejects unknown fields).
LOOK = {
    'exposure': -0.30,
    # Black point and contrast were set against the owner's reference frames
    # (checks/visual-audit/rain-*.png): 12 to 41 % of their pixels sit under
    # display level 16 and their 5th percentile is 0 to 3. Medium High
    # Contrast with a positive veil measured 3 to 5 % and 17 to 20 on the
    # same five shots, so black paint read as charcoal.
    'view_look': 'AgX - High Contrast',
    'world_saturation': .85,
    'plate_saturation': .80,
    'plate_value': 1.0,
    'foliage_saturation': .80,
    'foliage_value': .85,
    # Thin scattering around the car, so its blacks stay black. The distance
    # fade is a second, denser ground-fog layer with a clear pocket around the
    # car and every camera position. (A compositor Mist pass was measured
    # first: it is not denoised and put salt noise into every dark region,
    # residual 12.1 against 0.74 without it.)
    'haze_density': .0014,
    'fog_density': .0040,
    'fog_clearance': 1.5,
    # Rain falls (owner, 2026-09-17, after the close clip). The earlier
    # "vibrating" verdict came from 20-sample previews, not from the rain.
    # False leaves everything wet with nothing falling and no impact rings.
    'falling_rain': True,
    # When it rains: drop size and lit brightness against the physical values (a
    # true 1 mm drop is a third of a pixel wide at 1080p and vanishes against an
    # overcast sky), how far the rain reaches (the operator walks 11 m out; the
    # original field stopped at 7), and the depth of the rings drops leave in
    # standing water against the first, barely visible .26 mm.
    'rain_size': 2.3,
    'rain_reach': 1.7,
    'rain_backlight': 2.5,
    # Emission on airborne water: the only rain brightness the indirect clamp cannot cap.
    'rain_glow': 1.1,
    'ripple_depth': 5.0,
    # Ring reach and wavelength multiplier; depth scales with it so slopes hold.
    'ripple_scale': 1.0,
    # Drops swelling on the sills, bumper lips and mirrors and falling off.
    'drips': 70,
    # Multiplier on the 1.7 to 2.6 mm drip bead radius and on landing-ring height.
    'drip_size': 1.0,
    # Wind strength on trees, grass and loose leaves (wind.py); 0 is still air.
    'wind': 1.0,
    'wind_canopy': False,
    # Key and rim, as on a car shoot: a long softbox off camera draws a highlight
    # along the shoulder line and a cool edge light from behind lifts the dark
    # body off the trees. Light-linked to the car, so neither shows in the road.
    'strip_energy': 0.0,
    # Running lamps. The exported model carries flat emitters (white 11, pure red
    # 9.8) that sit below an overcast sky, so they read as painted lines. LEDs are
    # far brighter than their surroundings: at these strengths the tone curve burns
    # a pale core into the red bar and the bloom and wet road catch both. Colours
    # are a 6000 K daytime-running white and a deep LED red that is not pure, so it
    # can brighten toward orange-pink instead of clipping to flat red.
    'drl_emission': 240.0,
    'drl_color': (.80, .89, 1.0),
    'tail_emission': 95.0,
    'tail_color': (1.0, .030, .012),
    # Per setup, in the order of film_camera.SHOT_NAMES: the headlight macro looks
    # straight into the ring and keeps a fraction, so the optics stay readable.
    'lamp_per_shot': (1.0, 1.0, 1.0, .16, .55),
    'key_diffuse': .12,
    # The gaffer trims the rig for each setup (order of film_camera.SHOT_NAMES): from
    # behind, the edge light becomes a frontal key and needs far less; the macro
    # shots keep only a trace so lens and clearcoat detail survive.
    'key_per_shot': (1.0, .38, .65, .045, .30),
    # Shallow standing water under and around the parked car (height-field units).
    'car_apron': .12,
    # Scene-linear offset at black. Positive is lens veiling glare; negative
    # sets the black point just under the wet paint, as a colourist would.
    'veil': -.0015,
    'bloom': .09,
    # Film halation: a wide, warm, low-threshold glow around lamps and sky
    # edges. 0 removes the node.
    'halation': .05,
    # Cycles pixel-filter width in pixels. 1.5 is the razor-sharp CG default;
    # a real lens plus sensor resolves nearer 2, which also calms shimmer on
    # grilles, spokes and wet speculars.
    'filter_width': 1.95,
    # Slight barrel distortion of a real lens; the fit crops the edges back.
    'distortion': .006,
    # Sampling. Adaptive sampling stops a pixel once its error estimate drops
    # under this; whatever noise is left is reshaped by the denoiser, and a
    # different shape every frame is what reads as surfaces morphing.
    'adaptive_threshold': .025,
    # Cycles noise seed. The film keeps one fixed seed; the two-seed probe
    # (checks/claude-pass/seed_probe.py) renders one frame under two seeds and
    # reads their difference as the noise the denoiser could not settle.
    'seed': 20260915,
    # Seed for every random draw the scene build makes (rain columns, drip
    # emitters, tree siblings, wind gusts): spec.derive_seeds() fans it out.
    'scene_seed': 20260915,
    # False glues the noise pattern to the screen while surfaces slide under
    # it; True redraws it every frame, which the film grain then absorbs.
    'animated_seed': False,
    # Stability probes only. None leaves Blender's value alone (OpenImageDenoise,
    # accurate prefilter, albedo + normal guides); False / a name overrides it.
    'denoise': None,
    'denoiser': None,
    'denoise_prefilter': None,
    # CLI stability probe only: hold the camera at this film offset so any
    # frame-to-frame change on static surfaces is render instability.
    'freeze_camera': None,
    # CLI probe only: replace the film camera with a slow handheld move, for looking
    # at something the edit never frames. Metres from the car's centre on the road:
    # {'from': [x, y, z], 'to': [x, y, z], 'aim': [x, y, z], 'aim_to': [...], 'lens': 35, 'fstop': 2.8}
    'probe_camera': None,
    # Handheld drift of the probe camera, 1 = the 2026-09-17 clip the owner called far too shaky.
    'probe_shake': .25,
    # A photographer meters each setup. Stops added per shot, in the order of
    # film_camera.SHOT_NAMES; the wheel sits in the arch's shade.
    'shot_exposure': (-0.10, 0.25, 0.55, 0.30, 0.05),
    'wheel_reflector': 38.0,
    # The car was driven here. 0 turns a layer off; see road_weathering.py.
    'road_film': 1.0,
    'brake_dust': .9,
    # Practical hidden in the headliner so seats and wheel read through the
    # glass. Lights the car only; invisible to camera and to reflections.
    'cabin_fill': 7.0,
}


def configure(overrides):
    for key, value in (overrides or {}).items():
        if key not in LOOK:
            raise ValueError('Unknown look setting: ' + str(key))
        LOOK[key] = value


def constant_pigment(socket):
    """Read glTF's constant tint, including its vertex-color multiply wrapper."""
    if not socket.is_linked:
        return tuple(socket.default_value)
    node = socket.links[0].from_node
    if node.type == 'MIX' and node.data_type == 'RGBA' and node.blend_type == 'MULTIPLY':
        a = next(s for s in node.inputs if s.name == 'A' and s.type == 'RGBA')
        b = next(s for s in node.inputs if s.name == 'B' and s.type == 'RGBA')
        factor = node.inputs[0]
        if (not factor.is_linked and abs(factor.default_value - 1) < .0001
                and not b.is_linked and a.is_linked and a.links[0].from_node.type == 'VERTEX_COLOR'):
            return tuple(b.default_value)
    return None


def color_grade(tree, socket, saturation, value, label):
    """Keep upstream textures and color values editable behind a named grade."""
    node = tree.nodes.new('ShaderNodeHueSaturation')
    node.label = node.name = label
    node.inputs['Saturation'].default_value = saturation
    node.inputs['Value'].default_value = value
    if socket.is_linked:
        tree.links.new(socket.links[0].from_socket, node.inputs['Color'])
    else:
        node.inputs['Color'].default_value = socket.default_value
    tree.links.new(node.outputs['Color'], socket)
    return node


def car_materials(meshes, car_id, scale):
    """Only the inspected Manthey asset gets the requested finish overrides."""
    if car_id != MANTHEY_992:
        return []
    report = []
    mats = {m for obj in meshes for m in obj.data.materials if m and m.use_nodes}
    for mat in sorted(mats, key=lambda m: m.name):
        if mat.get('mv_rain_look'):
            continue
        shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if shader is None:
            continue
        name = mat.name.lower()
        category = None
        if name.startswith('mv-unified-paint') and shader.inputs['Coat Weight'].default_value > .5:
            color = shader.inputs['Base Color']
            pigment = constant_pigment(color)
            # Grade only the inspected bright Grello pigment. Custom panel maps
            # and other selected colors/finishes keep their authored appearance.
            metal = shader.inputs['Metallic']
            if (pigment and pigment[0] > .5 and pigment[1] > .5 and pigment[2] < .15
                    and not metal.is_linked and metal.default_value < .1):
                color_grade(mat.node_tree, color, .93, .65, 'Rain film — muted Grello pigment')
                texture = surface_detail.noise(mat.node_tree.nodes, mat.node_tree.links, scale, 4200)
                metallic = surface_detail.variation(mat.node_tree.nodes, mat.node_tree.links, texture, .025, .075)
                mat.node_tree.links.new(metallic, shader.inputs['Metallic'])
                set_input(shader, 'Roughness', .3)
                set_input(shader, 'Coat Weight', 1)
                category = 'muted-yellow-lacquer'
        elif name.split('.')[0] == 'manthey cap':
            # The bronze rear ring belongs to the aerodynamic wheel cover,
            # not the brake rotor. Neutralize its warm cast for this requested
            # black/yellow/red film palette while preserving all lettering.
            color_grade(mat.node_tree, shader.inputs['Base Color'], .08, .65, 'Rain film — neutral aero-cover accent')
            category = 'neutral-aero-cover-accent'
        elif name.startswith('mv-window-tint'):
            # This scene explicitly substitutes light tint for the snapshot's
            # opaque privacy treatment. Keep the stored pigment and opacity;
            # create a separately named thin-sheet optical surface.
            output = next((n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
            pigment = constant_pigment(shader.inputs['Base Color'])
            alpha, transmission = shader.inputs['Alpha'], shader.inputs['Transmission Weight']
            if (output and not output.inputs['Volume'].is_linked and pigment and max(pigment[:3]) < .01
                    and not alpha.is_linked and alpha.default_value > .999
                    and not transmission.is_linked and transmission.default_value < .001):
                optic = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
                optic.name = 'Rain film — lightly tinted window optics'
                optic.inputs['Base Color'].default_value = (.85, .88, .89, 1)
                optic.inputs['Transmission Weight'].default_value = 1
                optic.inputs['IOR'].default_value = 1.52
                mat.node_tree.links.new(optic.outputs[0], output.inputs['Surface'])
                surface_detail.thin_lens(optic)
                mix = next(n for n in mat.node_tree.nodes if n.type == 'MIX_SHADER')
                polarizer = mat.node_tree.nodes.new('ShaderNodeMath')
                polarizer.name = 'Rain film — window reflection control'
                polarizer.operation = 'MULTIPLY'
                polarizer.inputs[1].default_value = .42
                mat.node_tree.links.new(mix.inputs[0].links[0].from_socket, polarizer.inputs[0])
                mat.node_tree.links.new(polarizer.outputs[0], mix.inputs[0])
                category = 'lightly-tinted-window'
        elif name.split('.')[0] in ('matte plastic', 'glossy plastic', 'rims'):
            # No imported textures or aftermarket finishes are replaced.
            if not any(n.type == 'TEX_IMAGE' for n in mat.node_tree.nodes):
                if name.startswith('matte plastic'):
                    set_input(shader, 'Roughness', .58)
                    set_input(shader, 'Metallic', 0)
                    set_input(shader, 'Coat Weight', 0)
                    grain = surface_detail.noise(mat.node_tree.nodes, mat.node_tree.links, scale, 2200)
                    surface_detail.bump(shader, grain, .00004 * scale, .15)
                    category = 'satin-trim'
                elif name.startswith('glossy plastic'):
                    set_input(shader, 'Roughness', .28)
                    set_input(shader, 'Metallic', 0)
                    category = 'semi-gloss-trim'
                else:
                    set_input(shader, 'Roughness', .30)
                    category = 'satin-wheel-metal'
        if category:
            mat['mv_rain_look'] = category
            report.append({'material': mat.name, 'treatment': category})
    return report


def environment(scene, center, low, scale):
    """Overcast daylight: the photographed sky lights and reflects, haze
    separates the distance, and nothing in the rig pretends to be a studio."""
    if scene.get('mv_moody_rain'):
        return
    scene['mv_moody_rain'] = True
    background = scene.world.node_tree.nodes.get('Background')
    color_grade(scene.world.node_tree, background.inputs['Color'], LOOK['world_saturation'], 1,
                'Rain — slightly muted overcast illumination')
    for name in ('Rain — background photograph', 'Rain — projected distant park ground'):
        mat = bpy.data.materials[name]
        emission = next(n for n in mat.node_tree.nodes if n.type == 'EMISSION')
        color_grade(mat.node_tree, emission.inputs['Color'], LOOK['plate_saturation'], LOOK['plate_value'],
                    'Rain — muted distant foliage')
    # Grade the actual foliage as well as its photographed distant backdrop.
    foliage = {m for obj in scene.objects if obj.name.startswith(('Rain — detailed park tree', 'Rain — park grass tuft'))
               for m in obj.data.materials if m and m.use_nodes}
    for mat in foliage:
        shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if shader:
            color_grade(mat.node_tree, shader.inputs['Base Color'], LOOK['foliage_saturation'], LOOK['foliage_value'],
                        'Rain — subdued planted foliage')
    for obj in list(scene.objects):
        if obj.name.startswith('Rain — bench'):
            bpy.data.objects.remove(obj, do_unlink=True)

    origin = Vector((center.x, center.y, low.z))
    def area(name, xyz, aim, energy, width, height, color):
        data = bpy.data.lights.new(name, 'AREA')
        data.shape = 'RECTANGLE'
        data.energy = energy * scale * scale * LOOK['strip_energy']
        data.size, data.size_y = width * scale, height * scale
        data.color = color
        # The sky supplies the diffuse illumination. These only describe
        # panel curvature in the clearcoat reflection.
        data.diffuse_factor = LOOK['key_diffuse']
        data.volume_factor = .06
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = origin + Vector(xyz) * scale
        obj.rotation_euler = (origin + Vector(aim)*scale-obj.location).to_track_quat('-Z', 'Y').to_euler()
    if LOOK['strip_energy'] > 0:
        area('Rain — top front softbox', (1.3, -2.8, 4.5), (0, -.7, .65), 2200, 5, .72, (.96, .98, 1))
        area('Rain — long side reflection', (3.6, .1, 2.35), (0, .1, .75), 1750, 5.5, .62, (.90, .96, 1))
        area('Rain — rear edge light', (-2.8, 3.5, 3.2), (0, .8, .8), 1000, 4, .65, (.70, .85, 1))
    # A bounded, optically thin atmosphere. Against a bright sky it lifts the
    # distance toward light grey, which is what separates a black car from
    # dark trees in an overcast photograph.
    bpy.ops.mesh.primitive_cube_add(size=1, location=origin + Vector((0, 0, 6))*scale)
    haze = bpy.context.object
    haze.name = 'Rain — light courtyard haze'
    haze.scale = (70*scale, 70*scale, 14*scale)
    mat = bpy.data.materials.new('Rain — cool sparse haze')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    volume = nodes.new('ShaderNodeVolumeScatter')
    volume.inputs['Color'].default_value = (.80, .85, .9, 1)
    volume.inputs['Density'].default_value = LOOK['haze_density'] / scale
    volume.inputs['Anisotropy'].default_value = .25
    mat.node_tree.links.new(volume.outputs[0], out.inputs['Volume'])
    haze.data.materials.append(mat)


def link_reflections(scene, meshes):
    """Shape the car without reflecting the studio strips in the wet road."""
    receivers = bpy.data.collections.new('Rain — car reflection receivers')
    for obj in list(meshes) + [o for o in scene.objects if o.name.startswith(('Rain — surface water beads', 'Rain — molded sidewall lettering'))]:
        receivers.objects.link(obj)
    for name in ('Rain — top front softbox', 'Rain — long side reflection', 'Rain — rear edge light'):
        if name in scene.objects:
            scene.objects[name].light_linking.receiver_collection = receivers


def compositor(scene, scale=1.0):
    """Per-shot metering, black point, bloom and lens dispersion."""
    if not hasattr(scene, 'compositing_node_group'):
        return False  # Blender 4 retains the ungraded proof; renderer still works.
    tree = bpy.data.node_groups.new('Rain film — optical finishing', 'CompositorNodeTree')
    tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    scene.compositing_node_group = tree
    source = tree.nodes.new('CompositorNodeRLayers')
    source.scene = scene
    meter = tree.nodes.new('CompositorNodeExposure')
    meter.name = 'Rain film — per-shot metering'
    tree.links.new(source.outputs['Image'], meter.inputs['Image'])
    grade = tree.nodes.new('CompositorNodeColorBalance')
    grade.name = 'Rain film — cool shadow density'
    grade.inputs['Type'].default_value = 'Lift/Gamma/Gain'
    # Lift is a constant in scene-linear light. Above 1 it is lens veiling
    # glare; below 1 it pulls the black point down. LOOK['veil'] says which
    # and why. The slight blue-over-red split keeps shadows cool.
    veil = 1 + LOOK['veil']
    for name, color in [('Lift', (veil * .9992, veil, veil * 1.0010, 1)),
                        ('Gamma', (.997, 1.0, 1.004, 1)),
                        ('Gain', (1.0, 1.0, 1.0, 1))]:
        next(s for s in grade.inputs if s.name == name and s.type == 'RGBA').default_value = color
    glare = tree.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value = 'Fog Glow'
    glare.inputs['Quality'].default_value = 'High'
    glare.inputs['Threshold'].default_value = 2.5
    glare.inputs['Strength'].default_value = LOOK['bloom']
    glare.inputs['Size'].default_value = .2
    output = tree.nodes.new('NodeGroupOutput')
    lens = tree.nodes.new('CompositorNodeLensdist')
    lens.name = 'Rain film — restrained edge dispersion'
    lens.inputs['Distortion'].default_value = LOOK['distortion']
    lens.inputs['Dispersion'].default_value = .00035
    lens.inputs['Fit'].default_value = True
    tree.links.new(meter.outputs['Image'], grade.inputs['Image'])
    tree.links.new(grade.outputs['Image'], glare.inputs['Image'])
    tail = glare
    if LOOK['halation'] > 0:
        halo = tree.nodes.new('CompositorNodeGlare')
        halo.name = 'Rain film — warm halation'
        halo.inputs['Type'].default_value = 'Fog Glow'
        halo.inputs['Quality'].default_value = 'High'
        halo.inputs['Threshold'].default_value = 1.2
        halo.inputs['Strength'].default_value = LOOK['halation']
        halo.inputs['Size'].default_value = .45
        if 'Tint' in halo.inputs:
            halo.inputs['Tint'].default_value = (1.0, .58, .38, 1)
        tree.links.new(glare.outputs['Image'], halo.inputs['Image'])
        tail = halo
    scene.cycles.filter_width = LOOK['filter_width']
    tree.links.new(tail.outputs['Image'], lens.inputs['Image'])
    tree.links.new(lens.outputs['Image'], output.inputs['Image'])
    return True


def distance_fog(scene, center, low, scale):
    """Ground fog beyond a clear pocket that holds the car and every camera.

    Uniform fog cannot keep a car at ten metres crisp while fading a park at
    ninety. Real mornings do it with distance; this small court does it with
    a pocket. Homogeneous on both sides, so Cycles never ray-marches.
    """
    if LOOK['fog_density'] <= 0:
        return None
    radius = 8.0 * scale
    camera = scene.camera
    action = camera.animation_data.action if camera and camera.animation_data else None
    if action:
        if hasattr(action, 'layers'):
            curves = [curve for layer in action.layers for strip in layer.strips
                      for bag in strip.channelbags for curve in bag.fcurves]
        else:
            curves = list(action.fcurves)
        xs = next((c for c in curves if c.data_path == 'location' and c.array_index == 0), None)
        ys = next((c for c in curves if c.data_path == 'location' and c.array_index == 1), None)
        if xs and ys:
            for kx, ky in zip(xs.keyframe_points, ys.keyframe_points):
                radius = max(radius, ((kx.co[1] - center.x) ** 2 + (ky.co[1] - center.y) ** 2) ** .5)
    radius += LOOK['fog_clearance'] * scale
    origin = Vector((center.x, center.y, low.z))
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=60 * scale,
                                        location=origin + Vector((0, 0, 10)) * scale)
    pocket = bpy.context.object
    pocket.name = 'Rain — clear pocket cutter'
    pocket.hide_render = True
    pocket.display_type = 'WIRE'
    bpy.ops.mesh.primitive_cube_add(size=1, location=origin + Vector((0, 0, 6.5)) * scale)
    fog = bpy.context.object
    fog.name = 'Rain — distant ground fog'
    fog.scale = (260 * scale, 260 * scale, 15 * scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cut = fog.modifiers.new('Clear pocket around car and cameras', 'BOOLEAN')
    cut.operation = 'DIFFERENCE'
    cut.solver = 'EXACT'
    cut.object = pocket
    mat = bpy.data.materials.new('Rain — distant ground fog')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    volume = nodes.new('ShaderNodeVolumeScatter')
    volume.inputs['Color'].default_value = (.80, .85, .9, 1)
    volume.inputs['Density'].default_value = LOOK['fog_density'] / scale
    volume.inputs['Anisotropy'].default_value = .35
    mat.node_tree.links.new(volume.outputs[0], out.inputs['Volume'])
    fog.data.materials.append(mat)
    fog['pocket_radius_m'] = radius / scale
    return fog


def lamps(meshes):
    """Give the exported lamp emitters LED brightness and colour. Returns the shaders."""
    found = []
    for obj in meshes:
        name = obj.name.lower()
        kind = 'drl' if name.startswith('drl-') else 'tail' if 'tail-light-bar' in name else None
        if not kind:
            continue
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes or mat.get('mv_lamp'):
                continue
            shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if shader is None or shader.inputs['Emission Strength'].default_value <= 0:
                continue
            mat['mv_lamp'] = kind
            shader.inputs['Emission Color'].default_value = (*LOOK[kind + '_color'], 1)
            shader.inputs['Emission Strength'].default_value = LOOK[kind + '_emission']
            found.append((kind, mat, shader))
    return found


def switch_off_lamps(meshes):
    """Orbit scenes keep the exported emitters as they are; a spec can only
    switch a kind off (emission 0). Returns the kinds switched off."""
    off = []
    for obj in meshes:
        name = obj.name.lower()
        kind = 'drl' if name.startswith('drl-') else 'tail' if 'tail-light-bar' in name else None
        if not kind or LOOK[kind + '_emission'] > 0:
            continue
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if shader is None:
                continue
            shader.inputs['Emission Strength'].default_value = 0
            if kind not in off:
                off.append(kind)
    return off


def animate_lamps(scene, first, total):
    """Trim the lamps per setup, switching in the closed-shutter gap like the rig."""
    count = 0
    for mat in bpy.data.materials:
        kind = mat.get('mv_lamp') if mat.use_nodes else None
        if not kind:
            continue
        shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        socket = shader.inputs['Emission Strength']
        for offset in range(total):
            index, _ = film_camera.shot_at(offset, total)
            socket.default_value = LOOK[kind + '_emission'] * LOOK['lamp_per_shot'][index]
            if offset and film_camera.shot_at(offset-1, total)[0] != index:
                socket.keyframe_insert(data_path='default_value', frame=first + offset - .5)
            socket.keyframe_insert(data_path='default_value', frame=first + offset)
        _constant_keys(mat.node_tree)
        count += 1
    return count


def _constant_keys(owner):
    action = owner.animation_data.action
    if hasattr(action, 'layers'):
        curves = [curve for layer in action.layers for strip in layer.strips
                  for bag in strip.channelbags for curve in bag.fcurves]
    else:
        curves = action.fcurves
    for curve in curves:
        for key in curve.keyframe_points:
            key.interpolation = 'CONSTANT'


def wheel_reflector(scene, meshes, center, extent, low, scale):
    """A reflector board beside the wheel setup, as on a real shoot.

    It exists only during the wheel shot and only lights the car, so the wet
    road never shows a floating rectangle.
    """
    if LOOK['wheel_reflector'] <= 0:
        return None
    anchor = film_camera.anchors(meshes, center, extent, low)['wheel']
    data = bpy.data.lights.new('Rain — wheel reflector board', 'AREA')
    data.shape = 'RECTANGLE'
    data.size, data.size_y = 1.7 * scale, 1.1 * scale
    data.energy = LOOK['wheel_reflector'] * scale * scale
    data.color = (.97, .985, 1)
    data.specular_factor = .45
    data.volume_factor = 0
    board = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(board)
    board.location = anchor + Vector((2.0, 1.15, .05)) * scale
    board.rotation_euler = (anchor - board.location).to_track_quat('-Z', 'Y').to_euler()
    receivers = bpy.data.collections.get('Rain — car reflection receivers')
    if receivers:
        board.light_linking.receiver_collection = receivers
    return board


def cabin_fill(scene, center, extent, low, scale):
    if LOOK['cabin_fill'] <= 0:
        return None
    data = bpy.data.lights.new('Rain — cabin practical', 'AREA')
    data.shape = 'RECTANGLE'
    data.size, data.size_y = .8 * scale, .6 * scale
    data.energy = LOOK['cabin_fill'] * scale * scale
    data.color = (1, .96, .90)
    data.volume_factor = 0
    lamp = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(lamp)
    lamp.location = Vector((center.x, center.y + extent.y * .04, low.z + extent.z * .80))
    lamp.visible_camera = False
    lamp.visible_glossy = False
    lamp.visible_transmission = False
    receivers = bpy.data.collections.get('Rain — car reflection receivers')
    if receivers:
        lamp.light_linking.receiver_collection = receivers
    return lamp


def animate_exposure(scene, first, total):
    """Meter each shot separately; the change lands exactly on the cut."""
    tree = getattr(scene, 'compositing_node_group', None)
    meter = tree.nodes.get('Rain film — per-shot metering') if tree else None
    board = scene.objects.get('Rain — wheel reflector board')
    energy = board.data.energy if board else 0
    for offset in range(total):
        index, _ = film_camera.shot_at(offset, total)
        if meter:
            socket = meter.inputs['Exposure']
            socket.default_value = LOOK['shot_exposure'][index]
            socket.keyframe_insert(data_path='default_value', frame=first + offset)
        if board:
            board.data.energy = energy if index == 2 else 0
            if offset and film_camera.shot_at(offset-1, total)[0] != index:
                board.data.keyframe_insert(data_path='energy', frame=first + offset - .5)
            board.data.keyframe_insert(data_path='energy', frame=first + offset)
    if meter:
        _constant_keys(tree)
    if board:
        _constant_keys(board.data)


def animate_reflections(scene, first, total):
    """Relight close-ups without blowing out the lens and clearcoat detail.

    Constant keys keep the adjustment at editorial cuts, never mid-shot.
    """
    for name in ('Rain — top front softbox', 'Rain — long side reflection', 'Rain — rear edge light'):
        light = scene.objects.get(name)
        if not light:
            continue
        data = light.data
        energy = data.energy
        for offset in range(total):
            index, _ = film_camera.shot_at(offset, total)
            data.energy = energy * LOOK['key_per_shot'][index]
            if offset and film_camera.shot_at(offset-1, total)[0] != index:
                # Relight in the closed-shutter interval between shots, so
                # incoming exposure never includes the outgoing light level.
                data.keyframe_insert(data_path='energy', frame=first + offset - .5)
            data.keyframe_insert(data_path='energy', frame=first + offset)
        action = data.animation_data.action
        if hasattr(action, 'layers'):
            curves = [curve for layer in action.layers for strip in layer.strips
                      for bag in strip.channelbags for curve in bag.fcurves]
        else:
            curves = action.fcurves
        for curve in curves:
            for key in curve.keyframe_points:
                key.interpolation = 'CONSTANT'
