"""TIERS [M] items on rendered key frames. Display-referred sRGB in [0, 1] (the thresholds in
TIERS.md are display values). Every threshold comes from harness/thresholds.json; report-only.

Each item function returns (value, ok): ok is True / False, or None when the item does not apply
to that frame."""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion  # skimage's versions go away in 0.28
from skimage.measure import label, regionprops
from skimage.morphology import disk  # pass as structure=disk(r)

from engine.craft_rules import VEHICLE_SIZE_M, ItemResult

MIN_GLOSS_SHARE = 0.005  # below this the gloss items do not apply (too few pixels to read)
UNMEASURED_V0 = {
    "B-03": "flicker needs dense frames and optical flow (phase 6 full-preview QC)",
    "T3-12": "smoothness needs dense frames and optical flow (phase 6)",
    "T3-17": "motivated cut needs flow across cuts (phase 6)",
    "T4-04": "grain and halation realism not measured in v0",
}
DENSE_FRAME_ITEMS = frozenset({"B-03", "T3-12", "T3-17"})  # need every frame (flow); key frames never can


@dataclass
class Frame:
    frame: int
    t: float
    shot: int
    lens: float
    fstop: float
    rgb: np.ndarray            # H x W x 3 float32
    mask: np.ndarray           # subject (object index 1)
    gloss: np.ndarray          # TIERS gloss mask: subject pixels on gloss materials
    mist: np.ndarray | None    # 0 near .. 1 far


