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


def resolution(aspect, short_side):
    """Width and height that are both even (video encoders need it), keep the aspect exactly
    (w * ah == h * aw) and never fall below short_side: the smallest k with k * min(aw, ah) >=
    short_side, k even whenever aw or ah is odd (4:5 at 540 -> 544 x 680)."""
    w, h = aspect_wh(aspect)
    step = 1 if w % 2 == 0 and h % 2 == 0 else 2
    k = -(-short_side // (min(w, h) * step)) * step
    return w * k, h * k
