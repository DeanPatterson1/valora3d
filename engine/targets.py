"""Resolve a shot's detail target to a point and normal in placed coordinates."""
import math
from dataclasses import dataclass

DEFAULT_NORMAL = (0.0, -0.957826, 0.287348)  # unit (0, -1, 0.3): side-on, slightly above


@dataclass(frozen=True)
class Target:
    point: tuple
    normal: tuple
    source: str  # "marker:<id>" | "detail:<i>" | "centre"


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v) if n > 0 else DEFAULT_NORMAL


def resolve_target(shot, profile, markers):
    """Marker, then detail point, then subject centre. None if the reference does not exist."""
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
    return Target(tuple(profile.center), DEFAULT_NORMAL, "centre")
