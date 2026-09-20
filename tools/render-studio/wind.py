"""Wind for the courtyard: one gust field, everything answers it differently.

A gust is a travelling front, so the far belt moves before the near trees and
the leaves on the road stir last. Trees and grass rock about their roots on
their own natural frequency, the eight court trees also get canopy flutter
(a displace modifier weighted to the crown), and a handful of loose leaves
tremble and now and then skitter downwind. Everything is keyed per frame from
closed-form functions: deterministic, continuous across the open shutter.
"""
import math
import random

import bpy
import numpy as np

DIRECTION = (.55, .835)          # unit vector the wind blows toward, car space
FRONT_SPEED = 7.0                # m/s, how fast a gust crosses the park


def gust(seconds, x, y, scale=1.0):
    """Wind strength 0..~1.3 at a place and time."""
    s = seconds - (x * DIRECTION[0] + y * DIRECTION[1]) / (FRONT_SPEED * scale)
    value = .50 + .30*math.sin(.83*s + .4) + .20*math.sin(1.91*s + 1.7) + .12*math.sin(3.67*s + .2) + .07*math.sin(6.1*s + 2.9)
    return max(0.0, value)


def _curve(datablock, path, index, frames, values):
    if datablock.animation_data is None:
        datablock.animation_data_create()
    if datablock.animation_data.action is None:
        datablock.animation_data.action = bpy.data.actions.new('Wind — ' + datablock.name)
    curve = datablock.animation_data.action.fcurve_ensure_for_datablock(datablock, path, index=index)
    curve.keyframe_points.clear()
    curve.keyframe_points.add(len(frames))
    flat = np.empty(len(frames) * 2, dtype=np.float32)
    flat[0::2] = frames
    flat[1::2] = values
    curve.keyframe_points.foreach_set('co', flat)
    curve.keyframe_points.foreach_set('interpolation', [1] * len(frames))      # linear
    curve.update()


def _rock(obj, frames, times, scale, rng, lean, swing, natural):
    """Rigid sway about the root, in the wind direction, local to the object's spin."""
    x, y = obj.location.x / scale, obj.location.y / scale
    omega, phase, cross = rng.uniform(*natural), rng.uniform(0, math.tau), rng.uniform(-.35, .35)
    spin = obj.rotation_euler[2]
    rest = (obj.rotation_euler[0], obj.rotation_euler[1])
    tilt_x, tilt_y = [], []
    for t in times:
        g = gust(t, x, y)
        along = math.radians(lean) * g + math.radians(swing) * g * math.sin(omega * t + phase)
        across = math.radians(swing) * cross * g * math.sin(omega * .77 * t + phase * 1.9)
        # Tilting toward (dx, dy) is a rotation about the horizontal axis at right angles to it.
        wx = -(along * DIRECTION[1] + across * DIRECTION[0])
        wy = along * DIRECTION[0] - across * DIRECTION[1]
        tilt_x.append(rest[0] + wx * math.cos(spin) + wy * math.sin(spin))
        tilt_y.append(rest[1] - wx * math.sin(spin) + wy * math.cos(spin))
    _curve(obj, 'rotation_euler', 0, frames, tilt_x)
    _curve(obj, 'rotation_euler', 1, frames, tilt_y)


