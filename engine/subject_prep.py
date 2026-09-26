"""Subject preparation (realism pass 2026-09-25): which calibration each uploaded material gets. Pure, host side.

The Blender side (engine/blender/subject_prep.py) gathers each material's facts, asks classify() for its role and
applies that role's calibration, ported from ModVision's render-studio (the black rain film's car):
render_materials.calibrate_materials, component_materials.prepare, surface_detail, road_weathering, rain_look.

Guards, not names. render-studio could trust names because it only ever saw its own exports; an upload can call
anything anything. So every role needs corroborating evidence beyond a word: transparency for glass, an opaque
white or red untextured surface for a lamp emitter, a dark dielectric for rubber, and for tyres, discs, calipers
and rims the geometry itself, measured against the profile's wheels (vertex_labels). A material with no role is
left exactly as uploaded."""
import re

# ---- words --------------------------------------------------------------------------------------------------
LAMP_WORDS = frozenset({"headlight", "headlights", "headlamp", "headlamps", "taillight", "taillights", "taillamp",
                        "taillamps", "drl", "lamp", "lamps", "light", "lights", "indicator", "indicators", "blinker",
                        "marker", "foglight", "foglamp"})
DRL_WORDS = frozenset({"drl", "daytime"})
TAIL_WORDS = frozenset({"tail", "taillight", "taillights", "taillamp", "taillamps", "brake", "stop", "rear"})
LENS_WORDS = frozenset({"glass", "lens", "lenses", "cover", "clear", "transparent", "polycarbonate"})
WINDOW_WORDS = frozenset({"glass", "window", "windows", "windshield", "windscreen", "glazing", "sunroof", "tint"})
CARBON_WORDS = frozenset({"carbon", "cfrp", "carbonfiber", "carbonfibre", "weave"})
AERO_DISC_WORDS = frozenset({"aero", "cap", "cover"})   # a wheel's flat aero disc (the Manthey's rear aero-disc cap)
PAINT_WORDS = frozenset({"paint", "carpaint", "bodypaint", "lacquer", "clearcoat"})
RUBBER_WORDS = frozenset({"rubber", "tire", "tyre", "tires", "tyres", "seal", "gasket"})
TRIM_WORDS = frozenset({"plastic", "plastics", "trim", "abs", "polymer"})
INTERIOR_WORDS = frozenset({"interior", "cabin", "seat", "seats", "dash", "dashboard", "leather", "alcantara"})

# ---- evidence thresholds (eng unless a source is given) ---------------------------------------------------------
OPAQUE = 0.98          # alpha at or above: an opaque surface
TRANSPARENT = 0.98     # alpha below (or transmission >= TRANSMISSIVE): a see-through surface
TRANSMISSIVE = 0.5
DIELECTRIC = 0.5       # metallic below: not a metal (render_materials: lamp lens `metallic < 0.5`)
DARK = 0.10            # luminance at or below: black rubber
TRIM_DARK = 0.12       # black plastic trim
PRIVACY_DARK = 0.05    # an opaque window this dark is deliberate privacy glass (render_materials :166-172)
DRL_WHITE = 0.6        # every channel at or above: a white DRL emitter
RED = 3.0              # red at least 3x green and blue: a red tail emitter
CALIPER_CHROMA = 0.25  # a painted caliper is saturated; a black one keeps its export
SHARE = 0.6            # of a material's vertices, on one wheel part, to take that part's role

# ---- wheel geometry (placed metres; engine/physics/wheel_mask.py is the shared tyre rule) -----------------------
DISC_RMAX = (0.42, 0.66)   # x r: a brake disc fills the barrel inside the bead seat (fixture 0.57 r; road cars'
#                            256-420 mm discs on 0.30-0.36 m tyres: 0.43-0.62 r); a flat hub cap is smaller (0.39 r)
DISC_FLAT = 0.15           # axial thickness / diameter at most
CALIPER_OFF = 0.30         # x r: a caliper's centroid sits off the axle (a spinning part's does not)


def tokens(*names):
    """Lower-case words of the names: split on separators, digits and camelCase ("MV_HeadlightGlass.001")."""
    out = set()
    for n in names:
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(n or ""))
        out.update(w for w in re.split(r"[^a-z]+", s.lower()) if w)
    return out


