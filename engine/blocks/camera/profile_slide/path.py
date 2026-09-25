"""profile_slide (phase 5 Task 83, CATALOG-GAPS rank 13): a lateral truck at a profile angle.

The long axis L is the subject's longer horizontal side. The camera sits at distance x radius on the bearing
angleDeg from L (90 = the side profile, V-C04), on the `side` of L, at heightFrac x height (V-C04: door-handle
height ~0.45 H), and trucks along L by slideFrac x length, eased; the target shifts in parallel, so the view
direction and the angle never change.

foreground(params, profile, outdoor) (F-C08 / P-C09 / P-C10): an out-of-focus foreground post, a vertical card
standing on the ground at FG_DEPTH x the mid-shot camera distance from the lens and FG_SIDE of the way to the
frame's right edge. It is static in the world, so the truck moves it across the frame 1 / FG_DEPTH ~ 3x as far
as the subject (>= 2x parallax). None when not asked, in a world without outdoor props (the studio), or when
it would stand inside the subject's bounds + margin or not in front of it. Deviation from the plan text: the
card is one generic post silhouette, not a prop from the world's list (no world exposes a prop list)."""
import math

from engine.easing import ease, settle
from engine.geometry import SENSOR_MM, Pose, _basis, point_in_box

MIN_HEIGHT_M = 0.03
FG_DEPTH = 0.3        # plan: the card at 0.3 x the camera distance (P-C09: 0.1-0.3)
FG_SIDE = 0.7         # (eng) share of the way to the frame edge (portrait-safe: of the short side)
FG_WIDTH = 0.12       # (eng) card width as a share of the frame's short side at its depth
FG_OVER = 1.2         # (eng) the card rises this far past the frame top (a post, not a stub)
BOX_MARGIN = 0.10     # = checker.BOX_MARGIN


def long_axis(profile):
    return (1.0, 0.0) if profile.sizeM[0] >= profile.sizeM[1] else (0.0, 1.0)


def _view(params, profile):
    lx, ly = long_axis(profile)
    s = 1.0 if params["side"] == "right" else -1.0
    a = math.radians(params["angleDeg"])
    return (lx, ly), (math.cos(a) * lx - s * math.sin(a) * ly, math.cos(a) * ly + s * math.sin(a) * lx)


def sample(params, profile, u, target=None):
    cx, cy, cz = profile.center
    (lx, ly), (dx, dy) = _view(params, profile)
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    o = (k - 0.5) * params["slideFrac"] * profile.longest
    d = params["distance"] * profile.radius
    z = max(MIN_HEIGHT_M, params["heightFrac"] * profile.sizeM[2])
    return Pose(position=(cx + d * dx + o * lx, cy + d * dy + o * ly, z),
                target=(cx + o * lx, cy + o * ly, cz), lens_mm=params["lensMm"])


def foreground(params, profile, outdoor=True):
    if not params.get("foreground") or not outdoor:
        return None
    mid = sample(params, profile, 0.5)
    fwd, right, up = _basis(mid)
    reach = math.dist(mid.position, mid.target)
    depth = FG_DEPTH * reach
    half = (SENSOR_MM / 2.0) / mid.lens_mm * depth               # frame half-extent (long side) at the card
    short = half * 9.0 / 16.0                                   # the short side of a portrait/landscape frame
    rh = math.hypot(right[0], right[1]) or 1.0
    rx, ry = right[0] / rh, right[1] / rh                       # horizontal right: the card stands upright
    c = [mid.position[i] + fwd[i] * depth for i in range(3)]
    c[0] += rx * FG_SIDE * short
    c[1] += ry * FG_SIDE * short
    w = FG_WIDTH * 2.0 * short
    top = max(0.0, c[2]) + half * FG_OVER
    corners = [(c[0] + sx * rx * w / 2, c[1] + sx * ry * w / 2, z) for sx in (-1, 1) for z in (0.0, top)]
    centre = (c[0], c[1], top / 2)
    near = min(sum((q[i] - mid.position[i]) * fwd[i] for i in range(3))
               for q in _box(profile.boundsMin, profile.boundsMax))
    far = max(sum((q[i] - mid.position[i]) * fwd[i] for i in range(3)) for q in corners)
    if far >= near or any(point_in_box(q, profile.boundsMin, profile.boundsMax, BOX_MARGIN) for q in corners + [centre]):
        return None
    return {"kind": "post", "center": centre, "corners": corners, "width": w, "height": top,
            "normal": (-fwd[0], -fwd[1], 0.0)}


def _box(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
