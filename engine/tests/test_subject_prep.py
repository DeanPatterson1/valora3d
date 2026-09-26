"""Subject preparation (realism pass 2026-09-25): which calibration an uploaded material gets. Pure, host side.

Every role needs corroborating evidence beyond a name (transparency, pigment, metalness, where the geometry sits
on a measured wheel); an unrecognised material gets no role and is left exactly as uploaded."""
import numpy as np
import pytest

from engine.subject_prep import classify, conditions, part_labels, pigment_stats, tokens


def mat(name, users=(), **kw):
    f = {"name": name, "users": list(users), "principled": True, "textured": False, "volume": False,
         "direct": True, "alpha": 1.0, "transmission": 0.0, "metallic": 0.0, "roughness": 0.5, "coat": 0.0,
         "pigment": (0.5, 0.5, 0.5), "emission": 0.0, "emissionColor": (1.0, 1.0, 1.0), "emissionLinked": False,
         "geo": {}, "painted": False}
    f.update(kw)
    return f


def test_tokens_split_names_on_separators_and_camel_case():
    assert tokens("MV_HeadlightGlass.001") >= {"mv", "headlight", "glass"}
    assert tokens("taillight-l-tail-light-bar") >= {"taillight", "tail", "light", "bar"}
    assert "drl" in tokens("Front DRL") and "drl" in tokens("drl-l-ring-1")


# ---- the sports_car fixture's real material setups (read from the GLB 2026-09-25) --------------------------
@pytest.mark.parametrize("f,role", [
    (mat("mv-body-paint", ["door-l-shell"], metallic=0.7, roughness=0.25, pigment=(0.85, 0.02, 0.02)), "paint"),
    (mat("Carbon Fiber Glossy", ["front-splitter-blade"], metallic=0.3, roughness=0.15, pigment=(.05, .05, .06)),
     "carbon"),
    (mat("Glass", ["windshield", "side-window-l"], alpha=0.42, roughness=0.03, pigment=(.03, .033, .038)),
     "window-glass"),
    (mat("Headlight glass", ["headlight-l-lens-1"], alpha=0.16, roughness=0.04, pigment=(.9, .93, .96)), "lamp-lens"),
    (mat("Tail glass", ["taillight-l-tail-glass"], alpha=0.85, roughness=0.1, pigment=(.6, .05, .02)), "lamp-lens"),
    (mat("Front DRL", ["drl-l-ring-1"], roughness=0.1, pigment=(1.0, 1.0, 1.0)), "lamp-drl"),
    (mat("Tail lights", ["taillight-l-tail-light-bar"], roughness=0.2, pigment=(.6, .05, .02)), "lamp-tail"),
    (mat("Rubber.001", ["tire-fl"], roughness=0.85, pigment=(.02, .02, .02), geo={"tyre": 0.97}), "tyre"),
    (mat("Rubber", ["interior-rubber-1"], roughness=0.85, pigment=(.02, .02, .02)), "rubber"),
    (mat("Brake Disc", ["rotor-fl"], metallic=0.6, pigment=(.35, .32, .3), geo={"disc": 1.0}), "rotor"),
    (mat("Manthey cap", ["manthey-aero-disc-cap-l", "manthey-aero-disc-cap-r"], metallic=1.0, roughness=0.55,
         pigment=(.314, .195, .136), textured=True, geo={"disc": 1.0}), "aero-disc"),
    (mat("Brakes", ["caliper-front-l"], metallic=0.8, roughness=1.0, pigment=(.654, .481, 0.0),
         geo={"caliper": 1.0}), "caliper"),
    (mat("Rims", ["wheel-fl"], metallic=0.9, roughness=0.3, pigment=(.12, .12, .13), geo={"rim": 0.99}), "rim"),
    (mat("Matte Plastic", ["front-airduct-l-matte-plastic-15"], roughness=0.75, pigment=(.03, .03, .03)),
     "trim-matte"),
    (mat("Glossy Plastic", ["front-bumper-detail-glossy-plastic-1"], metallic=0.1, roughness=0.15,
         pigment=(.05, .05, .05)), "trim-gloss"),
])
def test_the_fixture_car_materials_get_their_roles(f, role):
    assert classify(f) == role


@pytest.mark.parametrize("f", [
    mat("Aluminum", ["front-bumper-trim-1"], metallic=1.0, roughness=0.25, pigment=(.7, .7, .72)),
    mat("Leather Black", ["interior-leather-black-1"], roughness=0.6, pigment=(.03, .03, .03)),
    mat("Satin Metallic", ["wheel-fl-hub", "front-bumper-detail-satin-metallic-2"], metallic=0.9,
        geo={"rim": 0.3}),
    mat("Yellow Plastic", ["interior-yellow-plastic-1"], roughness=0.4, pigment=(.8, .7, .05)),
    mat("Material.004", ["Cube"], pigment=(.8, .8, .8)),
    mat("Porsche Logo", ["gt3rs-badge-front"], metallic=1.0, alpha=None, textured=True),
])
def test_an_unrecognised_material_gets_no_role(f):
    assert classify(f) is None


