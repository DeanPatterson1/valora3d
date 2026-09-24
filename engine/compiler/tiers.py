"""Render tiers (spec §4.7). `keyframes` exists for tests and eval only. Preview = composition and
motion in minutes. Final = the paid clip. Sample counts are (eng): the final default follows the
engine survey's measured 192 spp baseline, and the spec's open question 2 (price per clip) may
change it."""
from engine.geometry import aspect_wh

SHUTTER = 0.5  # 180 degrees, centred (TIERS T2-05)

TIERS = {
    "keyframes": {"shortSide": 144, "samples": 4, "denoise": True, "passes": True},
    "preview": {"shortSide": 540, "samples": 16, "denoise": True, "passes": True},
    "final": {"shortSide": 1080, "samples": 192, "denoise": True, "passes": False},
}


def _even(x):
    x = int(round(x))
    return x + (x % 2)


def resolution(aspect, short_side):
    w, h = aspect_wh(aspect)
    if w <= h:
        return _even(short_side), _even(short_side * h / w)
    return _even(short_side * w / h), _even(short_side)
