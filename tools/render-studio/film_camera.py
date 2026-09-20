"""Five handheld walk-around shots filmed by a simulated human operator."""
import json
import math
import random

from mathutils import Vector


SHOT_NAMES = ('Low front three-quarter', 'Rear three-quarter', 'Wheel and contact', 'Headlight optics', 'Wet hood and carbon')
SHOT_BOUNDARIES = (0, .42, .60, .74, .87, 1)


def shot_at(offset, total):
    # Integer boundaries keep small smoke renders and non-divisible durations
    # inside valid shots. Samples never interpolate across an editorial cut.
    position = max(0, min(offset, total-1)) / max(1, total)
    index = next((i for i in range(len(SHOT_NAMES)) if position < SHOT_BOUNDARIES[i+1]), len(SHOT_NAMES)-1)
    start = math.ceil(SHOT_BOUNDARIES[index] * total)
    end = math.ceil(SHOT_BOUNDARIES[index+1] * total) - 1
    t = max(0.0, min(1.0, (offset - start) / max(1, end - start)))
    return index, t


# Camera-side (+X) parts by ModVision slot id; the site tags every exported mesh
# with `mvSlot` (glTF extra -> custom property), so this works on any car.
SLOT_ANCHORS = {'wheel-FL': 'wheel', 'tire-FL': 'wheel', 'headlight-L': 'lamp'}


def anchor_key(obj):
    """'wheel' / 'lamp' / None for one mesh: slot tag first, canonical name second."""
    try:
        slot = obj.get('mvSlot')
    except (AttributeError, TypeError):
        slot = None
    if isinstance(slot, str) and slot in SLOT_ANCHORS:
        return SLOT_ANCHORS[slot]
    name = obj.name.lower()
    if name.startswith('headlight-l-lens'):
        return 'lamp'
    if name.startswith(('wheel-fl', 'tire-fl')):
        return 'wheel'
    return None


def anchors(meshes, center, extent, low):
    """Use assembled part locations, with bounds-based fallbacks for other cars."""
    result = {'wheel': Vector((center.x + extent.x*.4, center.y - extent.y*.26, low.z + extent.z*.24)),
              'lamp': Vector((center.x + extent.x*.33, center.y - extent.y*.37, low.z + extent.z*.49))}
    candidates = {'wheel': [], 'lamp': []}
    rejected = []
    for obj in meshes:
        key = anchor_key(obj)
        if not key:
            continue
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        lo = Vector([min(p[i] for p in corners) for i in range(3)])
        hi = Vector([max(p[i] for p in corners) for i in range(3)])
        size, middle = (hi - lo).length, (hi + lo) / 2
        # A front camera-side part sits ahead of the car's centre (nose at -Y)
        # and on +X. A slot alias that swept up half the body (one Chiron
        # carbon mesh is tagged headlight-L) fails both tests, so it can no
        # longer drag the close-up onto bodywork.
        if size > 0.6 * extent.length or middle.y > center.y or middle.x < center.x:
            rejected.append([obj.name, key, round(size, 2), [round(v, 2) for v in middle]])
            continue
        # Rank by how far outboard (+X) and forward (-Y) the part sits, in car
        # units: the lamp and the front wheel live at the corner, a sprawling
        # alias (a whole headlight assembly, a fender-wide carbon piece) has
        # its centre well inboard of it. Size no longer wins.
        corner = (middle.x - center.x) / max(1e-6, extent.x) - (middle.y - center.y) / max(1e-6, extent.y)
        candidates[key].append((corner, size, middle, obj.name))
    chosen = {}
    for key, choices in candidates.items():
        if choices:
            best = max(choices, key=lambda item: (round(item[0], 3), item[1]))
            result[key] = best[2]
            chosen[key] = best[3]
    # Reported to the render log so a close-up that lands on bodywork can be
    # traced to its anchor without re-rendering.
    print('ANCHORS ' + json.dumps({key: {'source': 'part' if candidates[key] else 'bounds',
                                           'candidates': len(candidates[key]), 'chosen': chosen.get(key),
                                           'at': [round(v, 3) for v in result[key]]} for key in result}
                                   | {'center': [round(v, 3) for v in center], 'extent': [round(v, 3) for v in extent],
                                      'rejected': rejected}), flush=True)
    return result


