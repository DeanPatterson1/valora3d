"""Wheel spin from the path (TAXONOMY VD-02; METHODS §2.2 M-KIN): omega = (z x v) / r about each axle
(engine/physics/wheel_spin). The angle per frame is keyed on valora_rz_wheel_<i> (location.x, radians);
the node tree turns every spin-safe island (valora_spin, round and on the axle) about its axle.
Calipers and anything off-axis never spin. Stacked before tyre_contact (resolver ORDER).
The angle is keyed one frame past each end from the motion's own value there (review item 7): it runs on
where the motion runs on (a centred shutter samples frame n + 0.5) and holds where the motion holds.
The angle is 0 at frame 1 (the integration starts one frame early, at that extra key): frame 1 shows the
modelled wheel pose."""
from engine.physics import wheel_spin as WS


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import SPIN, driver, fcurves, key_series, motion_track, record, rig, tag_wheels
    prof, scene = ctx.profile, ctx.scene
    _, offset = rig()
    tag_wheels(ctx.meshes, prof.wheels)
    pos, yaw = motion_track(scene)
    frames = list(range(0, scene.frame_end + 2))              # one frame past each end
    xpos, xyaw = motion_track(scene, frames)
    # a turning path (drive arcs, Task 79 / H5): each wheel integrates its OWN contact-point path, so the
    # outer wheel turns more than the inner one; a straight path keeps the phase-3 form (identical there)
    turning = max((abs(y - xyaw[0]) for y in xyaw), default=0.0) > 1e-6
    t = gn.Tree("valora_rz_wheel_roll")
    P, back = gn.placed(t, offset)
    tag, new, slips, scrubs = t.attr(SPIN), P, [], []
    for i, w in enumerate(prof.wheels):
        if turning:
            c = w["center"]
            cp = WS.contact_points(xpos, xyaw, (c[0], c[1], c[2] - w["radius"]))
            ang = WS.wheel_angles_contact(cp, xyaw, w["axis"], w["radius"])
        else:
            ang = WS.wheel_angles(xpos, xyaw, w["axis"], w["radius"])
        ang = [a - ang[1] for a in ang]                        # frames[1] is frame 1: its pose is unchanged
        if turning:
            slips.append(WS.slip_curved(ang[1:-1], cp[1:-1], w["radius"], xyaw[1:-1], w["axis"]))
            scrubs.append(WS.scrub(cp[1:-1], xyaw[1:-1], w["axis"]))
        else:
            slips.append(WS.slip(ang[1:-1], pos, w["radius"]))
        drv = driver(f"valora_rz_wheel_{i}")
        key_series(drv, "location", 0, frames, ang)             # constant past the extra keys
        c = t.vec(*w["center"])
        turn = t.xyz(t.object_location(drv))[0]
        spun = t.vmath("ADD", t.rotate(t.vmath("SUBTRACT", P, c), t.vec(*w["axis"]), turn), c)
        new = t.switch_vec(t.equals(tag, i + 1), new, spun)
    t.set_position(back(new))
    ng = t.finish()
    for o in ctx.meshes:
        a = o.data.attributes.get(SPIN)
        if a is not None:
            gn.add_modifier(o, ng, "valora_rz_wheel_roll")
    record("wheel_slip", max(slips, default=0.0))
    record("wheel_roll_form", "contact" if turning else "path")
    record("wheel_scrub", [round(x, 6) for x in scrubs])      # report-only: unsteered wheels pushed sideways
    drv0 = scene.objects.get("valora_rz_wheel_0")
    c = next((c for c in fcurves(drv0.animation_data.action)), None) if drv0 and drv0.animation_data else None
    n = scene.frame_end
    record("wheel_angle_extrapolated", [bool(c) and abs(c.evaluate(0) - c.evaluate(1)) > 1e-9,
                                        bool(c) and abs(c.evaluate(n + 1) - c.evaluate(n)) > 1e-9])
