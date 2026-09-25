"""One wind per clip (TAXONOMY WD-01; METHODS §2.9). Every wind-driven block reads the same field so
rain, smoke, leaves and foliage can never disagree. Direction: the world azimuth the air moves
TOWARD, degrees counter-clockwise from +x. Speed in m/s, Beaufort-anchored (0-14 m/s = force 0-6).

The Blender field (engine/blocks/field/wind/build.py) is mean * (1 + gustiness * g(p, t)) + turbulence
terms, with g a noise in [-1, 1] advected downwind; its speed stays inside envelope()."""
import math

BEAUFORT_UPPER = (0.5, 1.5, 3.3, 5.5, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6)   # upper speed of force 0..11 (m/s); above: 12
CALM_MS = 0.3            # below this nothing visibly moves (inside Beaufort 0) (eng)
GUST_WAVELENGTH_M = 12.0  # spatial size of a gust front (eng)
TURB_SCALE_M = 1.5       # spatial size of turbulent eddies (eng)


def vector(direction_deg, speed):
    a = math.radians(direction_deg)
    return (speed * math.cos(a), speed * math.sin(a), 0.0)


def beaufort(speed):
    return next((i for i, u in enumerate(BEAUFORT_UPPER) if speed <= u), len(BEAUFORT_UPPER))


def envelope(speed, gustiness):
    return max(0.0, speed * (1.0 - gustiness)), speed * (1.0 + gustiness)


def is_calm(speed):
    return speed < CALM_MS