def _wander(seed, seconds, slow=1.0, fast=.12):
    """Smooth drift plus faint hand tremor, roughly -1..1.

    Sums of incommensurate sines: continuous across the open shutter, so depth
    of field never shimmers the way per-frame random jitter does.
    """
    a = seed * 12.9898
    drift = (math.sin(seconds*1.45 + a) + .6*math.sin(seconds*2.61 + a*1.7) + .35*math.sin(seconds*4.83 + a*2.3)) / 1.95
    rig = (math.sin(seconds*19.5 + a*3.1) + .7*math.sin(seconds*33.3 + a*.7) + .5*math.sin(seconds*42.1 + a*1.3)) / 2.2
    return slow*drift + fast*rig


def _bezier(a, b, c, u):
    return a*((1-u)**2) + b*(2*u*(1-u)) + c*(u*u)


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x*x*(3 - 2*x)


def _shots(center, extent, low, targets, scale, portrait):
    """Where a person walks, and what they point the camera at.

    Car space: +X is the camera side, -Y the nose, metres at reference scale.
    `path` is the route of the operator's hands (start, via, end); walking
    pace, footfalls, sway, aim lag and reframing come from `_operate`. `gait`
    scales the footstep motion: 1 a normal walk, lower for a crouched shuffle
    or a lean-in where the feet barely move.
    """
    s = scale
    nose = center.y - extent.y/2
    tail = center.y + extent.y/2
    ground = low.z

    def P(x, y, z):
        return Vector((x, y, z))

    wheel, lamp = targets['wheel'], targets['lamp']
    hood = P(center.x + extent.x*.10, nose + extent.y*.20, ground + extent.z*.60)
    # The walk-in is long-lensed so the car fills the frame the way the rear
    # three-quarter does; the hood pass stays wide because it is inches away.
    wide = (40, 24) if not portrait else (30, 20)
    return [
        # 0 — walking in from the grass past the near tree, camera at chest
        # height. The trunk crosses the car and clears it.
        dict(lens=wide[0], fstop=2.8, gait=1.0,
             # Starts with the near trunk (about 6.0, -6.5) on the line to the
             # car, rounds it on the outside, steps over the curb and closes in.
             path=(P(center.x + 7.65*s, center.y - 8.0*s, ground + 1.34*s),
                   P(center.x + 7.5*s, center.y - 5.9*s, ground + 1.30*s),
                   P(center.x + 4.4*s, center.y - 4.5*s, ground + 1.12*s)),
             aim=(P(center.x - extent.x*.35, center.y - extent.y*.08, ground + extent.z*.50),
                  P(center.x + extent.x*.05, center.y - extent.y*.20, ground + extent.z*.48)),
             focus=(lamp, lamp), pull=(0, 1)),
        # 1 — walking around the rear quarter, camera sinking from chest to hip.
        dict(lens=28 if not portrait else 24, fstop=2.0, gait=1.0,
             path=(P(center.x + 3.9*s, tail + 2.6*s, ground + 1.18*s),
                   P(center.x + 3.0*s, tail + 3.1*s, ground + 1.02*s),
                   P(center.x + 1.5*s, tail + 2.9*s, ground + .86*s)),
             aim=(P(center.x - extent.x*.40, tail - extent.y*.14, ground + extent.z*.52),
                  P(center.x + extent.x*.05, tail - extent.y*.10, ground + extent.z*.50)),
             focus=(P(center.x + 3.0*s, tail + 1.6*s, ground + .3*s),
                    P(center.x + extent.x*.25, tail - extent.y*.04, ground + extent.z*.55)),
             pull=(.05, .30)),
        # 2 — crouched beside the front wheel, shuffling along the sill.
        dict(lens=70, fstop=2.2, gait=.35,
             path=(wheel + P(1.55*s, -.42*s, -.10*s),
                   wheel + P(1.66*s, -.12*s, -.17*s),
                   wheel + P(1.55*s, .20*s, -.21*s)),
             aim=(wheel + P(0, -.06*s, .03*s), wheel + P(0, .07*s, -.20*s)),
             focus=(wheel + P(-.05*s, .0, .02*s), wheel + P(.13*s, .05*s, -.24*s)), pull=(.35, .75)),
        # 3 — leaning in over the wing: beads first, then the lamp optics.
        dict(lens=85, fstop=3.2, gait=.25,
             path=(lamp + P(.95*s, -.55*s, .62*s),
                   lamp + P(.66*s, -.98*s, .52*s),
                   lamp + P(.22*s, -1.16*s, .42*s)),
             aim=(lamp + P(.02*s, .10*s, .02*s), lamp + P(-.02*s, .0, -.01*s)),
             focus=(lamp + P(.10*s, .34*s, .10*s), lamp), pull=(.20, .60)),
        # 4 — walking past the nose, camera held out over the wet hood.
        dict(lens=wide[1], fstop=2.8, gait=1.0,
             path=(P(center.x + extent.x*.62, nose - .70*s, ground + extent.z*.86),
                   P(center.x + extent.x*.40, nose - .35*s, ground + extent.z*.84),
                   P(center.x + extent.x*.16, nose + .15*s, ground + extent.z*.88)),
             aim=(hood + P(-.10*s, .25*s, -.02*s), hood + P(-.18*s, 1.25*s, .06*s)),
             focus=(hood + P(.12*s, -.25*s, .0), hood + P(.0, .55*s, .04*s)), pull=(.15, .80)),
    ]


