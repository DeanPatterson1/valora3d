"""Display-referred sensor grain: render-studio's delivery grain (tools/render-studio/pipeline.py:152,
GRAIN_FILTER) re-done in numpy on the finished frame, AFTER the AgX view transform, as the film had it.

ffmpeg's chain was: noise=alls=13:allf=t+u (uniform noise of +-13 code values on Y, U and V, fresh every frame)
merged into the clean frame through a lutyuv mask y = clip(250 - 1.35 Y, 45, 250), u = v = 110 (maskedmerge:
out = a + (noisy - a) x mask / 255), so shadows carry most of the grain and highlights stay clean, as on a real
sensor. The frame is yuv420p there, so chroma noise lives at half resolution. The engine's earlier compositor
grain ran scene-linear before AgX with a gamma-slope guess (realism audit #20); this replaces it.

Pure numpy: `apply_grain(rgb, amount, seed, frame)` takes and returns float RGB in [0, 1] display space."""
import hashlib

import numpy as np

FILM_STRENGTH = 13            # ffmpeg alls=13, the film's grain
AMOUNT_PER_FILM = 0.5         # the grade's grain param: 0.5 = the film (engine/grade_plan.GRAIN_AMP comment)
MASK_Y = (250.0, 1.35, 45.0)  # lutyuv y = clip(250 - 1.35 val, 45, 250)
MASK_UV = 110.0               # lutyuv u = v = 110
KR, KB = 0.2126, 0.0722       # BT.709 luma


def strength_for(amount):
    """Code values of uniform noise (+-) for a grade grain amount."""
    return FILM_STRENGTH * float(amount) / AMOUNT_PER_FILM


def _rng(seed, frame):
    h = hashlib.sha256(f"grain:{int(seed)}:{int(frame)}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def apply_grain(rgb, amount, seed, frame):
    """The frame with sensor grain; identity at amount 0. Same (seed, frame) -> the same grain."""
    if amount <= 0:
        return rgb
    s = strength_for(amount) / 255.0
    img = np.asarray(rgb, np.float64)
    h, w = img.shape[:2]
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    y = KR * r + (1 - KR - KB) * g + KB * b
    cb = (b - y) / (2 * (1 - KB))
    cr = (r - y) / (2 * (1 - KR))
    rng = _rng(seed, frame)
    ny = rng.uniform(-s, s, (h, w))
    hc, wc = (h + 1) // 2, (w + 1) // 2
    nc = rng.uniform(-s, s, (2, hc, wc)).repeat(2, axis=1).repeat(2, axis=2)[:, :h, :w]
    m_y = np.clip(MASK_Y[0] - MASK_Y[1] * y * 255.0, MASK_Y[2], MASK_Y[0]) / 255.0
    y = y + ny * m_y
    cb = cb + nc[0] * (MASK_UV / 255.0)
    cr = cr + nc[1] * (MASK_UV / 255.0)
    r = y + 2 * (1 - KR) * cr
    b = y + 2 * (1 - KB) * cb
    g = (y - KR * r - KB * b) / (1 - KR - KB)
    return np.clip(np.stack([r, g, b], axis=-1), 0.0, 1.0)