# ---- guards: a name alone never earns a role -----------------------------------------------------------------
def test_a_rubber_named_but_bright_or_metal_surface_is_not_rubber():
    assert classify(mat("Rubber", ["seal"], pigment=(.8, .8, .8))) is None
    assert classify(mat("Tire chrome", ["tire-fl"], metallic=1.0, pigment=(.02, .02, .02), geo={"tyre": 1.0})) is None


def test_a_dark_surface_on_the_tyre_band_is_the_tyre_whatever_its_name():
    assert classify(mat("Material.012", ["Object_33"], roughness=0.9, pigment=(.015, .015, .015),
                        geo={"tyre": 0.9})) == "tyre"
    assert classify(mat("Material.012", ["Object_33"], pigment=(.015, .015, .015), geo={"tyre": 0.3})) is None


def test_a_carbon_named_transparent_or_emissive_part_is_not_carbon():
    assert classify(mat("carbon lens", ["x"], alpha=0.3)) is None
    assert classify(mat("Carbon", ["x"], emission=4.0, emissionColor=(1, 1, 1))) is None


def test_glass_needs_transparency_and_a_plain_network():
    assert classify(mat("Glass", ["windshield"], alpha=1.0, pigment=(.5, .5, .5))) is None      # opaque grey
    assert classify(mat("Glass", ["windshield"], alpha=0.4, textured=True)) is None             # authored maps
    assert classify(mat("Glass", ["windshield"], alpha=0.4, direct=False)) is None              # layered network
    assert classify(mat("Glass", ["windshield"], alpha=0.4, volume=True)) is None               # authored volume
    assert classify(mat("Window tint", ["side-window"], alpha=1.0, pigment=(.004, .004, .004))) == "privacy-glass"
    assert classify(mat("Glass", ["windshield"], alpha=1.0, transmission=1.0)) == "window-glass"


def test_a_lamp_emitter_must_be_an_opaque_untextured_surface():
    assert classify(mat("Front DRL", ["drl-l"], pigment=(1, 1, 1), alpha=0.3)) == "lamp-lens"
    assert classify(mat("Front DRL", ["drl-l"], pigment=(1, 1, 1), emissionLinked=True)) is None
    assert classify(mat("Front DRL", ["drl-l"], pigment=(.1, .1, .1))) is None            # a dark housing
    assert classify(mat("Tail lights", ["tail-light-bar"], pigment=(.8, .8, .8))) is None  # a white reflector


def test_a_disc_or_caliper_needs_the_wheel_geometry_not_the_name():
    assert classify(mat("Brake Disc", ["rotor-fl"], metallic=0.6, geo={})) is None
    assert classify(mat("Brakes", ["caliper"], metallic=0.8, pigment=(.1, .1, .1), geo={"caliper": 1.0})) is None
    assert classify(mat("Paint", ["caliper"], pigment=(.8, .05, .05), geo={"caliper": 1.0})) == "paint"


def test_an_aero_disc_cap_needs_the_disc_shape_and_the_name():
    """Round 7: the rear aero-disc cap (copper, fully metallic, normal-mapped) read as a bronze brake disc; it now
    wears the carbon-ceramic disc look. A cap off the disc geometry, or an unnamed textured disc, stays as uploaded."""
    cap = dict(metallic=1.0, pigment=(.314, .195, .136), textured=True)
    assert classify(mat("Manthey cap", ["manthey-aero-disc-cap-l"], geo={"disc": 1.0}, **cap)) == "aero-disc"
    assert classify(mat("Wheel cover", ["wheel-rl"], geo={"disc": 0.9}, **cap)) == "aero-disc"
    assert classify(mat("Manthey cap", ["manthey-aero-disc-cap-l"], geo={"rim": 1.0}, **cap)) != "aero-disc"
    assert classify(mat("Material.012", ["Object.3"], geo={"disc": 1.0}, **cap)) is None
    assert classify(mat("Manthey cap", ["manthey-aero-disc-cap-l"], geo={"disc": 1.0}, emission=2.0, **cap)) is None


def test_the_paint_override_always_makes_paint():
    assert classify(mat("valora_paint_gloss", ["door"], painted=True, textured=True)) == "paint"


def test_pigment_stats():
    lum, chroma = pigment_stats((0.654, 0.481, 0.0))
    assert chroma == pytest.approx(0.654) and 0.3 < lum < 0.6
    assert pigment_stats(None) == (None, None)


# ---- scene conditions -----------------------------------------------------------------------------------------
def _script(world="rain_courtyard", wetness=0.0, effects=()):
    return {"world": {"id": world, "params": {"wetness": wetness}},
            "effects": [{"id": e, "params": {}} for e in effects]}