def _user_tokens(users):
    """Words at least half the users' object names carry (one headlight washer on the window glass is no lamp)."""
    if not users:
        return set()
    counts = {}
    for u in users:
        for t in tokens(u):
            counts[t] = counts.get(t, 0) + 1
    return {t for t, c in counts.items() if 2 * c >= len(users)}


def pigment_stats(rgb):
    """(Rec.709 luminance, chroma = max - min) of a linear RGB pigment, or (None, None)."""
    if rgb is None:
        return None, None
    r, g, b = rgb[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b, max(r, g, b) - min(r, g, b)


def _opaque(f):
    return f["alpha"] is not None and f["alpha"] >= OPAQUE and f["transmission"] is not None \
        and f["transmission"] < 0.05


def _transparent(f):
    return (f["alpha"] is not None and f["alpha"] < TRANSPARENT) or \
        (f["transmission"] is not None and f["transmission"] >= TRANSMISSIVE)


def _dielectric(f):
    return f["metallic"] is not None and f["metallic"] < DIELECTRIC


def _emissive(f):
    return f["emissionLinked"] or (f["emission"] > 0 and max(f["emissionColor"][:3]) > 0)


def _plain(f):
    """A principled BSDF straight into the output, no authored maps, no volume: safe to re-wire."""
    return f["direct"] and not f["textured"] and not f["volume"]


def classify(f):
    """The calibration role of one material from its facts, or None (left as uploaded). Facts:
    name, users (object names), principled, textured, volume, direct, alpha, transmission, metallic, roughness,
    coat (None = a linked socket), pigment (constant linear RGB or None), emission, emissionColor, emissionLinked,
    geo ({tyre|rim|disc|caliper: share of the material's vertices}), painted (the engine's paint override)."""
    if not f["principled"] or f["volume"]:
        return None
    if f.get("painted"):
        return "paint"
    words = tokens(f["name"]) | _user_tokens(f["users"])
    lum, chroma = pigment_stats(f["pigment"])
    geo = f.get("geo") or {}
    lamp = bool(words & LAMP_WORDS)
    if lamp and _opaque(f) and _dielectric(f) and not f["textured"] and not f["emissionLinked"]:
        emit = f["emissionColor"] if f["emission"] > 0 else f["pigment"]
        if words & DRL_WORDS and emit is not None and min(emit[:3]) >= DRL_WHITE:
            return "lamp-drl"
        if words & TAIL_WORDS and emit is not None and emit[0] >= 0.3 and emit[0] >= RED * max(emit[1], emit[2]):
            return "lamp-tail"
    if lamp and _dielectric(f) and _plain(f) and (_transparent(f) or (words & LENS_WORDS and not _opaque(f))):
        return "lamp-lens"
    if words & WINDOW_WORDS and _dielectric(f) and _plain(f) and not _emissive(f):
        if _transparent(f):
            return "window-glass"
        if _opaque(f) and f["pigment"] is not None and max(f["pigment"][:3]) < PRIVACY_DARK:
            return "privacy-glass"
    if words & CARBON_WORDS and _opaque(f) and not _emissive(f):
        return "carbon"
    if words & PAINT_WORDS and _opaque(f) and not _emissive(f):
        return "paint"
    rubbery = _opaque(f) and _dielectric(f) and not _emissive(f)
    if geo.get("tyre", 0) >= SHARE and rubbery and (lum is not None and lum <= DARK or lum is None and f["textured"]):
        return "tyre"
    if geo.get("disc", 0) >= SHARE and words & AERO_DISC_WORDS and _opaque(f) and not _emissive(f):
        return "aero-disc"      # disc-shaped on the axle AND named a cap/cover: reads as a brake disc, so it wears
        #                         the carbon-ceramic disc look (round 7: the copper "Manthey cap" read as a bronze disc)
    if geo.get("disc", 0) >= SHARE and not f["textured"] and f["metallic"] is not None and f["metallic"] >= 0.3:
        return "rotor"
    if geo.get("caliper", 0) >= SHARE and not f["textured"] and chroma is not None and chroma >= CALIPER_CHROMA:
        return "caliper"
    if geo.get("rim", 0) >= SHARE and _opaque(f) and f["metallic"] is not None and f["metallic"] >= DIELECTRIC:
        return "rim"
    if words & RUBBER_WORDS and rubbery and lum is not None and lum <= DARK:
        return "rubber"
    if words & TRIM_WORDS and _opaque(f) and not f["textured"] and not _emissive(f) and lum is not None \
            and lum <= TRIM_DARK and f["metallic"] is not None and f["metallic"] <= 0.2 and f["roughness"] is not None:
        if f["roughness"] >= 0.5:
            return "trim-matte"
        if f["roughness"] <= 0.35:
            return "trim-gloss"
    return None


def interior(name, users):
    """A cabin material: road film never reaches it."""
    return bool((tokens(name) | _user_tokens(users)) & INTERIOR_WORDS)


# ---- wheel geometry -----------------------------------------------------------------------------------------
def vertex_labels(points, wheels):
    """Per-vertex wheel part of one object's (n, 3) placed points: 'tyre' | 'rim' | 'disc' | 'caliper' | ''.
    A whole object inside one wheel's cylinder is judged as a piece: flat, round and on the axle inside the
    bead seat is a disc; off the axle is a caliper; otherwise its tyre-band vertices are tyre and the rest rim.
    An object reaching outside every wheel keeps only its tyre-band vertices (a merged car mesh's tyres)."""
    import numpy as np
    from engine.physics.wheel_mask import _frame, in_wheel_box, radial, tyre_mask
    n = len(points)
    out = np.full(n, "", dtype=object)
    if not n or not wheels:
        return out
    lo, hi = points.min(axis=0), points.max(axis=0)
    for w in wheels:
        rho = radial(points, w)
        rmax = float(rho.max())
        if not in_wheel_box(lo, hi, w, rmax):
            continue
        r, (ai, rad) = w["radius"], _frame(w)
        c = np.asarray(w["center"], dtype=np.float64)
        off = float(np.hypot(*(points[:, k].mean() - c[k] for k in rad)))
        thick = float(hi[ai] - lo[ai])
        if off > CALIPER_OFF * r and rmax < 0.95 * r:
            out[:] = "caliper"
        elif off <= 0.1 * r and DISC_RMAX[0] * r <= rmax <= DISC_RMAX[1] * r and thick <= DISC_FLAT * 2 * rmax:
            out[:] = "disc"
        else:
            out[:] = "rim"
            out[tyre_mask(points, w)] = "tyre"
        return out
    for w in wheels:
        out[(out == "") & tyre_mask(points, w)] = "tyre"
    return out


def part_labels(points, wheels):
    """{label: vertex count} of vertex_labels, blanks dropped (tests and the prep report)."""
    labels = vertex_labels(points, wheels)
    out = {}
    for lab in labels:
        if lab:
            out[lab] = out.get(lab, 0) + 1
    return out


# ---- scene conditions -------------------------------------------------------------------------------------------
WET_EFFECTS = frozenset({"rain", "wet_surface", "droplets", "snow"})
NIGHT_WORLDS = frozenset({"night_street"})      # dark by default (its timeOfDay default is night)
DARK_TIMES = frozenset({"dusk", "night", "blue_hour", "twilight"})
ROAD_FILM = {"wet": 1.0, "dry": 0.15, "indoor": 0.0}     # rain_look.LOOK road_film 1.0 (the film); dry: a light
#                                                          dust, <= ~10% cover at its peak (eng; critique r4 5-10%)
BRAKE_DUST = {"wet": 0.9, "dry": 0.5, "indoor": 0.0}     # rain_look.LOOK brake_dust .9; dry (eng)


def conditions(script, outdoor):
    """What the scene says about the car: wet (rain, snow, standing water, wet world), outdoor (the world's
    block.json `outdoor`), the road-film and brake-dust strengths, and whether its running lamps are on: outdoors
    in the wet or after dark, as in the rain film; in dry daylight and in a studio the upload's own lamp state
    stands (a parked car in the sun has its lamps off)."""
    world = script.get("world") or {}
    params = world.get("params") or {}
    fx = {e.get("id") for e in script.get("effects") or []}
    wet = bool(fx & WET_EFFECTS) or float(params.get("wetness") or 0) > 0
    tod = params.get("timeOfDay")
    # a night world is dark unless its timeOfDay says daylight (night_street overcast_day is a daytime street)
    dark = tod in DARK_TIMES or (world.get("id") in NIGHT_WORLDS and tod is None)
    key = "wet" if wet and outdoor else "dry" if outdoor else "indoor"
    return {"wet": wet, "outdoor": bool(outdoor), "roadFilm": ROAD_FILM[key], "brakeDust": BRAKE_DUST[key],
            "lampsOn": bool(outdoor and (wet or dark)), "dark": bool(outdoor and dark)}
