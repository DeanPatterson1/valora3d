"""Foliage level of detail by projected size, pure.

A tuft's detail follows how big it lands in the frame, not a flat budget: projected_px is the pinhole height
(px on the frame's long side) of an object `size_m` tall at `xyz`, taken at the camera key that sees it
largest (nearest distance x longest lens); pick() maps that to a LOD band. Bands (eng, set 2026-09-25 against
the field's photoscanned tufts, ~0.1-0.4 m tall, 300-2600 verts at full detail):
  0  full scan           >= FULL_PX  (blade tips and gaps resolve: decimation shows as clumped cards)
  1  ~MID_VERTS collapse  >= MID_PX
  2  ~FAR_VERTS collapse   below (a few px of texture: silhouette only)"""
import math

SENSOR_MM = 36.0         # engine/geometry.SENSOR_MM (sensor_fit AUTO: the long side)
FRAME_PX = 1920          # final tier's long side; LOD is a property of the shot, not of the preview tier
DEFAULT_LENS_MM = 50.0
NEAR_CLAMP_M = 0.05      # a camera inside a tuft: huge, not infinite
FULL_PX, MID_PX = 90.0, 25.0
MID_VERTS, FAR_VERTS = 400, 150


def projected_px(xyz, size_m, cameras, lenses_mm, frame_px=FRAME_PX, sensor_mm=SENSOR_MM):
    """Largest on-screen height (px) of `size_m` at xyz over the camera keys. No camera: inf (full detail)."""
    best = 0.0
    if not cameras:
        return float("inf")
    for i, c in enumerate(cameras):
        lens = lenses_mm[i] if i < len(lenses_mm) and lenses_mm[i] else DEFAULT_LENS_MM
        d = max(NEAR_CLAMP_M, math.dist(c, xyz))
        best = max(best, size_m * lens / sensor_mm * frame_px / d)
    return best


def pick(px):
    """LOD band for a projected size: 0 full, 1 mid, 2 far."""
    return 0 if px >= FULL_PX else 1 if px >= MID_PX else 2
