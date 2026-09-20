"""Shared-mesh instances of checksum-verified CC0 foliage, loaded offline."""
import math
import os
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ASSETS = Path(os.environ.get('RENDER_STUDIO_ASSETS') or Path(__file__).resolve().parent / 'assets')


def prototypes(asset):
    path = ASSETS / asset / (asset + '_1k.gltf')
    if not path.is_file():
        raise RuntimeError('Rain scene foliage missing. Run tools/render-studio/prepare_assets.py once.')
    previous = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    imported = set(bpy.data.objects) - previous
    result = []
    for obj in sorted(imported, key=lambda o: o.name):
        if obj.type != 'MESH':
            continue
        mesh = obj.data.copy()
        mesh.transform(obj.matrix_world)
        low = Vector(tuple(min(v.co[i] for v in mesh.vertices) for i in range(3)))
        high = Vector(tuple(max(v.co[i] for v in mesh.vertices) for i in range(3)))
        center = (low + high) / 2
        mesh.transform(Matrix.Translation((-center.x, -center.y, -low.z)))
        result.append((mesh, max(0.01, high.z-low.z)))
        for mat in mesh.materials:
            if not mat or not mat.use_nodes:
                continue
            shader = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if shader:
                shader.inputs['Specular IOR Level'].default_value = 0.25
                shader.inputs['Roughness'].default_value = 0.6
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    return result


def shape_variants(prototype, count=4, seed=20260919):
    """Siblings of the one scanned tree: same species, clearly different individuals.

    Bark, leaves and twig detail are kept; the architecture is regrown. Each
    sibling gets its own bole height, an S-curved leaning trunk, a crown twisted
    round the trunk, spread far wider one way than the other, stretched tall or
    pressed flat, and a slow three-dimensional warp that pushes whole limbs in
    different directions so no two silhouettes share an outline. Everything
    fades to zero at the root flare, so every tree still stands on its base.
    """
    import random
    import numpy as np
    mesh, height = prototype
    rng = random.Random(seed)
    result = [prototype]
    for number in range(count):
        copy = mesh.copy()
        copy.name = mesh.name + ' — sibling %d' % (number + 1)
        co = np.empty(len(copy.vertices) * 3, dtype=np.float32)
        copy.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3).astype(np.float64)
        h = np.clip(co[:, 2] / height, 0, 1)
        crown = np.clip((h - .22) / .33, 0, 1)
        crown = crown * crown * (3 - 2 * crown)
        # Whole limbs pushed around: a smooth vector field, wavelength about half the tree.
        warp = np.zeros_like(co)
        for _ in range(4):
            k = np.array([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, .7)])
            k *= rng.uniform(1.6, 3.2) * 2 * np.pi / height / np.linalg.norm(k)
            push = np.array([rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, .45)])
            push *= rng.uniform(.035, .075) * height / np.linalg.norm(push)
            warp += np.sin(co @ k + rng.uniform(0, 6.283))[:, None] * push
        co += warp * crown[:, None]
        twist = rng.choice((-1, 1)) * rng.uniform(.5, 1.7) * crown
        cos, sin = np.cos(twist), np.sin(twist)
        x, y = co[:, 0] * cos - co[:, 1] * sin, co[:, 0] * sin + co[:, 1] * cos
        direction = rng.uniform(0, 6.283)
        wide, narrow = rng.uniform(1.10, 1.55), rng.uniform(.62, .95)
        ax, ay = np.cos(direction), np.sin(direction)
        along, across = x * ax + y * ay, -x * ay + y * ax
        # Lopsided as well as oval: one side of the crown reaches farther.
        along = along * (1 + (wide - 1) * crown) + rng.uniform(.0, .10) * height * crown
        across *= 1 + (narrow - 1) * crown
        x, y = along * ax - across * ay, along * ay + across * ax
        lean_direction, counter = rng.uniform(0, 6.283), rng.uniform(0, 6.283)
        lean = rng.uniform(.05, .16) * height * h * h
        bow = rng.uniform(.02, .06) * height * np.sin(np.pi * np.clip(h / .55, 0, 1))      # S-curve low in the trunk
        co[:, 0] = x + np.cos(lean_direction) * lean + np.cos(counter) * bow
        co[:, 1] = y + np.sin(lean_direction) * lean + np.sin(counter) * bow
        # Bole height and crown depth change separately.
        bole, depth = rng.uniform(.80, 1.30), rng.uniform(.78, 1.30)
        z = co[:, 2]
        split = .30 * height
        co[:, 2] = np.where(z < split, z * bole, split * bole + (z - split) * depth)
        copy.vertices.foreach_set('co', co.astype(np.float32).ravel())
        copy.update()
        result.append((copy, float(co[:, 2].max())))
    return result