def test_rain_or_wet_worlds_weather_the_car_and_light_its_lamps():
    c = conditions(_script(effects=("rain",)), outdoor=True)
    assert c["wet"] and c["outdoor"] and c["roadFilm"] == 1.0 and c["brakeDust"] == pytest.approx(0.9)
    assert c["lampsOn"]
    assert conditions(_script(wetness=0.6), outdoor=True)["wet"]
    assert conditions(_script(world="night_street", effects=("wet_surface",)), outdoor=True)["wet"]


def test_a_dry_outdoor_world_keeps_light_road_dust_and_a_studio_stays_clean():
    dry = conditions(_script(world="golden_field"), outdoor=True)
    assert not dry["wet"] and 0 < dry["roadFilm"] < 0.5 and 0 < dry["brakeDust"] < 0.9 and not dry["lampsOn"]
    dusk = conditions({"world": {"id": "golden_field", "params": {"timeOfDay": "dusk"}}}, outdoor=True)
    assert dusk["lampsOn"] and conditions(_script(world="night_street"), outdoor=True)["lampsOn"]
    studio = conditions(_script(world="studio_cyc"), outdoor=False)
    assert studio["roadFilm"] == 0 and studio["brakeDust"] == 0 and not studio["lampsOn"]


# ---- wheel geometry labels (placed metres) --------------------------------------------------------------------
WHEEL = {"center": [0.8, -1.2, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "width": 0.26,
         "tyreBand": [0.74, 1.0]}


def _ring(r, x, n=64):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.stack([np.full(n, x), WHEEL["center"][1] + r * np.cos(t), WHEEL["center"][2] + r * np.sin(t)], 1)


def test_part_labels_split_a_wheel_into_tyre_rim_disc_and_caliper():
    tyre = np.concatenate([_ring(0.35, 0.72), _ring(0.35, 0.88), _ring(0.27, 0.70), _ring(0.27, 0.90)])
    assert part_labels(tyre, [WHEEL]) == {"tyre": len(tyre)}
    rim = np.concatenate([_ring(0.24, 0.85), _ring(0.05, 0.84)])
    assert part_labels(rim, [WHEEL]) == {"rim": len(rim)}
    disc = np.concatenate([_ring(0.19, 0.79), _ring(0.19, 0.81), _ring(0.08, 0.80)])
    assert part_labels(disc, [WHEEL]) == {"disc": len(disc)}
    caliper = np.array([[0.78, -1.2 + dy, 0.35 + 0.18 + dz] for dy in (-0.08, 0.08) for dz in (-0.03, 0.04)])
    assert part_labels(caliper, [WHEEL]) == {"caliper": len(caliper)}


def test_a_flat_hub_face_is_no_brake_disc():
    hub = np.concatenate([_ring(0.135, 0.81), _ring(0.135, 0.82), _ring(0.03, 0.815)])   # the fixture's hub, 0.39 r
    assert "disc" not in part_labels(hub, [WHEEL])


def test_part_labels_ignore_geometry_off_the_wheels():
    body = np.array([[0.0, 0.0, 0.8], [0.5, 1.0, 1.0], [0.9, -1.2, 0.9]])
    assert part_labels(body, [WHEEL]) == {}
    assert part_labels(np.zeros((0, 3)), [WHEEL]) == {}
    assert part_labels(body, []) == {}


def test_night_street_in_overcast_day_is_daylight_not_night():
    """night_street's timeOfDay overcast_day is a daylight street: a dry one leaves the lamps as uploaded;
    night, dusk and twilight (and the world's default, night) light them."""
    def street(tod=None, wet=0.0):
        p = {"wetness": wet} if tod is None else {"wetness": wet, "timeOfDay": tod}
        return {"world": {"id": "night_street", "params": p}, "effects": []}
    assert not conditions(street("overcast_day"), outdoor=True)["lampsOn"]
    for tod in (None, "night", "dusk", "twilight"):
        assert conditions(street(tod), outdoor=True)["lampsOn"], tod
    assert conditions(street("overcast_day", wet=1.0), outdoor=True)["lampsOn"]   # the rain film's DRLs


def test_after_dark_the_prep_knows_it_is_dark():
    """Round 6: a night world marks the car's conditions dark (the lamps then burn at LAMP_DARK_SCALE of the daylight
    film's strength); a wet overcast street keeps its DRLs at full strength and is not dark; a studio never is."""
    def street(tod=None, wet=0.0):
        p = {"wetness": wet} if tod is None else {"wetness": wet, "timeOfDay": tod}
        return {"world": {"id": "night_street", "params": p}, "effects": []}
    for tod in (None, "night", "dusk"):
        assert conditions(street(tod), outdoor=True)["dark"], tod
    assert not conditions(street("overcast_day", wet=1.0), outdoor=True)["dark"]
    assert not conditions(street("night"), outdoor=False)["dark"]
