"""Interior mapping for the street's window rooms (pure maths; engine/blender/facade_kit.room_material realises
it in nodes). Realism audit "facade interior cards": a flat emissive card 0.55 m behind the glass reads as a
poster once the camera looks along the facade. Here the card is a window onto a virtual room box: the view ray
through each card point is intersected with the room's walls, ceiling and floor, and the hit is lit by one
ceiling lamp, so rooms show depth, side walls and a ceiling that slide correctly with the camera.

Card-local frame: x along the card (+u, metres), y up (+v, metres), z into the building (> 0)."""
import math

ROOM_DEPTH_M = 3.6        # (eng) back wall depth behind the card
ROOM_SIDE_M = 1.1         # (eng) the room reaches this far past each side of the window
ROOM_SILL_M = 0.95        # (eng) floor this far below the window's bottom edge
ROOM_HEAD_M = 0.35        # (eng) ceiling this far above its top edge
SURF_BASE = {"back": 0.7, "side": 0.55, "ceiling": 1.0, "floor": 0.4}   # (eng) share of the lamp each surface returns
LAMP_FALLOFF = 0.45       # (eng) b = base / (1 + LAMP_FALLOFF d^2) around the lamp
AMBIENT = 0.14            # (eng) the room's fill


def bounds(w, h):
    return (-ROOM_SIDE_M, w + ROOM_SIDE_M), (-ROOM_SILL_M, h + ROOM_HEAD_M), (0.0, ROOM_DEPTH_M)


def room_hit(px, py, d, w, h):
    """(surface, hit point) of the ray from card point (px, py, 0) along local direction d (d.z > 0)."""
    (x0, x1), (y0, y1), (_, z1) = bounds(w, h)
    dx, dy, dz = d
    tx = abs((x1 if dx > 0 else x0) - px) / max(abs(dx), 1e-4)
    ty = abs((y1 if dy > 0 else y0) - py) / max(abs(dy), 1e-4)
    tz = z1 / max(dz, 1e-4)
    t = min(tx, ty, tz)
    hit = (px + t * dx, py + t * dy, t * dz)
    if tz <= min(tx, ty):
        return "back", hit
    if tx <= ty:
        return "side", hit
    return ("ceiling" if dy > 0 else "floor"), hit


def lamp_at(w, h, lx):
    """The room's ceiling lamp: lx (0..1) across the room, just under the ceiling, mid-depth."""
    (x0, x1), (_, y1), (_, z1) = bounds(w, h)
    return (x0 + lx * (x1 - x0), y1 - 0.15, 0.55 * z1)


def brightness(surface, hit, lamp):
    d2 = sum((a - b) ** 2 for a, b in zip(hit, lamp))
    return SURF_BASE[surface] / (1.0 + LAMP_FALLOFF * d2) + AMBIENT


def local_dir(view, t, n_out):
    """World view direction (camera -> point) in the card frame: (along T, world up, into = -n_out)."""
    return (sum(a * b for a, b in zip(view, t)), view[2], -sum(a * b for a, b in zip(view, n_out)))


def parallax_shift(depth, angle_deg):
    """How far (m) a point `depth` behind the card slides across it for a view `angle_deg` off the normal."""
    return depth * math.tan(math.radians(angle_deg))
