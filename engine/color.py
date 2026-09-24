"""Colour temperature -> linear-ish RGB for light colours (Tanner Helland fit). Pure. (eng)"""
import math


def kelvin_to_rgb(kelvin):
    t = min(max(float(kelvin), 1000.0), 40000.0) / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255.0 if t >= 66 else 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    c = [min(max(v, 0.0), 255.0) / 255.0 for v in (r, g, b)]
    m = max(c)
    return tuple(v / m for v in c)