def lum(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def srgb_to_lab(rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def box_mean(img, r):
    p = np.pad(img, r, mode="edge")
    c = np.pad(np.cumsum(np.cumsum(p, 0), 1), ((1, 0), (1, 0)))
    k = 2 * r + 1
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def laplacian(L):
    out = np.zeros_like(L)
    out[1:-1, 1:-1] = 4 * L[1:-1, 1:-1] - L[:-2, 1:-1] - L[2:, 1:-1] - L[1:-1, :-2] - L[1:-1, 2:]
    return out


def sharpness(L, region):
    v = laplacian(L)[region]
    return float(v.var()) if v.size >= 50 else None


def _gloss_ok(fd):
    return fd.gloss.sum() >= MIN_GLOSS_SHARE * fd.gloss.size


def _ratio(a, b):
    if a is None or b is None:
        return None
    return a / b if b > 0 else (float("inf") if a > 0 else 0.0)


def b01(fd, th):
    v = float(lum(fd.rgb).mean())
    return v, bool(v > th["minMeanLum"] and fd.mask.any())


def b02(fd, th, black_world):
    L = lum(fd.rgb)
    bright = float((L >= th["bright"]).mean())
    region = L[fd.mask] if black_world else L
    dark = float((region <= th["dark"]).mean()) if region.size else 0.0
    return {"bright": bright, "dark": dark}, bool(bright < th["maxBrightShare"] and dark < th["maxDarkShare"])


def b05(fd, th):
    if not fd.mask.any():
        return 0.0, False
    ys, xs = np.nonzero(fd.mask)
    h, w = fd.mask.shape
    v = max((xs.max() - xs.min() + 1) / w, (ys.max() - ys.min() + 1) / h)
    return float(v), bool(v >= th["minCoverage"])


def t1x2(fd, th):
    L = lum(fd.rgb)
    bg = ~fd.mask
    if not bg.any():
        return None, None
    std = float(L[bg].std())
    shadow = False
    if fd.mask.any():
        ys, xs = np.nonzero(fd.mask)
        y0, y1 = ys.max() + 1, min(L.shape[0], ys.max() + 1 + max(1, int(round(0.05 * L.shape[0]))))
        strip = L[y0:y1, xs.min():xs.max() + 1]
        shadow = bool(strip.size and strip.mean() < th["shadowRatio"] * np.median(L[bg]))
    return std, bool(not (std < th["minBgStd"] and not shadow))


def t202(fd, th):
    if not _gloss_ok(fd):
        return None, None
    v = float(lum(fd.rgb)[fd.gloss].std())
    return v, bool(v >= th["minGlossStd"])


def t206(fd, th):
    if fd.fstop > th["maxFstop"]:
        return None, None
    L = lum(fd.rgb)
    r = _ratio(sharpness(L, fd.mask), sharpness(L, ~fd.mask))
    return (None, None) if r is None else (r, bool(r >= th["minRatio"]))


def t207(fd, th):
    if fd.mist is None:
        return None, None
    bg = ~fd.mask
    if not bg.any():
        return None, None
    p30, p70 = np.percentile(fd.mist[bg], [30, 70])
    near, far = bg & (fd.mist <= p30), bg & (fd.mist >= p70)
    if not near.any() or not far.any():
        return None, None
    L = lum(fd.rgb)
    lc = np.abs(L - box_mean(L, 4))
    r = _ratio(float(lc[far].mean()), float(lc[near].mean()))
    return r, bool(r <= th["maxFarNearRatio"])


def t303m(fd, th):
    mk = fd.mask
    touches = bool(mk[0].any() or mk[-1].any() or mk[:, 0].any() or mk[:, -1].any())
    area = float(mk.mean())
    return area, bool(touches or area >= th["minDetailCoverage"])


def t306(fd, th, vehicle):
    if not _gloss_ok(fd):
        return None, None
    hi = (lum(fd.rgb) >= th["highlight"]) & fd.gloss
    min_area = max(4, 2e-4 * hi.size)
    props = [p for p in regionprops(label(hi, connectivity=2)) if p.area >= min_area]
    v = float(np.mean([p.axis_major_length / max(p.axis_minor_length, 1.0) for p in props])) if props else 0.0
    need = th["minElongationVehicle"] if vehicle else th["minElongation"]
    return v, bool(v >= need)


def t307(fd, th):
    if not _gloss_ok(fd):
        return None, None
    g = lum(fd.rgb)[fd.gloss]
    dark, bright = float((g < th["dark"]).mean()), float((g > th["bright"]).mean())
    return {"dark": dark, "bright": bright}, bool(dark >= th["minDarkShare"] and bright >= th["minBrightShare"])


def t308(fd, th):
    if not _gloss_ok(fd):
        return None, None
    v = float((lum(fd.rgb)[fd.gloss] >= th["blown"]).mean())
    return v, bool(v <= th["maxBlownShare"])


def t309(fd, th):
    mk, b = fd.mask, int(th["band"])
    if not mk.any() or mk.all():
        return None, None
    inner = (mk & ~binary_erosion(mk, structure=disk(b))).astype(np.float64)
    outer = (binary_dilation(mk, structure=disk(b)) & ~mk).astype(np.float64)
    edge = mk & ~binary_erosion(mk, structure=disk(1))
    L = lum(fd.rgb).astype(np.float64)
    r = b + 1
    wi, wo = box_mean(inner, r), box_mean(outer, r)
    li, lo = box_mean(L * inner, r), box_mean(L * outer, r)
    valid = edge & (wi > 0) & (wo > 0)
    if not valid.any():
        return None, None
    contrast = np.abs(li[valid] / wi[valid] - lo[valid] / wo[valid])
    v = float((contrast >= th["minContrast"]).mean())
    return v, bool(v >= th["minBoundaryShare"])


def t315(fd, th):
    if fd.t > th["hookS"] + 1e-9:
        return None, None
    v = float(fd.mask.mean())
    return v, bool(v >= th["minArea"])


def t318(fd, th, aspect):
    if aspect != "9:16":
        return None, None
    if not fd.mask.any():
        return 0.0, False
    h, w = fd.mask.shape
    x0, y0, x1, y1 = th["box1080x1920"]
    ys, xs = np.nonzero(fd.mask)
    cx, cy = xs.mean() * 1080 / w, ys.mean() * 1920 / h
    inside = x0 <= cx <= x1 and y0 <= cy <= y1
    return (round(float(cx), 1), round(float(cy), 1)), bool(inside)


def t319(fd, th):
    bg = ~fd.mask
    if not fd.mask.any() or not bg.any():
        return None, None
    lab = srgb_to_lab(fd.rgb.astype(np.float64))
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    cs, cb = float(chroma[fd.mask].mean()), float(chroma[bg].mean())
    if cs < th["monoChroma"] and cb < th["monoChroma"]:
        v = abs(float(lab[..., 0][fd.mask].mean()) - float(lab[..., 0][bg].mean())) / 100.0
        return v, bool(v >= 0.10)
    v = cs / max(cb, 1e-6)
    return v, bool(v >= th["minRatio"])


def t320(frames, th):
    per_shot = {}
    for fd in frames:
        bg = ~fd.mask
        if bg.any():
            per_shot.setdefault(fd.shot, []).append(srgb_to_lab(fd.rgb.astype(np.float64))[bg].mean(0))
    if not per_shot:
        return None, None
    means = np.array([np.mean(v, 0) for v in per_shot.values()])
    de = float(np.linalg.norm(means - means.mean(0), axis=1).max())
    return de, bool(de <= th["maxDeltaE"])


def t322(fd, th):
    if fd.lens < th["minLens"]:
        return None, None
    L = lum(fd.rgb)
    r = _ratio(sharpness(L, ~fd.mask), sharpness(L, fd.mask))
    return (None, None) if r is None else (r, bool(r <= th["maxRatio"]))


def _shot_param(shot, catalog, key):
    ref = shot["camera"]
    if key in ref.get("params", {}):
        return float(ref["params"][key])
    return float(catalog.get("camera", ref["id"])["params"][key]["default"])


def script_applicable(script, catalog, th):
    """Items whose applicability is a property of the script, not of a frame: {id: bool}. When the
    script has an applicable shot but no sampled frame reads the item, it is unmeasured, never n/a."""
    shots = script["shots"]
    framings = {catalog.get("camera", sh["camera"]["id"])["framing"] for sh in shots}
    return {
        "B-05": "full" in framings,
        "T1-X2": "full" in framings,
        "T3-03": "detail" in framings,
        "T2-06": any(_shot_param(sh, catalog, "fstop") <= th["T2-06"]["maxFstop"] for sh in shots),
        "T3-22": any(_shot_param(sh, catalog, "lensMm") >= th["T3-22"]["minLens"] for sh in shots),
        "T3-15": script["format"]["durationS"] >= th["T3-15"]["hookS"],
        "T3-18": script["format"]["aspect"] == "9:16",
    }


def _aggregate(iid, rows, detail="", applicable=False):
    """Strict v0 rule: an item passes only if every applicable frame passes. An item the script makes
    applicable that no sampled frame read is unmeasured."""
    applied = [r for r in rows if r[2] is not None]
    if not applied:
        if applicable:
            return ItemResult(iid, "unmeasured", rows,
                              "the script has an applicable shot but no sampled frame measured it")
        return ItemResult(iid, "na", rows, detail or "no applicable frame")
    return ItemResult(iid, "pass" if all(r[2] for r in applied) else "fail", applied, detail)


PER_FRAME_IDS = ("B-01", "B-02", "B-05", "T1-X2", "T2-02", "T2-06", "T2-07", "T3-03", "T3-06", "T3-07",
                 "T3-08", "T3-09", "T3-15", "T3-18", "T3-19", "T3-22")


def evaluate(frames, script, profile, catalog, th):
    """{id: ItemResult} for every [M] item (and the M halves of S+M items) on the key frames.
    Full-framing items run on full-framing shots, T3-03's M half on detail shots."""
    if not frames:  # an empty render log measured nothing: never let n/a count as a pass
        ids = list(PER_FRAME_IDS) + ["T3-20"] + list(UNMEASURED_V0)
        return {iid: ItemResult(iid, "unmeasured", None, UNMEASURED_V0.get(iid, "no rendered frames"))
                for iid in ids}
    aspect = script["format"]["aspect"]
    black_world = script["world"].get("params", {}).get("tone") == "black"
    vehicle = profile.longest >= VEHICLE_SIZE_M
    shots = script["shots"]

    def framing(fd):
        return catalog.get("camera", shots[fd.shot]["camera"]["id"])["framing"]

    per_frame = {
        "B-01": lambda fd: b01(fd, th["B-01"]),
        "B-02": lambda fd: b02(fd, th["B-02"], black_world),
        "B-05": lambda fd: b05(fd, th["B-05"]) if framing(fd) == "full" else (None, None),
        "T1-X2": lambda fd: t1x2(fd, th["T1-X2"]),
        "T2-02": lambda fd: t202(fd, th["T2-02"]),
        "T2-06": lambda fd: t206(fd, th["T2-06"]),
        "T2-07": lambda fd: t207(fd, th["T2-07"]),
        "T3-03": lambda fd: t303m(fd, th["T3-03"]) if framing(fd) == "detail" else (None, None),
        "T3-06": lambda fd: t306(fd, th["T3-06"], vehicle),
        "T3-07": lambda fd: t307(fd, th["T3-07"]),
        "T3-08": lambda fd: t308(fd, th["T3-08"]),
        "T3-09": lambda fd: t309(fd, th["T3-09"]),
        "T3-15": lambda fd: t315(fd, th["T3-15"]),
        "T3-18": lambda fd: t318(fd, th["T3-18"], aspect),
        "T3-19": lambda fd: t319(fd, th["T3-19"]),
        "T3-22": lambda fd: t322(fd, th["T3-22"]),
    }
    assert tuple(per_frame) == PER_FRAME_IDS
    out = {}
    gated = script_applicable(script, catalog, th)
    for iid, fn in per_frame.items():
        out[iid] = _aggregate(iid, [(fd.frame, *fn(fd)) for fd in frames], applicable=gated.get(iid, False))
    v, ok = t320(frames, th["T3-20"]) if frames else (None, None)
    out["T3-20"] = ItemResult("T3-20", "na" if ok is None else ("pass" if ok else "fail"), v,
                              "clip-level: max per-shot background dE76 from the clip mean")
    for iid, why in UNMEASURED_V0.items():
        out[iid] = ItemResult(iid, "unmeasured", None, why)
    return out