_TAKES = {}


def _operate(index, shot, frames, fps, scale):
    """Simulate a person walking this shot with a lightly stabilized camera.

    Integrated at 8 substeps per frame so the body, not a formula, produces
    the motion: pace that builds and eases with a little unevenness, footfalls
    whose stride length varies step to step, weight shifting side to side with
    roll, and an aim that chases the subject through a damped spring. The
    operator also reframes now and then, so tracking is never locked. Returns
    one (location, aim point, roll, focus point) per frame. Deterministic.
    """
    rng = random.Random(9176 + index)
    sub = 8
    dt = 1 / (fps * sub)
    duration = max(1, frames - 1) / fps
    start, via, end = shot['path']
    length = (via - start).length + (end - via).length
    gait = shot['gait']

    def pace(time):
        x = time / max(1e-6, duration)
        # Already moving on the cut, settles into pace, eases before the next cut.
        return (.62 + .38*_smooth(x / .30)) * (1 - .45*_smooth((x - .68) / .32)) * (1 + .09*_wander(index + .71, time, fast=0))

    steps = max(1, (frames - 1) * sub)
    total_pace = sum(pace(k * dt) for k in range(steps)) * dt
    # Occasional reframing: a new framing offset (fractions of the picture)
    # every .8 to 1.9 s, which the aim spring then glides toward.
    corrections, clock = [], rng.uniform(.3, .9)
    while clock < duration + 2:
        corrections.append((clock, rng.uniform(-.10, .10), rng.uniform(-.055, .06)))
        clock += rng.uniform(.5, 1.4)
    travelled, phase, stride_bias = 0.0, rng.random(), 0.0
    aim_point, aim_velocity = None, Vector((0, 0, 0))
    frame_offset = [rng.uniform(-.05, .05), rng.uniform(-.02, .03)]
    offset_now, offset_velocity = list(frame_offset), [0.0, 0.0]
    result = []
    omega = 5.0      # wrist: settles on the intended direction in about a quarter second
    damping = .58
    # Hesitations: the operator checks footing or the screen. Count, depth and
    # length differ per take, and each one brings a framing fix with it.
    pauses = [(rng.uniform(.15, .85) * duration, rng.uniform(.18, .55), rng.uniform(.25, .70))
              for _ in range(rng.choice((0, 1, 1, 2)) + (duration > 3))]
    for when, width, _depth in pauses:
        corrections.append((when + rng.uniform(-.1, .25) * width, rng.uniform(-.08, .08), rng.uniform(-.05, .05)))
    corrections.sort()

    def footfall():
        # No two steps are alike: height, side reach, push and how hard it lands.
        return dict(bob=rng.uniform(.55, 1.45), sway=rng.uniform(.6, 1.4), surge=rng.uniform(.4, 1.6),
                    hard=rng.lognormvariate(0, .45), skew=rng.uniform(-.5, .5))
    last_step, this_step = footfall(), footfall()
    # Arms: the camera hangs off the body through a loose spring, so it lags the
    # steps by a changing amount and rings a little after each landing.
    hand, hand_velocity = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]      # up, across, along (metres at scale 1)
    jolt, jolt_velocity = [0.0, 0.0], [0.0, 0.0]                # pitch/yaw ring-down, picture fractions
    goal_direction = None
    tolerance = rng.uniform(.05, .10)                            # how far the subject may slide before a fix
    catch_up, lapse_until = 0.0, -1.0
    next_lapse = rng.uniform(.8, 2.5)
    for k in range(steps + 1):
        time = k * dt
        speed = length * pace(time) / max(1e-6, total_pace)       # m/s along the route
        speed *= 1 + .16*_wander(index + .77, time * .45, fast=0) + .05*_wander(index + .78, time * 1.9, fast=0)
        for when, width, depth in pauses:
            speed *= 1 - depth * math.exp(-((time - when) / width) ** 2)
        u = min(1.0, travelled / max(1e-6, length))
        body = _bezier(start, via, end, u)
        heading = (_bezier(start, via, end, min(1, u + .02)) - _bezier(start, via, end, max(0, u - .02)))
        heading.z = 0
        heading = heading.normalized() if heading.length > 1e-6 else Vector((0, 1, 0))
        across = Vector((heading.y, -heading.x, 0))
        stride = .64 * scale * (1 + .18*_wander(index + .83, time * .7, fast=0) + stride_bias)
        walking = min(1.0, speed / (.55 * scale)) * gait
        blend = _smooth(phase % 1)
        mix = {key: last_step[key] + (this_step[key] - last_step[key]) * blend for key in this_step}
        step = 2 * math.pi * (phase + .06 * mix['skew'] * math.sin(2 * math.pi * phase))
        heavy = 1 + .14*math.sin(step / 2 + .6)
        body_up = (-math.cos(step) + .22*math.cos(2*step + .8)) * .015 * heavy * mix['bob']
        body_across = (math.sin(step / 2) * .027 + .006*math.sin(step + 1.3)) * mix['sway']
        body_along = math.sin(step + 1.1) * .010 * mix['surge']
        # Grip tightens and loosens, which keeps shifting the lag behind the feet.
        arm = 9.0 * (1 + .30*_wander(index + .95, time * .5, fast=0))
        for axis, drive in enumerate((body_up, body_across, body_along)):
            accel = arm * arm * (drive * walking - hand[axis]) - 2 * .42 * arm * hand_velocity[axis]
            hand_velocity[axis] += accel * dt
            hand[axis] += hand_velocity[axis] * dt
        body = body + across * (.07 * scale * gait * (_wander(index + .9, time * .55, fast=0) + .4*_wander(index + .91, time * .23, fast=0)))
        drift = Vector((_wander(index + .1, time), _wander(index + .2, time), .7*_wander(index + .3, time))) * .018
        location = body + (Vector((0, 0, hand[0])) + across * hand[1] + heading * hand[2] + drift) * scale
        roll = (math.radians(.95) * (hand[1] / .027) * .8 + math.radians(3.5) * hand_velocity[1]
                + math.radians(.35) * _wander(index + .6, time, fast=.05))
        for when, right_fraction, up_fraction in corrections:
            if when <= time:
                frame_offset = [right_fraction, up_fraction]
        for axis in range(2):
            accel = 60.0 * (frame_offset[axis] - offset_now[axis]) - 9.5 * offset_velocity[axis]
            offset_velocity[axis] += accel * dt
            offset_now[axis] += offset_velocity[axis] * dt
            accel = 15.0 * 15.0 * -jolt[axis] - 2 * .33 * 15.0 * jolt_velocity[axis]
            jolt_velocity[axis] += accel * dt
            jolt[axis] += jolt_velocity[axis] * dt
        subject = shot['aim'][0].lerp(shot['aim'][1], _smooth(u))
        forward = (subject - location).normalized()
        right = forward.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(forward).normalized()
        reach = (subject - location).length
        picture = 2 * reach * 18 / shot['lens']                     # metres across the frame at the subject
        desired = subject + right * (offset_now[0] * picture) + up * (offset_now[1] * picture * .5625)
        # Tracking. A person holds a direction, not a point on the car: they
        # pan along roughly, fall behind, notice, and catch up. Now and then
        # their eyes leave the screen and the pan goes slack.
        # Composition drifts on its own too: attention, not geometry.
        loose = .4 + .6 * gait
        desired = desired + (right * (.040 * _wander(index + .98, time * .45, fast=0)) + up * (.022 * _wander(index + .99, time * .38, fast=0))) * picture * loose
        wanted = (desired - location).normalized()
        if goal_direction is None:
            goal_direction = wanted.copy()
        slip = (wanted - goal_direction).length * reach / picture   # picture fractions
        if slip > tolerance and catch_up < .05:
            catch_up = 1.0
            tolerance = rng.uniform(.04, .11)
        if time > next_lapse:
            lapse_until = time + rng.uniform(.25, .7)
            next_lapse = time + rng.uniform(1.4, 4.0)
        follow = (1.1 + 2.2 * (1 - gait)) * (1 + .45*_wander(index + .97, time * .6, fast=0))   # close work is held tighter
        if time < lapse_until:
            follow *= .25
        follow += 7.5 * catch_up
        catch_up *= math.exp(-dt / .16)
        goal_direction = (goal_direction + (wanted - goal_direction) * min(1.0, follow * dt)).normalized()
        goal = location + goal_direction * reach
        tremor = (right * _wander(index + .4, time, slow=.35, fast=.10) + up * _wander(index + .5, time, slow=.30, fast=.10)) * picture * .010
        if aim_point is None:
            aim_point = goal.copy()
        aim_velocity += ((goal - aim_point) * (omega * omega) - aim_velocity * (2 * damping * omega)) * dt
        aim_point = aim_point + aim_velocity * dt
        if k % sub == 0:
            pull_start, pull_end = shot['pull']
            x = (time / max(1e-6, duration) - pull_start) / max(1e-6, pull_end - pull_start)
            focus = shot['focus'][0].lerp(shot['focus'][1], _smooth(x))
            leak = (right * jolt[0] + up * jolt[1]) * picture
            result.append((location.copy(), aim_point + leak + tremor, roll, focus))
        travelled += speed * dt
        previous = phase
        phase += speed / max(1e-6, stride) * dt
        if int(phase) != int(previous):
            stride_bias = rng.uniform(-.16, .16)                    # this step came out short or long
            last_step, this_step = this_step, footfall()
            # The landing: a knock through the arms and past the gimbal, never the same twice.
            hit = this_step['hard'] * walking
            hand_velocity[0] -= .028 * hit
            hand_velocity[1] += .020 * hit * rng.uniform(-1, 1)
            jolt_velocity[0] += .075 * hit * rng.uniform(-1, 1)
            jolt_velocity[1] -= .110 * hit * rng.uniform(.3, 1)
    return result


