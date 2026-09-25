"""Wheel spin from the path (TAXONOMY VD-02; METHODS §2.2 M-KIN): omega = (z x v) / r about each axle
(engine/physics/wheel_spin). The angle per frame is keyed on valora_rz_wheel_<i> (location.x, radians);
the node tree turns every spin-safe island (valora_spin, round and on the axle) about its axle.
Calipers and anything off-axis never spin. Stacked before tyre_contact (resolver ORDER).
The angle is keyed one frame past each end from the motion's own value there (review item 7): it runs on
where the motion runs on (a centred shutter samples frame n + 0.5) and holds where the motion holds."""
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
    t = gn.Tree("valora_rz_wheel_roll")
    P, back = gn.placed(t, offset)
    tag, new, slips = t.attr(SPIN), P, []
    for i, w in enumerate(prof.wheels):
        ang = WS.wheel_angles(xpos, xyaw, w["axis"], w["radius"])
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
    drv0 = scene.objects.get("valora_rz_wheel_0")
    c = next((c for c in fcurves(drv0.animation_data.action)), None) if drv0 and drv0.animation_data else None
    n = scene.frame_end
    record("wheel_angle_extrapolated", [bool(c) and abs(c.evaluate(0) - c.evaluate(1)) > 1e-9,
                                        bool(c) and abs(c.evaluate(n + 1) - c.evaluate(n)) > 1e-9])
