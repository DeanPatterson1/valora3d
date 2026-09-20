"""Bake the actual puddle/ripple shader fields through Cycles and measure them.

The road's water graph reads scanned image textures, which Geometry Nodes
fields cannot evaluate, so nothing is re-implemented here. A socket of the real
wet_asphalt() graph is routed into an emission shader on a ground plane and
photographed top-down by an orthographic camera: CPU, one sample at the pixel
centre, no denoise, 32-bit linear EXR. The harness first bakes world position
and must read every pixel centre back, so "pixel = value" is measured.

This checks pool coverage, coherent pools, soft but stone-broken shorelines,
fixed pool placement, optically flat standing water and localized temporal
ripples, not just node links.

blender -b --factory-startup --python-exit-code 1 --python check_puddle_fields.py
Renders a few small CPU frames into a temporary directory. No GPU, no scene file.
"""
from pathlib import Path
import sys
import tempfile

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rain_scene
from rain_scene import wet_asphalt

# Court foreground and both sides of the car at 2.5 cm per pixel, then the
# whole 14 x 32 m court at 5 cm per pixel. Metres, scale 1.
WINDOW, SIZE = (-4.8, -6.0, 4.8, 6.0), (384, 480)
COURT, COURT_SIZE = (-7, -16, 7, 16), (280, 640)
CLOSE = 512  # pixels across a 1 mm per pixel shoreline window


