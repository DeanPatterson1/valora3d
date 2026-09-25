"""Fallen leaves, pure: render-studio's folded, curled, twisted ovate leaf (rain_scene.py:337 LEAF_PROFILE,
:340 leaf_mesh), generalised to plain tuples.

Each leaf is len(LEAF_PROFILE) rows of three vertices (left edge, midrib, right edge) along its midrib, joined
by quads. fold raises the edges into a V along the midrib, curl lifts the tips off the road (negative: the
middle arches), twist tilts one half up and the other down. One change from render-studio: the finished leaf
is lifted so its lowest vertex rests REST_M above the road. render-studio set the midrib's centre there, so a
negative curl or a strong twist pushed tips and edges up to a centimetre into the asphalt."""
import math

# Half outline of a pointed ovate leaf: (position along the midrib 0..1, half width 0..1).
LEAF_PROFILE = ((0.0, 0.0), (.12, .55), (.32, .92), (.55, 1.0), (.76, .72), (.92, .34), (1.0, 0.0))
REST_M = 0.0015          # render-studio's 1.5 mm stand-off from the road


def shape(rng):
    """(fold, curl, twist) drawn over render-studio's ranges."""
    return rng.uniform(.05, .32), rng.uniform(-.10, .28), rng.uniform(-.10, .10)


def leaf(xy, yaw_deg, half_width, length, fold, curl, twist, z0=0.0):
    """(verts, quads) of one leaf centred at xy, midrib along yaw_deg; the lowest vertex at z0 + REST_M."""
    a = math.radians(yaw_deg)
    dx, dy = math.cos(a), math.sin(a)
    sx, sy = dy, -dx                                         # render-studio: side = direction x up
    verts, faces = [], []
    for along, half in LEAF_PROFILE:
        cx = xy[0] + dx * (along - .5) * length
        cy = xy[1] + dy * (along - .5) * length
        lift = curl * length * (2 * along - 1) ** 2
        for sign in (-1, 0, 1):
            off = sign * half * half_width
            rise = abs(sign) * half * half_width * (fold + twist * sign) + lift
            verts.append((cx + sx * off, cy + sy * off, rise))
    base = min(v[2] for v in verts)
    verts = [(x, y, z - base + z0 + REST_M) for x, y, z in verts]
    for r in range(len(LEAF_PROFILE) - 1):
        a0, b0 = 3 * r, 3 * (r + 1)
        for k in (0, 1):
            faces.append((a0 + k, a0 + k + 1, b0 + k + 1, b0 + k))
    return verts, faces
