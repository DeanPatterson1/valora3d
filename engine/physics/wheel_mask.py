"""Which pieces of a wheel spin and which vertices are tyre (METHODS §2.1 CD-02, §3). One rule for ingest
(island summaries) and the compiler (vertex arrays). Placed coordinates; wheels as SubjectProfile.wheels."""
import math

RADIAL_MAX = 1.05       # x r: a wheel piece lies within the tyre's outer radius (+5% for tread noise)
AXIAL_MARGIN = 0.05     # x r beyond the half width
SPIN_AXIS_TOL = 0.05    # x r: a spinning piece is round, so its centroid sits on the axle (a caliper does not)
BAND_SLACK = 0.02       # x r below tyreBand[0]
DEFAULT_BAND = (0.62, 1.0)   # METHODS CD-02 "tyre ring r in [0.62 r, 1.0 r]"
DEFAULT_HALF_WIDTH = 0.3     # x r when ingest measured no width (eng)


def _frame(w):
    ai = max(range(3), key=lambda k: abs(w["axis"][k]))
    return ai, [k for k in range(3) if k != ai]


def half_width(w):
    return 0.5 * w["width"] if w.get("width") else DEFAULT_HALF_WIDTH * w["radius"]


def in_wheel_box(lo, hi, w):
    """The axis-aligned box of a piece fits inside the wheel's cylinder box (tyre, rim, disc, caliper)."""
    ai, rad = _frame(w)
    c, r = w["center"], w["radius"]
    hw = half_width(w) + AXIAL_MARGIN * r
    return (lo[ai] >= c[ai] - hw and hi[ai] <= c[ai] + hw
            and all(lo[k] >= c[k] - RADIAL_MAX * r and hi[k] <= c[k] + RADIAL_MAX * r for k in rad))


def island_spins(lo, hi, centroid, w):
    ai, rad = _frame(w)
    off = math.hypot(*(centroid[k] - w["center"][k] for k in rad))
    return in_wheel_box(lo, hi, w) and off <= SPIN_AXIS_TOL * w["radius"]


def tyre_weight(p, w):
    """1 when p is in the tyre band (rubber ring within the tyre's width), else 0."""
    ai, rad = _frame(w)
    r = w["radius"]
    rho = math.hypot(*(p[k] - w["center"][k] for k in rad))
    inner = (w.get("tyreBand") or DEFAULT_BAND)[0]
    return int((inner - BAND_SLACK) * r <= rho <= RADIAL_MAX * r
               and abs(p[ai] - w["center"][ai]) <= half_width(w) + AXIAL_MARGIN * r)


def tyre_mask(points, w):
    """Vectorised tyre_weight for an (n, 3) numpy array (Blender side and host tests)."""
    import numpy as np
    ai, rad = _frame(w)
    r = w["radius"]
    c = np.asarray(w["center"], dtype=np.float64)
    rho = np.hypot(points[:, rad[0]] - c[rad[0]], points[:, rad[1]] - c[rad[1]])
    inner = (w.get("tyreBand") or DEFAULT_BAND)[0]
    return ((rho >= (inner - BAND_SLACK) * r) & (rho <= RADIAL_MAX * r)
            & (np.abs(points[:, ai] - c[ai]) <= half_width(w) + AXIAL_MARGIN * r))
