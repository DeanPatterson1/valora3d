"""One wind, many consumers (METHODS §2.9, hand-off H4). Each wind-driven block declares
physics.windCalibration = {unit, perMs}: its own unit per m/s of field speed (for a drag consumer such as
foliage sway the unit says per (m/s)^2 and perMs is engine/physics/sway.DRAG_K). Phase 5 declares today's
constants, so nothing changes look: haze wisps and shaft dust advect with the full mean wind (1.0).
Rain slant is analytic (slant = atan(wind / fall speed)); force-field strength is not m/s and gets its own
mapping (FF_STRENGTH_PER_MS2, fitted on cloth in phase 6 Task 107). Numbers are (eng) until the
wind_coherent probe and a <=3-frame look-check agree."""
import math

# Blender WIND strength per (m/s)^2, fitted in phase 6 Task 107 on a 1 m silk strip against the quasi-static drag
# model (engine/tests/test_cloth_calibration_blender.py; var/probe/cloth_calibration.json). Quadratic, because
# the field pushes a cloth face by strength x area like a pressure and drag pressure goes with v^2. It is the
# CLOTH's field: presets keep Blender-scale vertex masses (engine/physics/cloth), so the value is large; any
# other field consumer sets its own effector weight. Replaced the phase-5 (eng) linear 0.8 per m/s.
FF_STRENGTH_PER_MS2 = 7600.0
COHERENT_MIN_MS = 1.5      # BLOCKS §5: below this the wind is too weak to judge a consumer's direction
COHERENT_MAX_DEG = 45.0    # BLOCKS §5: a consumer's motion lies within 45 deg of the wind vector


def consumer_value(cal, speed_ms):
    return 0.0 if speed_ms <= 0 else cal["perMs"] * speed_ms


def perms(catalog, kind, bid, default=1.0):
    """The block's declared perMs (its manifest), or `default` when it declares none."""
    m = (catalog.get(kind, bid) if catalog is not None else None) or {}
    return float(((m.get("physics") or {}).get("windCalibration") or {}).get("perMs", default))


def rain_slant_deg(wind_ms, fall_ms):
    return math.degrees(math.atan2(wind_ms, fall_ms))


def force_field_strength(speed_ms):
    return FF_STRENGTH_PER_MS2 * speed_ms * speed_ms if speed_ms > 0 else 0.0


def ff_seed(block_seed):
    return 1 + block_seed % 128          # METHODS R3: force-field seed accepts 1-128 only


def coherent(disp, direction_deg, speed_ms):
    """wind_coherent (report-only): the angle between a consumer's horizontal displacement and the wind.
    Not judged (None) below COHERENT_MIN_MS or with no measurable displacement."""
    a = math.radians(direction_deg)
    dx, dy = float(disp[0]), float(disp[1])
    n = math.hypot(dx, dy)
    if speed_ms < COHERENT_MIN_MS or n <= 1e-12:
        return {"angleDeg": None, "ok": None}
    cos = max(-1.0, min(1.0, (dx * math.cos(a) + dy * math.sin(a)) / n))
    ang = round(math.degrees(math.acos(cos)), 2)
    return {"angleDeg": ang, "ok": ang <= COHERENT_MAX_DEG}
