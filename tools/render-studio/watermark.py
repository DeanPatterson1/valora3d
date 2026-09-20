"""Preview watermark for free-tier renders.

A watermarked preset ("watermark": True in jobs.PRESETS, server-authoritative:
the client cannot clear it) delivers every pixel the visitor can reach with a
diagonal <brand> PREVIEW tile plus a corner badge burnt in: the encoded video,
the poster, and the progress stills Blender writes while rendering. The overlay
is built once per job at delivery resolution with Pillow's bundled scalable
font, so no system font is required; if Pillow is missing the job fails closed
rather than shipping a clean preview.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

#: Keep in step with `apps/web/lib/brand.ts`.
BRAND = os.environ.get("RENDER_STUDIO_BRAND", "RENDER STUDIO")
TILE_TEXT = f"{BRAND} PREVIEW"
BADGE_TEXT = f"{BRAND} PREVIEW · NOT FOR DELIVERY"
TILE_ALPHA = 64          # of 255 — legible over paint and sky, never hides the car
BADGE_ALPHA = 200
ANGLE_DEG = 30


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: WPS433 — optional at import, required at use
    except ImportError as error:  # pragma: no cover — exercised only on a box without Pillow
        raise RuntimeError("Preview watermarking needs Pillow (py -m pip install pillow); the render was not delivered unmarked") from error
    return Image, ImageDraw, ImageFont


def build_overlay(path: Path, width: int, height: int) -> Path:
    """Write an RGBA PNG of exactly width x height with the tile + badge and return its path."""
    Image, ImageDraw, ImageFont = _pil()
    width, height = int(width), int(height)
    if width < 16 or height < 16:
        raise ValueError("Watermark overlay needs a real frame size")
    short = min(width, height)
    tile_size = max(12, round(short * 0.07))
    badge_size = max(9, round(short * 0.028))
    tile_font = ImageFont.load_default(size=tile_size)
    badge_font = ImageFont.load_default(size=badge_size)

    # Tile layer: text repeated on a grid, drawn on a canvas big enough to stay
    # covered after rotation, then rotated and cropped to the frame.
    diagonal = int(math.ceil(math.hypot(width, height))) + tile_size * 4
    layer = Image.new("RGBA", (diagonal, diagonal), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = draw.textbbox((0, 0), TILE_TEXT, font=tile_font)
    text_w, text_h = right - left, bottom - top
    step_x, step_y = text_w + tile_size * 3, text_h + tile_size * 3
    row = 0
    for y in range(-step_y, diagonal + step_y, step_y):
        offset = (step_x // 2) if row % 2 else 0
        for x in range(-step_x + offset, diagonal + step_x, step_x):
            draw.text((x, y), TILE_TEXT, font=tile_font, fill=(255, 255, 255, TILE_ALPHA))
        row += 1
    layer = layer.rotate(ANGLE_DEG, resample=Image.BICUBIC, expand=False)
    cx, cy = diagonal // 2, diagonal // 2
    overlay = layer.crop((cx - width // 2, cy - height // 2, cx - width // 2 + width, cy - height // 2 + height))

    # Corner badge: solid enough to survive compression and a crop of the tile.
    draw = ImageDraw.Draw(overlay)
    pad = max(4, round(short * 0.012))
    left, top, right, bottom = draw.textbbox((0, 0), BADGE_TEXT, font=badge_font)
    bw, bh = right - left + pad * 2, bottom - top + pad * 2
    x0, y0 = width - bw - pad * 2, height - bh - pad * 2
    draw.rectangle((x0, y0, x0 + bw, y0 + bh), fill=(0, 0, 0, 150))
    draw.text((x0 + pad - left, y0 + pad - top), BADGE_TEXT, font=badge_font, fill=(255, 255, 255, BADGE_ALPHA))

    path = Path(path)
    overlay.save(path, format="PNG")
    return path


def stamp_still(source: Path, overlay: Path, destination: Path, quality: int = 85) -> Path:
    """Composite the overlay onto a JPEG/PNG still and write it atomically to destination."""
    Image, _, _ = _pil()
    with Image.open(source) as image:
        frame = image.convert("RGBA")
    with Image.open(overlay) as mark:
        mark = mark.convert("RGBA")
        if mark.size != frame.size:
            mark = mark.resize(frame.size, Image.BICUBIC)
        frame.alpha_composite(mark)
    destination = Path(destination)
    temporary = destination.with_name(destination.stem + "-stamping" + destination.suffix)
    frame.convert("RGB").save(temporary, format="JPEG", quality=quality)
    temporary.replace(destination)
    return destination


def wants_watermark(job) -> bool:
    return bool(job.get("watermark")) if isinstance(job, dict) else False
