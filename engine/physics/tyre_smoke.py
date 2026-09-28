"""Pure fit of the library tyre-smoke billow onto a car (phase 6 Task 113, tyre_smoke).

The library preset tyre_smoke_burst (engine/physics/gas.PRESETS) has its two tyre flows at x = LIB_AXLE_X,
y = +-LIB_HALF_TRACK in the preset's base frame (base centre at the origin), blowing toward -x: library +x is the
car's forward. fit() returns the placement engine/blender/vdb.place_vdb needs: yaw (library +x onto the car's
forward at startS), scale (tyre spacing onto the car's rear track, within the x3 guard) and the anchor (the base
point that puts the library's axle midpoint on the car's rear-axle contact midpoint)."""
import math

from engine.motion_path import apply, pose_fn
from engine.physics import vdb as V
from engine.physics.sim_facts import nose_sign

LIB_AXLE_X, LIB_HALF_TRACK = -0.8, 0.8
DENSITY = 6.0            # (eng, G10) Principled density x the grid at density 1 (3.0 read faint, 2026-09-28)


def _forward(profile, markers=None):
    """The unit vector the car's nose points along: sim_facts.nose_sign returns the WORLD sign along the forward
    axis (a front / nose marker decides it at high confidence; without glass parts the measured guess is only the
    axis' own sign, "low": the sports_car eval model's nose is at -y against a +y forwardAxis, so mark the nose)."""
    ax = list((profile.vehicle or {}).get("forwardAxis") or [0.0, 1.0, 0.0])
    i = max(range(3), key=lambda k: abs(ax[k]))
    sign, _ = nose_sign(profile, markers or [])
    out = [0.0, 0.0, 0.0]
    out[i] = float(sign)
    return out


def rear_contacts(profile, markers=None):
    fwd = _forward(profile, markers)
    c = profile.center
    ws = [w for w in (profile.wheels or []) if w.get("contact")]
    rear = [w["contact"] for w in ws if sum((w["contact"][i] - c[i]) * fwd[i] for i in range(3)) < 0]
    return rear or [w["contact"] for w in ws]


def fit(profile, script, catalog, start_s):
    pose_at = pose_fn(script, profile, catalog)
    pose = pose_at(start_s)
    markers = script.get("markers") or []
    rear = rear_contacts(profile, markers)
    pts = [apply(r, pose, profile) for r in rear]
    mid = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    fwd = _forward(profile, markers)
    c = profile.center
    tip = apply([c[0] + fwd[0], c[1] + fwd[1], c[2]], pose, profile)
    base = apply(list(c), pose, profile)
    yaw = math.atan2(tip[1] - base[1], tip[0] - base[0])
    track = max((math.dist(a[:2], b[:2]) for a in pts for b in pts), default=2 * LIB_HALF_TRACK)
    k = track / (2 * LIB_HALF_TRACK) if track > 0 else 1.0
    k = min(V.SCALE_MAX, max(1 / V.SCALE_MAX, k))
    ca, sa = math.cos(yaw), math.sin(yaw)
    ox, oy = k * LIB_AXLE_X, 0.0                     # the library axle midpoint, scaled, before the yaw
    anchor = (mid[0] - (ca * ox - sa * oy), mid[1] - (sa * ox + ca * oy), 0.0)
    return {"anchor": [round(v, 6) for v in anchor], "yawDeg": math.degrees(yaw), "scale": k,
            "axleMid": [round(v, 6) for v in mid], "trackM": track}
