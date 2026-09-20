"""Camera programme driven by the app's own ScenePlan.

The studio draws a camera path in the viewer and the user directs it there, so the
render has to follow that same path or the video is not the scene they planned.
This module is a direct port of `apps/web/components/viewer/cameraPath.ts`; the two
must stay in step, and `test_scene_plan_camera.py` pins the shared numbers.

Axes: the plan is authored in the viewer's glTF frame (Y up, subject centred on XZ
and resting on y=0). Blender's glTF importer rotates that to Z up, so a plan point
(x, y, z) lands at (x, -z, y) relative to the subject's ground centre.
"""
from __future__ import annotations

import math

# `mathutils` exists only inside Blender. The path maths below is kept free of it so
# the numbers can be tested against the TypeScript original without running Blender;
# only the scene-graph helpers import it, lazily.

#: Half the height of a 35 mm sensor, in millimetres. Matches `lensToFov`.
SENSOR_HALF_HEIGHT_MM = 12.0

#: Aperture at `effects.depthOfField` 0 and 1. 16 is effectively deep focus.
APERTURE_DEEP = 16.0
APERTURE_SHALLOW = 1.8


class PlanError(ValueError):
    """The plan cannot be turned into a camera move."""


def bounds(extent):
    """Subject bounds in the viewer's terms: ground radius and height, in metres."""
    return {"radius": max(extent[0], extent[1]) / 2, "height": extent[2]}


def shot_at(plan, seconds):
    """The shot running at an absolute time, and progress through it in [0, 1]."""
    shots = plan["shots"]
    active = None
    for shot in shots:
        if shot["start"] <= seconds <= shot["end"]:
            active = shot
            break
    if active is None:
        active = shots[0] if seconds < shots[0]["start"] else shots[-1]
    span = active["end"] - active["start"]
    t = 0.0 if span <= 0 else (seconds - active["start"]) / span
    return active, min(1.0, max(0.0, t))


def shot_path_point(plan, shot, t, subject):
    """Camera position for `t` within a shot, as (x, y, z) in the viewer's Y-up frame."""
    lens = plan["camera"]["lensMm"]
    base = subject["radius"] * 4 * shot["distanceMultiplier"] * math.sqrt(lens / 50)
    y = plan["camera"]["heightM"]
    action = shot["action"]
    if action == "slow_orbit":
        a = -math.pi * 0.25 + t * math.pi * 0.9
        return (math.sin(a) * base, y, math.cos(a) * base)
    if action == "hero_push_in":
        r = base * (1.6 - 0.8 * t)
        a = -math.pi * 0.2
        return (math.sin(a) * r, y, math.cos(a) * r)
    if action == "low_tracking":
        return (-base * 0.8 + t * base * 1.6, min(y, 0.6), base * 0.9)
    if action == "handheld_walk_toward":
        r = base * (1.8 - 1.0 * t)
        a = -math.pi * 0.3 + t * 0.2
        return (math.sin(a) * r, y, math.cos(a) * r)
    raise PlanError("Unknown shot action: " + str(action))


def handheld_offset(seconds, strength):
    """Operator sway, keyed to absolute time so the frequency is per second."""
    if strength <= 0:
        return (0.0, 0.0, 0.0), 0.0
    return (
        (
            math.sin(seconds * 7.3) * 0.02 * strength,
            abs(math.sin(seconds * 5.1)) * 0.03 * strength,
            0.0,
        ),
        math.sin(seconds * 2.1) * 0.01 * strength,
    )


def lens_to_fov(lens_mm):
    """Vertical field of view in degrees, 35 mm sensor."""
    return math.degrees(2 * math.atan(SENSOR_HALF_HEIGHT_MM / lens_mm))


def aperture(depth_of_field):
    """`effects.depthOfField` to an f-stop. 0 keeps everything sharp."""
    amount = min(1.0, max(0.0, depth_of_field))
    return APERTURE_DEEP + (APERTURE_SHALLOW - APERTURE_DEEP) * amount


def to_blender(point, ground_centre):
    """A plan point (x, y, z) in the viewer's frame to a Blender world (x, y, z)."""
    return (ground_centre[0] + point[0], ground_centre[1] - point[2], ground_centre[2] + point[1])


def configure(camera_data, plan, subject):
    """Lens and depth of field. Vertical sensor fit so the framing matches the viewer."""
    camera_data.sensor_fit = "VERTICAL"
    camera_data.sensor_height = SENSOR_HALF_HEIGHT_MM * 2
    camera_data.lens = plan["camera"]["lensMm"]
    dof = plan["effects"]["depthOfField"]
    camera_data.dof.use_dof = dof > 0
    camera_data.dof.aperture_fstop = aperture(dof)


def pose(plan, subject, ground_centre, seconds):
    """Camera location, aim point and roll for one instant, all in Blender world space."""
    shot, t = shot_at(plan, seconds)
    point = shot_path_point(plan, shot, t, subject)
    sway, roll = handheld_offset(seconds, plan["camera"]["motionStrength"])
    swayed = (point[0] + sway[0], point[1] + sway[1], point[2] + sway[2])
    location = to_blender(swayed, ground_centre)
    aim = (ground_centre[0], ground_centre[1], ground_centre[2] + subject["height"] / 2)
    return location, aim, roll


def place(camera, plan, subject, ground_centre, seconds):
    """Points the camera for one instant. Returns the distance to the subject."""
    from mathutils import Vector

    located, aimed, roll = pose(plan, subject, ground_centre, seconds)
    location = Vector(located)
    aim = Vector(aimed)

    camera.location = location
    rotation = (aim - location).to_track_quat("-Z", "Y").to_euler()
    # Roll is about the view axis, which is the camera's local Y after tracking.
    rotation.rotate_axis("Z", roll)
    camera.rotation_euler = rotation
    distance = (aim - location).length
    if camera.data.dof.use_dof:
        camera.data.dof.focus_distance = distance
    return distance


def animate(camera, plan, subject, ground_centre, first, total, fps):
    """Bakes one keyframe per frame. Linear, so a hard cut between shots stays hard."""
    configure(camera.data, plan, subject)
    for offset in range(total):
        place(camera, plan, subject, ground_centre, offset / fps)
        frame = first + offset
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        if camera.data.dof.use_dof:
            camera.data.keyframe_insert(data_path="dof.focus_distance", frame=frame)
    for track in (camera.animation_data, camera.data.animation_data):
        if not track or not track.action:
            continue
        for curve in _fcurves(track.action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"


def _fcurves(action):
    """Blender 4.4 moved f-curves into slotted actions; 5.0 dropped the old attribute."""
    if hasattr(action, "layers"):
        return [curve for layer in action.layers for strip in layer.strips
                for bag in strip.channelbags for curve in bag.fcurves]
    return list(action.fcurves)
