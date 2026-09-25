"""Display-referred sensor grain on the finished frame, AFTER the AgX view transform (and after any resize: the
final frame is written at delivery size), in numpy.

Round 5 (critique mat-v2 #1, 2026-09-25): the earlier port of render-studio's delivery grain (ffmpeg
noise=alls=13, uniform +-13 code values masked into the shadows, ~7 code values std-dev there) was the film's
grain BEFORE its H.264 encode smoothed most of it away; on our lossless PNG frames it read as heavy speckle that
hid detail. The target now is what a clean modern sensor leaves: a luminance std-dev of 0.5-1.0 code values on
0-255 in any flat region (FILM_SIGMA at black falling to HIGHLIGHT_SIGMA at white), Gaussian, with low chroma
(CHROMA_SHARE of the luma std-dev, at half resolution as in a 4:2:0 frame). Fresh every frame, the same for the
same (seed, frame).

Pure numpy: `apply_grain(rgb, amount, seed, frame)` takes and returns float RGB in [0, 1] display space."""
import hashlib

import numpy as np

AMOUNT_PER_FILM = 0.5         # the grade's grain param: 0.5 = the camera's own grain (grade_plan.CAMERA_FINISH)
FILM_SIGMA = 0.9              # code values (0-255) of luma std-dev in flat shadows at amount 0.5
HIGHLIGHT_SIGMA = 0.5         # ... falling linearly to this at white (a sensor's highlights are cleaner)
CHROMA_SHARE = 0.25           # chroma std-dev as a share of the luma std-dev (low chroma)
KR, KB = 0.2126, 0.0722       # BT.709 luma


def sigma_for(amount, luma):
    """Luma std-dev (code values) of the grain at a display luma in [0, 1] for a grade grain amount."""
    k = float(amount) / AMOUNT_PER_FILM
    return k * (FILM_SIGMA + (HIGHLIGHT_SIGMA - FILM_SIGMA) * np.clip(luma, 0.0, 1.0))


def _rng(seed, frame):
    h = hashlib.sha256(f"grain:{int(seed)}:{int(frame)}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def apply_grain(rgb, amount, seed, frame):
    """The frame with sensor grain; identity at amount 0. Same (seed, frame) -> the same grain."""
    if amount <= 0:
        return rgb
    img = np.asarray(rgb, np.float64)
    h, w = img.shape[:2]
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    y = KR * r + (1 - KR - KB) * g + KB * b
    cb = (b - y) / (2 * (1 - KB))
    cr = (r - y) / (2 * (1 - KR))
    rng = _rng(seed, frame)
    s = sigma_for(amount, y) / 255.0
    ny = rng.standard_normal((h, w)) * s
    hc, wc = (h + 1) // 2, (w + 1) // 2
    nc = rng.standard_normal((2, hc, wc)).repeat(2, axis=1).repeat(2, axis=2)[:, :h, :w]
    y = y + ny
    cb = cb + nc[0] * s * CHROMA_SHARE
    cr = cr + nc[1] * s * CHROMA_SHARE
    r = y + 2 * (1 - KR) * cr
    b = y + 2 * (1 - KB) * cb
    g = (y - KR * r - KB * b) / (1 - KR - KB)
    return np.clip(np.stack([r, g, b], axis=-1), 0.0, 1.0)
