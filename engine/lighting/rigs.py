"""Layouts for the phase-5 lighting rigs (Task 72), relative to the hero camera. Pure: LightSpecs only, the
build.py files realise them. Sizes and distances are in subject radii; numbers marked (eng) are in the
calibration register."""
import math

from engine.geometry import _norm, _sub
from engine.reflect import LightSpec

OWN_SUN_AZ = 120.0          # (eng) hard_sun's own sun, degrees from the hero view: side-back (V-L14)
FILL_AZ, FILL_EL = -45.0, 10.0      # (eng) the bounce card: the camera's shadow side, low
RIM_AZ, RIM_EL = 180.0, 35.0        # (eng) straight behind, above
NEON_EL = 20.0              # (eng) neon rims just above the subject's centre
NEG_AZ, NEG_EL = 90.0, 5.0  # (eng) hdri_only's black card: beside the subject, camera's right


def hero_azimuth(profile, hero_pos):
    cx, cy, _ = profile.center
    return math.degrees(math.atan2(hero_pos[1] - cy, hero_pos[0] - cx))


def at(profile, az_deg, el_deg, dist):
    cx, cy, cz = profile.center
    az, el = math.radians(az_deg), math.radians(el_deg)
    return (cx + dist * math.cos(el) * math.cos(az), cy + dist * math.cos(el) * math.sin(az), cz + dist * math.sin(el))


def _spec(profile, name, role, c, sx, sy, power):
    return LightSpec(name, role, c, _norm(_sub(profile.center, c)), sx, sy, power)


def sun_vector(profile, hero_pos, az_from_hero_deg, elevation_deg):
    """Unit vector toward the sun: az measured from the hero camera's view direction (0 = behind the subject,
    +90 = on the camera's right)."""
    base = hero_azimuth(profile, hero_pos) + 180.0 - az_from_hero_deg
    a, e = math.radians(base), math.radians(elevation_deg)
    return (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))


def hard_sun_cards(profile, hero_pos, params):
    """The bounce fill card and the optional rim (the sun itself is a SUN light, not a card)."""
    r, h = profile.radius, hero_azimuth(profile, hero_pos)
    out = [_spec(profile, "valora_sun_fill", "fill", at(profile, h + FILL_AZ, FILL_EL, 3.0 * r), 1.5 * r, 1.0 * r,
                 params["fillRatio"])]
    if params["rim"] > 0:
        out.append(_spec(profile, "valora_sun_rim", "rim", at(profile, h + RIM_AZ, RIM_EL, 3.0 * r), 0.5 * r, 1.2 * r,
                         params["rim"]))
    return tuple(out)


def neon_hues(world_hue, split):
    return ((world_hue - split / 2.0) % 360.0, (world_hue + split / 2.0) % 360.0)


def rim_neon_layout(profile, hero_pos, params):
    """Two tall rim strips either side behind the subject and a low fill from the camera side."""
    r, h = profile.radius, hero_azimuth(profile, hero_pos)
    k = params["keyAzimuthDeg"]
    return (_spec(profile, "valora_neon_rim_a", "rim", at(profile, h + k, NEON_EL, 2.5 * r), 0.4 * r, 1.6 * r,
                  params["rimStrength"]),
            _spec(profile, "valora_neon_rim_b", "rim", at(profile, h - k, NEON_EL, 2.5 * r), 0.4 * r, 1.6 * r,
                  params["rimStrength"]),
            _spec(profile, "valora_neon_fill", "fill", at(profile, h - 30.0, 10.0, 3.5 * r), 1.5 * r, 1.0 * r, 0.12))


def neg_fill_card(profile, hero_pos, neg_fill):
    if neg_fill <= 0:
        return None
    r, h = profile.radius, hero_azimuth(profile, hero_pos)
    return _spec(profile, "valora_neg_fill", "negfill", at(profile, h + NEG_AZ, NEG_EL, 1.6 * r),
                 2.0 * r * neg_fill, 1.5 * r, 0.0)