def _crown_weights(mesh):
    """0 on the trunk, 1 out in the crown; stored once on the shared mesh."""
    count = len(mesh.vertices)
    co = np.empty(count * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    height = float(co[:, 2].max())
    rise = np.clip((co[:, 2] / height - .30) / .30, 0, 1)
    reach = np.clip(np.hypot(co[:, 0], co[:, 1]) / (.10 * height), 0, 1)
    return rise * rise * (3 - 2 * rise) * reach


def _flutter(trees, frames, times, scale, strength):
    if not trees:
        return 0
    texture = bpy.data.textures.new('Wind — canopy turbulence', 'CLOUDS')
    texture.noise_scale = 1.1 * scale
    texture.noise_depth = 1
    texture.cloud_type = 'COLOR'
    carrier = bpy.data.objects.new('Wind — turbulence carrier', None)
    bpy.context.collection.objects.link(carrier)
    carrier.hide_render = True
    # The turbulence blows through the crowns; it is not attached to them.
    for axis in range(2):
        _curve(carrier, 'location', axis, frames, [-DIRECTION[axis] * 1.6 * scale * t for t in times])
    _curve(carrier, 'location', 2, frames, [.35 * scale * math.sin(.9 * t) for t in times])
    weighted = set()
    for tree in trees:
        group = tree.vertex_groups.new(name='Wind crown')
        if tree.data.name not in weighted:                  # weights live on the mesh, shared by its instances
            weighted.add(tree.data.name)
            weights = _crown_weights(tree.data)
            for level in range(1, 11):
                chosen = np.nonzero(np.round(weights * 10) == level)[0]
                if len(chosen):
                    group.add(chosen.tolist(), level / 10, 'REPLACE')
        modifier = tree.modifiers.new('Wind — canopy flutter', 'DISPLACE')
        modifier.texture = texture
        modifier.texture_coords = 'OBJECT'
        modifier.texture_coords_object = carrier
        modifier.direction = 'RGB_TO_XYZ'
        modifier.space = 'GLOBAL'
        modifier.mid_level = .5
        modifier.vertex_group = 'Wind crown'
        # Flutter moves leaves millimetres per frame; blurring it would triple each tree's memory.
        tree.cycles.use_deform_motion = False
        x, y = tree.location.x / scale, tree.location.y / scale
        # Modifier strength is in object space; the tree object is scaled up from the scan.
        unit = strength * .085 * scale / max(1e-6, tree.scale.z)
        _curve(tree, 'modifiers["Wind — canopy flutter"].strength', 0, frames, [unit * (.25 + gust(t, x, y)) for t in times])
    return len(trees)


def _leaves(leaves, frames, times, scale, rng, strength):
    for leaf in leaves:
        x, y = leaf.location.x / scale, leaf.location.y / scale
        home = leaf.location.copy()
        spin = leaf.rotation_euler[2]
        half = leaf.get('mv_half_width', .012 * scale)
        omega, phase = rng.uniform(9, 17), rng.uniform(0, math.tau)
        lifts = rng.uniform(.5, 1.0)
        runner = rng.random() < .30                     # most wet leaves only tremble
        threshold, pace = rng.uniform(.75, 1.0), rng.uniform(.10, .32) * scale
        travelled, turned, dt = 0.0, 0.0, times[1] - times[0]
        flap, px, py, pz, yaw = [], [], [], [], []
        for t in times:
            g = gust(t, x, y) * strength
            push = max(0.0, g - threshold)
            if runner:
                travelled += push * pace * dt * 4
                turned += push * dt * rng.uniform(1.5, 4.0)
            angle = math.radians(16) * lifts * min(1.3, g) * (.35 + .65 * math.sin(omega * t + phase)) * (.4 + min(1.0, push * 4))
            flap.append(angle)
            px.append(home.x + DIRECTION[0] * travelled)
            py.append(home.y + DIRECTION[1] * travelled)
            pz.append(home.z + abs(math.sin(angle)) * half)      # it pivots on its low edge, never through the road
            yaw.append(spin + turned)
        _curve(leaf, 'rotation_euler', 0, frames, flap)
        _curve(leaf, 'rotation_euler', 2, frames, yaw)
        _curve(leaf, 'location', 0, frames, px)
        _curve(leaf, 'location', 1, frames, py)
        _curve(leaf, 'location', 2, frames, pz)


def apply(scene, first, total, scale, strength=1.0, canopy=True, seed=20260917):
    if strength <= 0:
        return {'strength': 0}
    fps = scene.render.fps / scene.render.fps_base
    frames = list(range(first - 1, first + total + 1))          # one spare each side for the open shutter
    times = [(f - first) / fps for f in frames]
    rng = random.Random(seed)
    names = {'court': 'Rain — detailed park tree', 'belt': 'Rain — park tree belt', 'verge': 'Rain — verge grass',
             'tuft': 'Rain — park grass tuft', 'leaf': 'Rain — loose leaf'}
    found = {key: sorted((o for o in scene.objects if o.name.startswith(name)), key=lambda o: o.name) for key, name in names.items()}
    for tree in found['court']:
        _rock(tree, frames, times, scale, rng, .22 * strength, .16 * strength, (1.6, 2.4))
    for tree in found['belt']:
        _rock(tree, frames, times, scale, rng, .75 * strength, .60 * strength, (1.7, 3.0))
    for grass in found['verge']:
        _rock(grass, frames, times, scale, rng, 5.0 * strength, 4.0 * strength, (5.0, 9.0))
    # Only the tufts a camera can resolve; the far lawn is sub-pixel.
    near = [g for g in found['tuft'] if abs(g.location.x / scale) < 9 and abs(g.location.y / scale) < 16]
    for grass in near:
        _rock(grass, frames, times, scale, rng, 4.0 * strength, 3.5 * strength, (6.0, 11.0))
    fluttering = _flutter(found['court'], frames, times, scale, strength) if canopy else 0
    _leaves(found['leaf'], frames, times, scale, rng, strength)
    return {'strength': strength, 'courtTrees': len(found['court']), 'beltTrees': len(found['belt']), 'verge': len(found['verge']),
            'tufts': len(near), 'looseLeaves': len(found['leaf']), 'canopyFlutter': fluttering}
