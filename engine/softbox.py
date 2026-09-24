"""softbox_three_point layout, relative to the hero camera. Pure. Distances/sizes are (eng),
re-authored in subject radii from product-render's 1 m-normalised rig (engine spec §10.8)."""
import math

from engine.geometry import _norm, _sub
from engine.reflect import LightSpec, RigLayout


def softbox_layout(profile, hero_pos, params):
    cx, cy, cz = profile.center
    r = profile.radius
    hero_az = math.degrees(math.atan2(hero_pos[1] - cy, hero_pos[0] - cx))

    def at(az_deg, el_deg, dist):
        az, el = math.radians(az_deg), math.radians(el_deg)
        return (cx + dist * math.cos(el) * math.cos(az), cy + dist * math.cos(el) * math.sin(az),
                cz + dist * math.sin(el))

    def spec(name, role, c, sx, sy, power):
        return LightSpec(name, role, c, _norm(_sub(profile.center, c)), sx, sy, power)

    key = at(hero_az + params["keyAzimuthDeg"], params["keyElevationDeg"], 3.0 * r)
    fill = at(hero_az - 40.0, 15.0, 3.5 * r)
    rim = at(hero_az + 150.0, 38.0, 3.0 * r)
    return RigLayout((spec("valora_key", "key", key, 1.2 * r, 0.9 * r, 1.0),
                      spec("valora_fill", "fill", fill, 1.5 * r, 1.0 * r, params["fillRatio"]),
                      spec("valora_rim", "rim", rim, 0.5 * r, 1.1 * r, params["rimStrength"])),
                     ambient=0.05)
