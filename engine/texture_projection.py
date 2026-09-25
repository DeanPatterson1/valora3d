"""World-space PBR projection maths (pure). Realism audit #14: ground textures used world-position XY
coordinates while the Normal Map node still read tangent space from UVs the meshes did not have, and vertical
kerb faces were projected from above (stretched streaks). Here every face picks the axis its normal is closest
to, and gets its own right-handed metric frame (T = +u, B = +v in world space); the node builder decodes the
GL normal map into world space with that frame, so no UVs or tangents are needed.

Anti-tiling: a second sample of every map at uv2 = R(ANTI_TILE_ROT_DEG) uv x ANTI_TILE_SCALE + offset, blended
in by a metre-scale noise, so a 3 m asphalt tile never repeats visibly; its normal is decoded with the rotated
frame (rotated_frame) so both samples light the same way."""
import math

ANTI_TILE_ROT_DEG = 37.0      # (eng) second-sample turn: no lattice realignment for tens of tiles
ANTI_TILE_SCALE = 0.71        # (eng) second-sample scale
ANTI_TILE_OFFSET = (0.37, 0.61)
ANTI_TILE_NOISE_TILES = 2.3   # (eng) blend-noise feature size, in tiles
ANTI_TILE_BAND = (0.42, 0.58)  # (eng) smoothstep of the blend noise: mostly one sample or the other
MACRO_VALUE = (0.88, 1.12)    # (eng) metre-scale albedo wear (render-studio 'Patchy wear albedo' .82-1.16)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dominant_axis(n):
    """0 = x, 1 = y, 2 = z: the axis the (true) face normal is closest to; ties go to z, then y."""
    ax = [abs(c) for c in n]
    if ax[2] >= ax[0] and ax[2] >= ax[1]:
        return 2
    return 1 if ax[1] >= ax[0] else 0


def projection_frame(n):
    """(T, B) unit world vectors for a face with normal n: z faces project XY (T = +-x, B = y), x faces YZ and y
    faces XZ with B = +z (texture up = world up). T's sign makes T x B point along n (never mirrored)."""
    a = dominant_axis(n)
    if a == 2:
        t, b = (1, 0, 0), (0, 1, 0)
    elif a == 0:
        t, b = (0, 1, 0), (0, 0, 1)
    else:
        t, b = (1, 0, 0), (0, 0, 1)
    if dot(cross(t, b), n) < 0:
        t = tuple(-c for c in t)
    return t, b


def face_frame(n, t, b):
    """(T, B) of a projection made tangent to the shading normal n (Gram-Schmidt: T' = T - n(n.T), B' = n x T'),
    the frame the normal map is decoded in, so a tilted face's normal is not skewed toward the projection axis."""
    ln = math.sqrt(dot(n, n))
    n = tuple(c / ln for c in n)
    tp = tuple(ti - ni * dot(n, t) for ti, ni in zip(t, n))
    lt = math.sqrt(dot(tp, tp))
    tp = tuple(c / lt for c in tp)
    bp = cross(n, tp)
    if dot(bp, b) < 0:           # keep texture up on the same side as the projection's B
        bp = tuple(-c for c in bp)
    return tp, bp


def rotated_frame(t, b, theta):
    """World directions of +u2 / +v2 when uv2 = R(theta) uv (R rotates counter-clockwise)."""
    c, s = math.cos(theta), math.sin(theta)
    t2 = tuple(c * ti - s * bi for ti, bi in zip(t, b))
    b2 = tuple(s * ti + c * bi for ti, bi in zip(t, b))
    return t2, b2


def uv_of(p, n, tile_m, rot=0.0, scale=1.0, offset=(0.0, 0.0)):
    """The metric texture coordinate of world point p on a face with normal n (optionally the rotated sample)."""
    t, b = projection_frame(n)
    u, v = dot(p, t) / tile_m, dot(p, b) / tile_m
    c, s = math.cos(rot), math.sin(rot)
    return ((c * u - s * v) * scale + offset[0], (s * u + c * v) * scale + offset[1])
