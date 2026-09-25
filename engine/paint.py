"""Paint override for the compile job (art pass round 4, 2026-09-25). Host side, pure.

A job may carry `paint: {"color": "#rrggbb", "finish": <FINISHES>}`; nothing else is accepted, and the
colour reaches Blender only as three linear floats this module computes (never a raw string). With no
`paint` the upload's materials are left exactly as they came (spec 4.5). The Blender side is
engine/blender/paint.py: it finds the paint materials by name and rebuilds them as a lacquered paint,
the recipe ModVision's render-studio used for the black rain film (render_materials.py / surface_detail.py)."""
import re

FINISHES = ("gloss", "metallic", "satin", "matte")
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


class PaintError(ValueError):
    pass


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def validate_paint(paint):
    """None -> None; else {"color": "#rrggbb", "linear": [r, g, b], "finish": str} or PaintError."""
    if paint is None:
        return None
    if not isinstance(paint, dict) or set(paint) - {"color", "finish"} or "color" not in paint:
        raise PaintError("paint must be {color: '#rrggbb', finish?: one of %s}" % (FINISHES,))
    color, finish = paint["color"], paint.get("finish", "gloss")
    if not isinstance(color, str) or not _HEX.fullmatch(color):
        raise PaintError(f"paint.color {color!r} is not a #rrggbb hex colour")
    if not isinstance(finish, str) or finish not in FINISHES:
        raise PaintError(f"paint.finish {finish!r} is not one of {FINISHES}")
    rgb = [int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return {"color": color.lower(), "linear": [round(srgb_to_linear(c), 6) for c in rgb], "finish": finish}