def pose(camera, center, extent, low, points, width, height, offset, total, scale, targets=None, fps=24):
    index, t = shot_at(offset, total)
    data = camera.data
    data.sensor_fit = 'HORIZONTAL'
    data.sensor_width = 36
    data.dof.use_dof = True
    data.dof.aperture_blades = 9
    portrait = height > width
    targets = targets or anchors([], center, extent, low)
    first = math.ceil(SHOT_BOUNDARIES[index] * total)
    last = math.ceil(SHOT_BOUNDARIES[index + 1] * total) - 1
    frames = max(1, last - first + 1)
    key = (index, frames, fps, portrait, round(scale, 6), tuple(round(v, 5) for v in (*center, *extent, *low)),
           tuple(round(v, 5) for name in ('wheel', 'lamp') for v in targets[name]))
    if key not in _TAKES:
        shot = _shots(center, extent, low, targets, scale, portrait)[index]
        _TAKES[key] = (shot, _operate(index, shot, frames, fps, scale))
    shot, take = _TAKES[key]
    location, aim_point, roll, focus_point = take[max(0, min(frames - 1, offset - first))]
    data.lens = shot['lens']
    data.dof.aperture_fstop = shot['fstop']
    aim = (aim_point - location).normalized()
    euler = aim.to_track_quat('-Z', 'Y').to_euler()
    euler.rotate_axis('Z', roll)
    camera.location = location
    camera.rotation_euler = euler
    data.dof.focus_distance = max(.05*scale, (focus_point - location).dot(aim))
    return {'index': index, 'name': SHOT_NAMES[index], 'position': list(location), 'target': list(aim_point), 'lens': data.lens}


