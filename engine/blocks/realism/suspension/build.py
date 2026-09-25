"""Body on springs (TAXONOMY VD-01; METHODS §2.2 M-KIN). Every vertex outside the wheel boxes
(valora_unsprung == 0) is the body: it sits sagFracR x r lower, and around each stop it pitches (the braking
dive builds over suspension.DIVE_RAMP_S, then is released into damped bounces), after each landing it heaves
(engine/physics/suspension). Per-frame values are keyed on the valora_rz_body driver (location.x = pitch in
radians, location.z = heave in metres); the node tree rotates the body about the wheelbase centre at axle
height, about the axis across the car. Keys run for suspension.settle_window_s after each event (until the
bounce is below 0.1%; a fixed 2 s window snapped a soft car mid-bounce, review fix 5); a car that never
stops or lands gets no keys at all (the sag is a plain driver location), so its geometry stays static."""
import math

from engine.physics import events, suspension as S



def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import UNSPRUNG, driver, key_series, motion_track, record, rig, tag_wheels
    p, prof, scene = ctx.params, ctx.profile, ctx.scene
    fps, n = ctx.script["format"]["fps"], scene.frame_end
    _, offset = rig()
    tag_wheels(ctx.meshes, prof.wheels)
    r = sorted(w["radius"] for w in prof.wheels)[len(prof.wheels) // 2]
    sag = S.static_sag(r, p["sagFracR"])
    fwd = (prof.vehicle or {}).get("forwardAxis", [0.0, 1.0, 0.0])
    pos, yaw = motion_track(scene)
    pitch, heave = [0.0] * n, [-sag] * n
    ramp = int(math.ceil(S.DIVE_RAMP_S * fps))
    win = int(math.ceil(min(S.settle_window_s(p["rideHz"], p["damping"]), n / fps) * fps))
    for e in events.stops(pos, fps, prof.longest):
        c, s = math.cos(yaw[e["frame"] - 1]), math.sin(yaw[e["frame"] - 1])
        ahead = 1.0 if e["dir"][0] * (c * fwd[0] - s * fwd[1]) + e["dir"][1] * (s * fwd[0] + c * fwd[1]) >= 0 else -1.0
        for f in range(max(1, e["frame"] - ramp), min(n, e["frame"] + win) + 1):
            pitch[f - 1] += ahead * S.pitch_after_stop((f - e["frame"]) / fps, e["decelMs2"], p["rideHz"], p["damping"])
    for e in events.landings(pos, fps, prof.longest):
        for f in range(e["frame"], min(n, e["frame"] + win) + 1):
            heave[f - 1] += S.heave_after_landing((f - e["frame"]) / fps, e["impactMs"], p["rideHz"], p["damping"], 0.3 * r)
    drv = driver("valora_rz_body")
    frames = list(range(1, n + 1))
    if len(set(pitch)) == 1 and len(set(heave)) == 1:
        # Nothing happens: the sag is a plain location, no keys. Any key animates the driver and every
        # frame then re-evaluates the car's modifiers and Cycles re-syncs it (Task 25 measurement).
        frames = []
        drv.location[0], drv.location[2] = pitch[0], heave[0]
    else:
        key_series(drv, "location", 0, frames, pitch)
        key_series(drv, "location", 2, frames, heave)
    cs = [w["center"] for w in prof.wheels]
    pivot = [sum(c[k] for c in cs) / len(cs) for k in range(3)]
    across = (fwd[1], -fwd[0], 0.0)                 # forward x up: nose-down pitch is a negative turn about it
    t = gn.Tree("valora_rz_suspension")
    P, back = gn.placed(t, offset)
    lx, _, lz = t.xyz(t.object_location(drv))
    piv = t.vec(*pivot)
    turned = t.vmath("ADD", t.rotate(t.vmath("SUBTRACT", P, piv), t.vec(*across), t.math("MULTIPLY", lx, -1.0)), piv)
    body = t.vmath("ADD", turned, t.vec(0.0, 0.0, lz))
    t.set_position(back(body), selection=t.equals(t.attr(UNSPRUNG), 0.0))
    ng = t.finish()
    for o in ctx.meshes:
        gn.add_modifier(o, ng, "valora_rz_suspension")
    record("suspension_sag_m", sag)
    record("suspension_keys", len(frames))
    record("suspension_animated", drv.animation_data is not None)
    record("suspension_peak_pitch_rad", max((abs(v) for v in pitch), default=0.0))
