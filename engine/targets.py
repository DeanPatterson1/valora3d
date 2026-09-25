"""Resolve a shot's detail target to a point and normal in placed coordinates."""
import math
from dataclasses import dataclass

DEFAULT_NORMAL = (0.0, -0.957826, 0.287348)  # unit (0, -1, 0.3): side-on, slightly above
SURFACE_TUBE_CELLS = 1.5   # ray "hits" a surface sample within this many sample cells (longest / 40) of it
SURFACE_OFFSET = 0.002     # x longest: the aim point sits this far out along the camera direction, off the skin


@dataclass(frozen=True)
class Target:
    point: tuple
    normal: tuple
    source: str  # "marker:<id>" | "detail:<i>" | "surface"


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v) if n > 0 else DEFAULT_NORMAL


def resolve_target(shot, profile, markers):
    """Marker, then detail point, then the surface point facing the default camera direction. None if the reference does not exist."""
    t = shot.get("target")
    if isinstance(t, dict) and "marker" in t:
        m = next((m for m in markers if m.get("id") == t["marker"]), None)
        if m is None:
            return None
        p = tuple(m["anchor"]["point"])
        n = m["anchor"].get("normal") or [a - b for a, b in zip(p, profile.center)]
        return Target(p, _unit(n), f"marker:{t['marker']}")
    if isinstance(t, dict) and "detail" in t:
        i = t["detail"]
        if i >= len(profile.detailPoints):
            return None
        d = profile.detailPoints[i]
        return Target(tuple(d["point"]), _unit(d["normal"]), f"detail:{i}")
    return Target(surface_point(profile, DEFAULT_NORMAL), DEFAULT_NORMAL, "surface")


def surface_point(profile, direction):
    """Where a ray from outside the subject along -direction toward its bbox centre first meets the surface:
    the outermost recorded surface sample within a thin tube around that ray (widened until one is found),
    nudged out along `direction`. Without samples, the bbox face the ray enters through. Deterministic.
    The bbox centre of a solid subject is inside the mesh: aiming a close-up there fails camera clearance."""
    from engine.ingest.measure import SURFACE_CELLS
    c, n, size = profile.center, direction, max(profile.longest, 1e-9)
    pts = profile.surfaceSamples or []
    if pts:
        tube = SURFACE_TUBE_CELLS * size / SURFACE_CELLS
        rel = [[a - b for a, b in zip(p, c)] for p in pts]
        along = [sum(a * b for a, b in zip(r, n)) for r in rel]
        perp = [math.sqrt(max(0.0, sum(a * a for a in r) - t * t)) for r, t in zip(rel, along)]
        while tube <= 2.0 * size:
            hits = [(t, -i) for i, (t, d) in enumerate(zip(along, perp)) if d <= tube]
            if hits:
                i = -max(hits)[1]
                return tuple(round(pts[i][k] + n[k] * SURFACE_OFFSET * size, 6) for k in range(3))
            tube *= 2.0
    h = profile.half
    t = min((h[k] / abs(n[k]) for k in range(3) if abs(n[k]) > 1e-12), default=0.0)
    return tuple(round(c[k] + n[k] * t, 6) for k in range(3))