def animate(camera, scene, center, extent, low, points, width, height, total, first, scale, meshes=()):
    """Bake motion with camera cuts outside both adjacent shutter intervals."""
    targets = anchors(meshes, center, extent, low)

    def key_pose(frame):
        for prop in ('location', 'rotation_euler'):
            camera.keyframe_insert(data_path=prop, frame=frame)
        for prop in ('lens', 'dof.focus_distance', 'dof.aperture_fstop'):
            camera.data.keyframe_insert(data_path=prop, frame=frame)

    for offset in range(total):
        info = pose(camera, center, extent, low, points, width, height, offset, total, scale, targets, scene.render.fps)
        frame = first + offset
        if offset and shot_at(offset-1, total)[0] != info['index']:
            # With a centered .5 shutter the previous frame ends exposure at
            # frame-.75 and this frame starts at frame-.25. Move the camera
            # only in that closed-shutter gap; falling rain keeps full blur.
            pose(camera, center, extent, low, points, width, height, offset-1, total, scale, targets, scene.render.fps)
            key_pose(frame-.75)
            pose(camera, center, extent, low, points, width, height, offset, total, scale, targets, scene.render.fps)
            key_pose(frame-.25)
        key_pose(frame)
        if offset == 0 or shot_at(offset-1, total)[0] != info['index']:
            scene.timeline_markers.new(info['name'], frame=frame)
    # Linear subframes prevent automatic Bezier handles from swinging toward
    # the next shot just before a cut. The path itself already has easing.
    for animated in (camera, camera.data):
        action = animated.animation_data.action
        if hasattr(action, 'layers'):
            curves = [curve for layer in action.layers for strip in layer.strips
                      for bag in strip.channelbags for curve in bag.fcurves]
        else:
            curves = action.fcurves
        for curve in curves:
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    scene.render.motion_blur_position = 'CENTER'
    if hasattr(scene.cycles, 'rolling_shutter_type'):
        scene.cycles.rolling_shutter_type = 'NONE'
