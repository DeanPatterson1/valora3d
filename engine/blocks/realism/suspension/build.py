"""Body on springs (TAXONOMY VD-01; METHODS §2.2 M-KIN). Every vertex outside the wheel boxes
(valora_unsprung == 0) is the body: it sits sagFracR x r lower, and around each stop it pitches (the braking
dive builds over suspension.DIVE_RAMP_S, then is released into damped bounces), after each landing it heaves
(engine/physics/suspension), and in a turn it rolls out of the turn by ROLL_DEG_PER_G[vehicleClass] x lateral g, lagged (Task 79,
VD-04/05). Per-frame values are keyed on the valora_rz_body driver (location.x = pitch in radians, location.y =
roll in radians, + = right side down, location.z = heave in metres); the node tree rotates the body about the
wheelbase centre at axle height, about the axis across the car, then about the forward axis. Keys run for suspension.settle_window_s after each event (until the
bounce is below 0.1%; a fixed 2 s window snapped a soft car mid-bounce, review fix 5); a car that never
stops, lands or turns gets no keys at all (the sag is a plain driver location), so its geometry stays static.
A perShot drive replays at every shot (motion_path.frame_shots): stops, landings and lateral g are read within
each take (the cut's jump back is no stop and no turn), the roll lag restarts level, and a settle's keys end
with its take."""
import math

from engine.physics import events, suspension as S



def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import UNSPRUNG, driver, key_series, motion_track, record, rig, tag_wheels
    from engine.motion_path import frame_shots
    p, prof, scene = ctx.params, ctx.profile, ctx.scene
    fps, n = ctx.script["format"]["fps"], scene.frame_end
    _, offset = rig()
    tag_wheels(ctx.meshes, prof.wheels)
    r = sorted(w["radius"] for w in prof.wheels)[len(prof.wheels) // 2]
    sag = S.static_sag(r, p["sagFracR"])
    fwd = (prof.vehicle or {}).get("forwardAxis", [0.0, 1.0, 0.0])
    pos, yaw = motion_track(scene)
    shots = frame_shots(ctx.script, range(1, n + 1))         # None unless the motion replays per shot
    pitch, heave = [0.0] * n, [-sag] * n
    # body roll in turns (Task 79, VD-04/05): rollDegPerG x lateral g, lagged, leaning out of the turn
    # rollDegPerG by vehicle class is a build constant, not a param: a new auto param would change every
    # resolved phase-3 script (the pre-motion pinned baseline)
    roll_k = S.roll_deg_per_g((prof.vehicle or {}).get("vehicleClass", "comfort"))
    roll = S.body_roll(S.lateral_g(pos, yaw, fps, fwd, shots), roll_k, fps, shots=shots)
    ramp = int(math.ceil(S.DIVE_RAMP_S * fps))
    win = int(math.ceil(min(S.settle_window_s(p["rideHz"], p["damping"]), n / fps) * fps))
    for e in events.stops(pos, fps, prof.longest, shots):
        first, last = events.take_of(shots, n, e["frame"])
        c, s = math.cos(yaw[e["frame"] - 1]), math.sin(yaw[e["frame"] - 1])
        ahead = 1.0 if e["dir"][0] * (c * fwd[0] - s * fwd[1]) + e["dir"][1] * (s * fwd[0] + c * fwd[1]) >= 0 else -1.0
        for f in range(max(first, e["frame"] - ramp), min(last, e["frame"] + win) + 1):
            pitch[f - 1] += ahead * S.pitch_after_stop((f - e["frame"]) / fps, e["decelMs2"], p["rideHz"], p["damping"])
    for e in events.landings(pos, fps, prof.longest, shots):
        last = events.take_of(shots, n, e["frame"])[1]
        for f in range(e["frame"], min(last, e["frame"] + win) + 1):
            heave[f - 1] += S.heave_after_landing((f - e["frame"]) / fps, e["impactMs"], p["rideHz"], p["damping"], 0.3 * r)
    drv = driver("valora_rz_body")
    frames = list(range(1, n + 1))
    if len(set(pitch)) == 1 and len(set(heave)) == 1 and max(abs(v) for v in roll) < 1e-9:
        # Nothing happens: the sag is a plain location, no keys. Any key animates the driver and every
        # frame then re-evaluates the car's modifiers and Cycles re-syncs it (Task 25 measurement).
        frames = []
        drv.location[0], drv.location[2] = pitch[0], heave[0]
    else:
        key_series(drv, "location", 0, frames, pitch)
        key_series(drv, "location", 1, frames, roll)
        key_series(drv, "location", 2, frames, heave)
    cs = [w["center"] for w in prof.wheels]
    pivot = [sum(c[k] for c in cs) / len(cs) for k in range(3)]
    across = (fwd[1], -fwd[0], 0.0)                 # forward x up: nose-down pitch is a negative turn about it
    t = gn.Tree("valora_rz_suspension")
    P, back = gn.placed(t, offset)
    lx, ly, lz = t.xyz(t.object_location(drv))
    piv = t.vec(*pivot)
    rel = t.rotate(t.vmath("SUBTRACT", P, piv), t.vec(*across), t.math("MULTIPLY", lx, -1.0))
    rel = t.rotate(rel, t.vec(fwd[0], fwd[1], 0.0), ly)     # roll about the forward axis: + = right side down
    turned = t.vmath("ADD", rel, piv)
    body = t.vmath("ADD", turned, t.vec(0.0, 0.0, lz))
    t.set_position(back(body), selection=t.equals(t.attr(UNSPRUNG), 0.0))
    ng = t.finish()
    for o in ctx.meshes:
        gn.add_modifier(o, ng, "valora_rz_suspension")
    record("suspension_sag_m", sag)
    record("suspension_keys", len(frames))
    record("suspension_animated", drv.animation_data is not None)
    record("suspension_peak_pitch_rad", max((abs(v) for v in pitch), default=0.0))
    record("suspension_roll_deg_per_g", roll_k)
    record("suspension_peak_roll_rad", max(roll, key=abs, default=0.0))       # signed: + = leaning right
