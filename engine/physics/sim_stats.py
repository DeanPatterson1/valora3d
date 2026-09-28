"""Sim hygiene rules (phase 6 Task 99; research/physics BLOCKS §5 compile probes, PH-03 / PH-04). Pure: the
Blender side (engine/blender/sim_probe.py) gathers positions, inside flags, edge lengths and volumes; these
functions judge them. Every threshold is (eng) and REPORT-ONLY until good and bad bakes separate on real blocks
(PHASING: thresholds before gating); nothing here fails a compile.

- no_particles_in_subject: points (or piece centres) inside the collision shell <= 0.1% of the points;
- sim_stable: no NaN / inf; max speed <= 3 x the block's bake.maxSpeedMs; rigid: the kinetic energy of the last
  10% of frames <= 1% of its peak; cloth: max edge stretch <= 2.5 x rest; liquid: mesh volume within 15% of
  its value when the inflow stops."""
import math

INSIDE_MAX = 0.001
SPEED_X = 3.0
KE_TAIL = 0.10
KE_MAX = 0.01
STRETCH_MAX = 2.5
VOLUME_MAX = 0.15


def _finite(frames):
    return all(math.isfinite(c) for fr in frames for p in fr for c in p)


def speeds(frames, fps):
    """Per frame step, per point speed (m/s): |p[f+1] - p[f]| x fps. Points must keep their order."""
    out = []
    for a, b in zip(frames, frames[1:]):
        out.append([math.dist(p, q) * fps for p, q in zip(a, b)])
    return out


def rigid_verdict(frames, fps, max_speed_ms):
    """frames: [[(x, y, z) per piece] per frame]. Kinetic energy is sum v^2 (unit masses; only its ratio counts)."""
    if not frames:
        return {"finite": True, "ok": True, "maxSpeedMs": 0.0, "keTailRatio": 0.0, "frames": 0}
    if not _finite(frames):
        return {"finite": False, "ok": False, "maxSpeedMs": None, "keTailRatio": None, "frames": len(frames)}
    sp = speeds(frames, fps)
    vmax = max((v for row in sp for v in row), default=0.0)
    ke = [sum(v * v for v in row) for row in sp]
    peak = max(ke, default=0.0)
    tail = ke[-max(1, int(math.ceil(KE_TAIL * len(ke)))):] if ke else []
    ratio = (sum(tail) / len(tail) / peak) if peak > 0 and tail else 0.0
    ok = vmax <= SPEED_X * max_speed_ms and ratio <= KE_MAX
    return {"finite": True, "ok": ok, "maxSpeedMs": round(vmax, 6), "keTailRatio": round(ratio, 6),
            "frames": len(frames), "speedCapMs": SPEED_X * max_speed_ms}


def inside_verdict(flags):
    n = len(flags)
    k = sum(1 for f in flags if f)
    share = k / n if n else 0.0
    return {"points": n, "inside": k, "share": round(share, 6), "ok": share <= INSIDE_MAX}


def cloth_stretch(rest, now):
    """Edge lengths at rest and now (same order): the worst ratio."""
    worst = max((b / a for a, b in zip(rest, now) if a > 0), default=1.0)
    return {"maxStretch": round(worst, 6), "ok": worst <= STRETCH_MAX}


def liquid_volume(volumes):
    """Mesh volumes from the frame the inflow stops on: the worst relative change from the first."""
    if not volumes or volumes[0] <= 0:
        return {"maxChange": None, "ok": False}
    worst = max(abs(v - volumes[0]) / volumes[0] for v in volumes)
    return {"maxChange": round(worst, 6), "ok": worst <= VOLUME_MAX}