def harness(material, folder):
    """Return bake(socket, window, size, seconds, span) for one material."""
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=1)
    ground = bpy.context.object
    ground.scale = (40, 40, 1)
    ground.data.materials.append(material)
    data = bpy.data.cameras.new('Puddle field bake camera')
    data.type = 'ORTHO'
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    cycles = scene.cycles
    cycles.device = 'CPU'
    cycles.samples = 1
    cycles.use_denoising = cycles.use_adaptive_sampling = False
    cycles.pixel_filter_type = 'BOX'
    cycles.max_bounces = 0
    cycles.seed = 0
    cycles.use_animated_seed = False
    scene.render.use_motion_blur = False
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    settings = scene.render.image_settings
    settings.file_format, settings.color_mode, settings.color_depth = 'OPEN_EXR', 'RGB', '32'
    nodes, links = material.node_tree.nodes, material.node_tree.links
    output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output)
    emission = nodes.new('ShaderNodeEmission')
    links.new(emission.outputs[0], output.inputs['Surface'])
    encoder = nodes.new('ShaderNodeMath')
    encoder.operation = 'MULTIPLY_ADD'
    encoder.inputs[2].default_value = .5
    links.new(encoder.outputs[0], emission.inputs['Color'])

    def bake(socket, window, size, seconds=0.0, span=1.0):
        """Field values at pixel centres; row 0 is the window's low-y edge.

        A value within +/- span travels as .5 + value / (2 span): a renderer
        has no obligation to keep negative radiance.
        """
        nodes['Rain impact time seconds'].outputs[0].default_value = seconds
        links.new(socket, encoder.inputs[0])
        encoder.inputs[1].default_value = .5 / span
        camera.location = ((window[0] + window[2]) / 2, (window[1] + window[3]) / 2, 10)
        data.ortho_scale = max(window[2] - window[0], window[3] - window[1])
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.filepath = str(Path(folder) / 'field.exr')
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = np.empty(size[0] * size[1] * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        bpy.data.images.remove(image)
        return (pixels.reshape(size[1], size[0], 4)[:, :, 0].astype(np.float64) - .5) * 2 * span

    return bake


def crossings(mask):
    """Pixel edges that the shoreline passes through."""
    wet = mask > .5
    return int((wet[:, 1:] != wet[:, :-1]).sum() + (wet[1:, :] != wet[:-1, :]).sum())


def pool_areas(core, pixel):
    """Areas in m2 of the 4-connected regions, largest first."""
    height, width = core.shape
    remaining = {int(index) for index in np.flatnonzero(core)}
    areas = []
    while remaining:
        stack = [remaining.pop()]
        size = 0
        while stack:
            index = stack.pop()
            size += 1
            x, y = index % width, index // width
            neighbors = ([index - 1] if x else []) + ([index + 1] if x < width - 1 else [])
            neighbors += ([index - width] if y else []) + ([index + width] if y < height - 1 else [])
            for neighbor in neighbors:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        areas.append(size * pixel * pixel)
    return sorted(areas, reverse=True)


def measure(material, bake):
    nodes, links = material.node_tree.nodes, material.node_tree.links
    pixel = (WINDOW[2] - WINDOW[0]) / SIZE[0]

    # The harness must return world position at every pixel centre before any
    # other number it produces is believed. Measured error .0006 pixel.
    position = nodes.new('ShaderNodeNewGeometry')
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs['Position'], separate.inputs[0])
    for axis, name in enumerate('XY'):
        centres = WINDOW[axis] + (np.arange(SIZE[axis]) + .5) * pixel
        expected = centres[None, :] if axis == 0 else centres[:, None]
        error = np.abs(bake(separate.outputs[name], WINDOW, SIZE, span=24) - expected).max() / pixel
        print('BAKED FIELD: world', name, 'read back within', error, 'pixel', flush=True)
        assert error < .01, ('The bake does not sample pixel centres', name, error)

    mask_socket = nodes['Soft puddle to damp asphalt transition'].outputs[0]
    mask = bake(mask_socket, WINDOW, SIZE)
    assert mask.min() >= 0 and mask.max() <= 1
    assert np.array_equal(mask, bake(mask_socket, WINDOW, SIZE, seconds=.6)), 'Impact ripples must not move the pools'
    core, damp = float((mask >= .95).mean()), float((mask <= .05).mean())
    court = float((bake(mask_socket, COURT, COURT_SIZE) > .5).mean())
    print('BAKED FIELD: window core/damp fractions', core, damp, 'flooded share of the whole court', court, flush=True)
    # rain_scene.PUDDLE_LEVEL is set to flood "roughly a third of the court":
    # measured .310. Around the car it is .206 core under .740 of plain film.
    assert .20 < court < .45, ('Standing water should cover about a third of the court', court)
    assert .10 < core < .40, ('Water needs actual, localized pool cores', core)
    assert damp > .50, ('Most of the road carries a film, not a vague gradient', damp)
    areas = pool_areas(mask >= .95, pixel)
    print('BAKED FIELD: coherent pool areas m2', [round(area, 3) for area in areas[:12]],
          'of', len(areas), 'wet regions', flush=True)
    # Measured 13.6 m2 and seven pools of half a square metre or more.
    assert areas[0] > 3 and sum(area >= .5 for area in areas) <= 12

    # Shorelines, at the millimetre the scanned relief resolves. Eight windows
    # on the most evenly mixed half-metre blocks.
    block = 20
    mixed = sorted((abs(float((mask[j:j + block, i:i + block] > .5).mean()) - .5), j, i)
                   for j in range(0, SIZE[1] - block + 1, block)
                   for i in range(0, SIZE[0] - block + 1, block))[:8]
    assert mixed[-1][0] < .25, ('Too few shorelines inside the window', mixed)
    half = CLOSE * .001 / 2
    windows = [(WINDOW[0] + (i + block / 2) * pixel - half, WINDOW[1] + (j + block / 2) * pixel - half,
                WINDOW[0] + (i + block / 2) * pixel + half, WINDOW[1] + (j + block / 2) * pixel + half)
               for _, j, i in mixed]
    shores = [bake(mask_socket, window, (CLOSE, CLOSE)) for window in windows]
    steps = [np.concatenate([np.abs(np.diff(shore, axis=1)).ravel(), np.abs(np.diff(shore, axis=0)).ravel()])
             for shore in shores]
    sharpest = max(float(step.max()) for step in steps)
    busiest = max(float(np.percentile(step, 99)) for step in steps)
    banks = float(np.mean([((shore > .05) & (shore < .95)).mean() for shore in shores]))
    print('BAKED FIELD: over 1 mm the mask changes by at most', sharpest, 'worst 99th percentile', busiest,
          'bank share of the shoreline windows', banks, flush=True)
    # Measured over sixteen windows: .35 to .60, .09 to .19, and .29 mean. A
    # hard threshold reads 1.0 and leaves almost no bank.
    assert sharpest < .8 and busiest < .30, 'Puddle banks change too sharply'
    assert banks > .10, ('Banks need a resolved soft transition', banks)

    # The same windows with the scanned relief flattened to its mean, which is
    # exactly the plain noise threshold the shoreline must not be.
    relief = next(node for node in nodes if node.type == 'TEX_IMAGE' and node.image
                  and 'Displacement' in node.image.name)
    consumers = [link.to_socket for link in relief.outputs['Color'].links]
    texels = np.empty(len(relief.image.pixels), dtype=np.float32)
    relief.image.pixels.foreach_get(texels)
    for link in list(relief.outputs['Color'].links):
        links.remove(link)
    for socket in consumers:
        socket.default_value = float(texels[0::4].mean())
    plain = [crossings(bake(mask_socket, window, (CLOSE, CLOSE))) for window in windows]
    for socket in consumers:
        links.new(relief.outputs['Color'], socket)
    assert np.array_equal(mask, bake(mask_socket, WINDOW, SIZE)), 'The scanned relief was not restored'
    broken = [crossings(shore) for shore in shores]
    print('BAKED FIELD: shoreline crossings with scanned relief', broken, 'as plain noise', plain,
          'ratio', sum(broken) / max(1, sum(plain)), flush=True)
    # Measured 6.3 times the crossings overall, never under 2.6 in a window.
    assert min(plain) > 0 and sum(broken) > 3 * sum(plain), 'The shoreline is a plain noise threshold'
    assert all(real > 1.5 * flat for real, flat in zip(broken, plain))

    # Ripples, at 2 mm per pixel over the most flooded 2 m block: their
    # wavelength is 27 mm, which the 2.5 cm grid above would alias.
    block = 80
    flooded = max((float((mask[j:j + block, i:i + block] >= .95).mean()), -j, -i)  # ties: lowest j, i
                  for j in range(0, SIZE[1] - block + 1, 8) for i in range(0, SIZE[0] - block + 1, 8))
    centre = (WINDOW[0] + (block / 2 - flooded[2]) * pixel, WINDOW[1] + (block / 2 - flooded[1]) * pixel)
    close = (centre[0] - 1.024, centre[1] - 1.024, centre[0] + 1.024, centre[1] + 1.024)
    bump = nodes['Localized shallow-water ripple normal']
    height_socket = bump.inputs['Height'].links[0].from_socket
    relief_scale = bump.inputs['Distance'].default_value * bump.inputs['Strength'].default_value
    early, late = (bake(height_socket, close, (1024, 1024), seconds) for seconds in (0, .6))
    height_delta = float(np.abs(early - late).max()) * relief_scale
    slopes = [np.gradient(height * relief_scale, .002) for height in (early, late)]
    normal_delta = float(np.hypot(slopes[0][0] - slopes[1][0], slopes[0][1] - slopes[1][1]).max())
    print('BAKED FIELD: maximum changing ripple relief metres', height_delta,
          'maximum changing normal slope', normal_delta, flush=True)
    # Measured 3.6e-05 m and .0124.
    assert height_delta > .000004, 'Ripple height is static or vanishingly small'
    assert .002 < normal_delta < .1, 'Ripple normal must change visibly but stay shallow'
    fields = [(bake(mask_socket, close, (1024, 1024)), (early, late)),
              (mask, [bake(height_socket, WINDOW, SIZE, seconds) for seconds in (0, .6)])]
    for wet, heights in fields:
        dry = wet == 0
        rings = max(float(np.abs(height[wet > 0]).max()) for height in heights)
        stray = max(float(np.abs(height[dry]).max()) for height in heights)
        print('BAKED FIELD: ripple height reaches', rings, 'in water and', stray, 'over',
              int(dry.sum()), 'pixels without standing water', flush=True)
        assert dry.sum() > 1000 and rings > .05 and stray < 1e-6, 'Ripples must stay inside the pools'

    # The water optics those fields drive, read from the shader's own inputs.
    shader = nodes['Principled BSDF']
    film_normal = bump.inputs['Normal'].links[0].from_node
    weight, roughness, relief_strength = (
        bake(socket.links[0].from_socket, WINDOW, SIZE) for socket in
        (shader.inputs['Coat Weight'], shader.inputs['Coat Roughness'], film_normal.inputs['Strength']))
    pooled, dry = mask == 1, mask == 0
    print('BAKED FIELD: coat weight/roughness/film relief in', int(pooled.sum()), 'pool pixels',
          weight[pooled].min(), roughness[pooled].max(), relief_strength[pooled].max(),
          'and film weight range over', int(dry.sum()), 'film pixels', weight[dry].min(), weight[dry].max(),
          'roughness from', roughness[dry].min(), flush=True)
    assert pooled.sum() > 1000 and dry.sum() > 1000
    assert weight[pooled].min() > 1 - 1e-6 and roughness[pooled].max() <= .005 and relief_strength[pooled].max() <= .005
    assert .62 - 1e-6 <= weight[dry].min() and weight[dry].max() <= .88 + 1e-6
    # The broken film is never as smooth as standing water: (.07 x .55) + .004.
    assert roughness[dry].min() > .04


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert (rain_scene.ASSETS / 'asphalt_02_Displacement_2k.exr').is_file(), \
        'Scanned relief missing: run prepare_assets.py, or shorelines fall back to plain noise'
    material = wet_asphalt(1)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        measure(material, harness(material, folder))
    print('PASS: baked pool coverage and cores, soft stone-broken shorelines, fixed pool placement,',
          'optically flat standing water under a 0.62–0.88 film, localized temporal ripple height/normals')


if __name__ == '__main__':
    main()
