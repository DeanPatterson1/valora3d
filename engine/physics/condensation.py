"""Pure maths for `condensation` (phase 6 Task 104, FL-05; its build.py does the Geometry Nodes).

A cold container sweats below its fill line (the liquid inside chills the wall; the dry shoulder above it stays
clear, P-M03): micro-droplets at 20-60 per cm2, real size 0.2-1.5 mm across (most of them small), on every face
that does not face down, over a thin fogged film (a rough, faintly white water layer a hair off the surface).
Nothing of the upload is modified: droplets and film are separate objects that read the upload's meshes."""

DENSITY_CM2 = (20.0, 60.0)      # P-M03 / METHODS FL-05
SIZE_MM = (0.2, 1.5)            # real size, across
SIZE_SKEW = 2.0                 # u ** 2: most micro-droplets sit at the small end (eng)
DOWN_NZ = -0.05                 # a face whose normal points down drips, it does not bead
FILM_M = 0.00015                # the fog film floats 0.15 mm off the surface (above the ray offset, under a drop)
MAX_DROPS = 400_000             # an instance cap by cost; a hand-size container needs ~15-45k


def per_m2(density_cm2):
    return float(density_cm2) * 1e4


def size_m(u):
    """The diameter (m) for a uniform draw u in [0, 1]."""
    lo, hi = SIZE_MM
    return (lo + (hi - lo) * u ** SIZE_SKEW) / 1000.0


def expected_count(area_m2, density_cm2):
    return int(round(area_m2 * per_m2(density_cm2)))


def effective_per_m2(area_m2, density_cm2):
    """The density the build uses: the asked one, capped so area x density <= MAX_DROPS."""
    d = per_m2(density_cm2)
    return min(d, MAX_DROPS / area_m2) if area_m2 > 0 else d


def in_zone(n, z, fill_z):
    """A surface point (unit normal n, height z) beads when it is below the fill line and not facing down."""
    return z <= fill_z and n[2] > DOWN_NZ
