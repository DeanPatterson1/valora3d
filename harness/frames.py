"""Load a rendered case's key frames and eval passes (Task 24 layout) into metrics.Frame objects."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

from engine.compiler.timeline import shot_index
from harness.metrics import Frame, _shot_param as _param


def _pass(case_dir, name, f):
    hit = sorted((Path(case_dir) / "passes").glob(f"{name}*{f:04d}*.png"))
    return hit[0] if hit else None


def _read_mask(path, shape):
    if path is None:
        return np.zeros(shape, bool)
    return np.asarray(Image.open(path).convert("L")) > 127


def _read_mist(path):
    if path is None:
        return None
    im = Image.open(path)
    a = np.asarray(im).astype(np.float32)
    top = 65535.0 if im.mode.startswith("I") else 255.0
    return a / top


def load_frames(case_dir, script, catalog):
    case_dir = Path(case_dir)
    log = json.loads((case_dir / "render_log.json").read_text(encoding="utf-8"))
    fps, shots = script["format"]["fps"], script["shots"]
    out = []
    for f in sorted(e["frame"] for e in log["frames"]):
        rgb = np.asarray(Image.open(case_dir / "beauty" / f"{f:04d}.png").convert("RGB"), dtype=np.float32) / 255.0
        mask = _read_mask(_pass(case_dir, "mask", f), rgb.shape[:2])
        gloss = _read_mask(_pass(case_dir, "gloss", f), rgb.shape[:2]) & mask  # TIERS: subject pixels only
        t = (f - 1) / fps
        i = shot_index(shots, t)
        out.append(Frame(frame=f, t=t, shot=i, lens=_param(shots[i], catalog, "lensMm"),
                         fstop=_param(shots[i], catalog, "fstop"), rgb=rgb, mask=mask, gloss=gloss,
                         mist=_read_mist(_pass(case_dir, "mist", f))))
    return out
