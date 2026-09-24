"""Colour temperature -> RGB for light colours (Tanner Helland fit). Pure. (eng)
The fit is display-referred sRGB; Blender light colours are scene-linear, so light consumers
(engine/blender/lights.py) use kelvin_to_rgb, which returns linear."""
import math


def srgb_to_linear(v):
    """IEC 61966-2-1 sRGB decode, one channel in [0, 1]."""
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def kelvin_to_srgb(kelvin):
    """sRGB-encoded black-body colour at `kelvin`, normalised so the largest channel is 1."""
    t = min(max(float(kelvin), 1000.0), 40000.0) / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255.0 if t >= 66 else 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    c = [min(max(v, 0.0), 255.0) / 255.0 for v in (r, g, b)]
    m = max(c)
    return tuple(v / m for v in c)


def kelvin_to_rgb(kelvin):
    """Scene-linear RGB (largest channel 1) for a Blender light colour."""
    return tuple(srgb_to_linear(v) for v in kelvin_to_srgb(kelvin))