def instance(prototype, name, position, height, angle):
    mesh, original_height = prototype
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler[2] = angle
    obj.scale = (height / original_height,) * 3
    return obj


def plant_tree(prototype, position, height, rng):
    if isinstance(prototype, list):
        # Dealt in turn without touching the scene's random sequence.
        plant_tree.planted = getattr(plant_tree, 'planted', -1) + 1
        prototype = prototype[(plant_tree.planted * 2 + 1) % len(prototype)]      # neighbours never share a shape
    return instance(prototype, 'Rain — detailed park tree', position, height, rng.random() * math.tau)


def plant_grass(prototypes, origin, scale, rng):
    for _ in range(1800):
        # Dense near the curb, wider and sparser farther out. All instances
        # reuse the source mesh BVH, so texture/geometry memory stays bounded.
        x = rng.choice((-1, 1)) * (5.1 + rng.random() ** 1.8 * 22)
        y = rng.uniform(-32, 32)
        position = origin + Vector((x, y, -0.014)) * scale
        instance(rng.choice(prototypes), 'Rain — park grass tuft', position,
                 rng.uniform(0.16, 0.30) * scale, rng.random() * math.tau)


def plant_depth_layers(prototype, origin, scale, rng):
    """Mid-ground and far tree belts, so the park recedes in steps.

    The eight court trees end at 7.5 m and the photographed dome starts at
    infinity; with nothing between, a walking camera gets no parallax behind
    the car and fog has nothing to grade. Three loose belts on every side,
    thinning and growing with distance. Instances share one mesh.
    """
    count = 0
    for near, far, spacing, low, high in ((14, 21, 8.0, 4.5, 8.5), (25, 34, 8.0, 7.0, 11.5), (40, 54, 9.0, 9.0, 14.0)):
        reach = far + 6
        along = -reach
        while along < reach:
            along += spacing * rng.uniform(.55, 1.5)
            for side in (-1, 1):
                if rng.random() < .22:
                    continue                                   # gaps: a belt, not a fence
                depth = rng.uniform(near, far)
                # Side belts run along the court; end belts close the view down its length.
                for x, y in ((side * depth, along), (along * .8, side * (depth + 8))):
                    if abs(x) < 12 and abs(y) < 18:
                        continue
                    position = origin + Vector((x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5), -0.02)) * scale
                    tree = instance(rng.choice(prototype) if isinstance(prototype, list) else prototype, 'Rain — park tree belt', position, rng.uniform(low, high) * scale, rng.random() * math.tau)
                    # One scanned tree: spread and lean differ so the belt is not a row of clones.
                    tree.scale.x *= rng.uniform(.8, 1.3) * rng.choice((-1, 1))      # mirrored trees are free variety
                    tree.scale.y *= rng.uniform(.8, 1.3)
                    tree.rotation_euler[0] = rng.uniform(-.06, .06)
                    tree.rotation_euler[1] = rng.uniform(-.06, .06)
                    count += 1
    return count


def plant_foreground_grass(prototypes, origin, scale, rng):
    """Uncut verge grass between the walker and the car, camera side only.

    Knee-high and close to the lens, so it crosses the bottom of the wide
    shots out of focus and moves faster than anything else in frame. Kept out
    of the two tree beds and off the operator's route.
    """
    count = 0
    for _ in range(260):
        x = 5.15 + rng.random() ** 1.6 * 2.6
        y = rng.uniform(-11.5, 1.5)
        if 4.7 < x < 6.7 and (-8.4 < y < -5.6 or -2.4 < y < .4):
            continue                                           # tree beds
        if x > 6.6 and -9.0 < y < -5.0:
            continue                                           # where the operator walks in
        if x < 6.2 and -5.6 < y < -3.6:
            continue                                           # where they step over the curb
        position = origin + Vector((x, y, -0.014)) * scale
        instance(rng.choice(prototypes), 'Rain — verge grass', position, rng.uniform(.42, .85) * scale, rng.random() * math.tau)
        count += 1
    return count

