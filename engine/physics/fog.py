"""ground_fog pure maths (phase 5 Task 60; port of render-studio rain_look.distance_fog, generalised).

render-studio: a 260 x 260 x 15 m cube with a Boolean cylinder "clear pocket" (radius max(8 m, farthest
camera) + 1.5 m), homogeneous density 0.0040 /m, anisotropy 0.35. Here:
- the domain is FOG_EXTENT x max(subject longest, farthest camera distance) wide (METHODS R5);
- the height is heightM, real metres (a low fog), density exp(-z / heightM), fading to zero at
  TOP_K x heightM so the domain's top face never shows;
- the pocket is a density falloff in the shader (no mesh Boolean): 0 inside POCKET x radius, 1 from twice
  that, smoothstep between;
- density is REAL per metre (sigma = density x FOG_SIGMA at the ground): low fog is a real-world layer,
  so on a tabletop subject it stays a thin veil instead of burying the set (unlike haze_volume, whose
  density is normalised to the subject radius).
Every number here is (eng) until the Task 60 look-check (calibration register)."""
import math

FOG_EXTENT = 6.0     # domain width, x max(longest, farthest camera) (eng)
POCKET = 1.5         # clear pocket radius, x subject radius (eng)
FOG_SIGMA = 0.12     # extinction per metre at the ground at density 1 (eng; render-studio 0.004 was a 260 m set)
TOP_K = 5.0          # the domain top sits at 5 x heightM, where exp(-5) = 0.7 % (then faded to zero)
EDGE_FADE = 0.8      # full density out to 80 % of the half-width, zero at the domain's side faces
MIST_HEIGHT_K = 3.0  # mist: a whole-set low-contrast veil (eng)
MIST_DENSITY_K = 0.4
ANISOTROPY = 0.35    # render-studio's forward scatter


def fog_density(z, height_m, density):
    """Extinction per metre at height z above the ground (below the ground: the ground value)."""
    return density * FOG_SIGMA * math.exp(-max(0.0, z) / height_m)


def _smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def pocket_weight(dist, radius):
    """0 inside `radius`, 1 from 2 x radius, smoothstep between."""
    return _smoothstep(radius, 2.0 * radius, dist)


def mode_params(mode, height_m, density):
    """(height, density) the volume uses: mist is MIST_HEIGHT_K x higher and MIST_DENSITY_K x as dense."""
    if mode == "mist":
        return height_m * MIST_HEIGHT_K, density * MIST_DENSITY_K
    return height_m, density


def domain_width(longest, farthest_camera):
    return FOG_EXTENT * max(longest, farthest_camera)


def domain_height(height_m):
    return TOP_K * height_m


def pocket_radius(radius):
    return POCKET * radius
