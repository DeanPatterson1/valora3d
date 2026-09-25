"""Block recipe step 1: every phase-5 block's manifest against its task's table (plan chunks 2-6).
New blocks land directorSelectable false and are flipped in Task 88 (review amendment 63->88)."""
from engine.catalog import Catalog


def _m(kind, bid):
    m = Catalog.load().get(kind, bid)
    assert m is not None, f"{kind}/{bid} missing"
    return m


def _param(m, name, typ, default, lo=None, hi=None, values=None):
    p = m["params"][name]
    assert p["type"] == typ and p["default"] == default, (name, p)
    if lo is not None:
        assert (p["min"], p["max"]) == (lo, hi), (name, p)
    if values is not None:
        assert p["values"] == values, (name, p)


def test_ground_fog_manifest():                                     # Task 60
    m = _m("effect", "ground_fog")
    _param(m, "heightM", "number", 0.4, 0.1, 1.5)
    _param(m, "density", "number", 0.4, 0.0, 1.0)
    _param(m, "mode", "enum", "fog", values=["fog", "mist"])
    _param(m, "tint", "enum", "neutral", values=["neutral", "warm", "cool"])
    assert m["physics"] == {"taxonomy": ["GS-04"], "state": "stateless", "windDriven": True,
                            "windCalibration": {"unit": "drift m/s", "perMs": 0.5},
                            "requiresWorld": {"hasGround": True}}
    assert m["atmosphere"] is True and m["maxPerClip"] == 1 and m["costWeight"] == 2.0
    assert m["tierMax"] == "T3" and m["subjectSizeM"] == [0.05, 30.0]
    assert m["capabilities"] == ["atmosphere.fog"]
    assert m["tags"]["mood"] == ["moody", "night", "mysterious"] and m["tags"]["energy"] == ["calm", "medium"]
    assert m.get("directorSelectable") is False                     # flipped in Task 88


def test_rain_courtyard_manifest():                                 # Task 63 (+ amendments 63, 63->88)
    m = _m("world", "rain_courtyard")
    _param(m, "wetness", "number", 0.0, 0.0, 1.0)
    _param(m, "timeOfDay", "enum", "overcast_day", values=["overcast_day", "dusk"])
    _param(m, "dressing", "enum", "full", values=["full", "sparse"])
    facts = {k: m[k] for k in ("hasGround", "groundType", "hasFoliage", "outdoor", "weathers", "temperature",
                               "windDefault", "timeOfDay", "toneParam", "driveLaneM")}
    assert facts == {"hasGround": True, "groundType": "asphalt", "hasFoliage": True, "outdoor": True,
                     "weathers": ["dry", "wet", "rain", "fog"], "temperature": "mild", "windDefault": 0.8,
                     "timeOfDay": {"param": "timeOfDay", "values": ["overcast_day", "dusk"]}, "toneParam": None,
                     "driveLaneM": 24.0}
    assert m["subjectSizeM"] == [0.03, 6.0] and m["costWeight"] == 3.0 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["world.street", "world.nature"]
    assert m["tags"]["mood"] == ["moody", "cinematic", "rainy"] and m["tags"]["palette"] == ["cool"]
    assert m.get("directorSelectable") is False


def test_night_street_manifest():                                   # Task 70 (+ amendments 70, 63->88)
    m = _m("world", "night_street")
    _param(m, "timeOfDay", "enum", "night", values=["dusk", "night"])
    _param(m, "neonHue", "number", 285.0, 0.0, 360.0)
    _param(m, "neonAmount", "number", 0.5, 0.0, 1.0)
    _param(m, "windowsLit", "number", 0.4, 0.0, 1.0)
    _param(m, "wetness", "number", 0.6, 0.0, 1.0)
    facts = {k: m[k] for k in ("hasGround", "groundType", "hasFoliage", "outdoor", "weathers", "temperature",
                               "windDefault", "timeOfDay", "toneParam", "driveLaneM")}
    assert facts == {"hasGround": True, "groundType": "asphalt", "hasFoliage": False, "outdoor": True,
                     "weathers": ["dry", "wet", "rain", "fog"], "temperature": "mild", "windDefault": 0.8,
                     "timeOfDay": {"param": "timeOfDay", "values": ["dusk", "night"]}, "toneParam": None,
                     "driveLaneM": 30.0}
    assert m["subjectSizeM"] == [0.03, 8.0] and m["costWeight"] == 2.6 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["world.street"]
    assert m["tags"] == {"mood": ["night", "neon", "cinematic", "moody"], "energy": ["medium", "hype"],
                         "palette": ["cool", "neon"]}
    assert "wet_surface" in m["description"] and "takes over" in m["description"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_golden_field_manifest():                                   # Task 71 (+ amendments 71, 63->88)
    m = _m("world", "golden_field")
    _param(m, "timeOfDay", "enum", "golden", values=["dawn", "golden", "dusk", "overcast"])
    _param(m, "sunAzimuthDeg", "number", 0.0, -180.0, 180.0)           # amendment: 0, layer 1 varies it
    _param(m, "grassHeightM", "number", 0.45, 0.1, 1.2)
    _param(m, "crop", "enum", "grass", values=["grass", "wheat", "wildflowers"])
    _param(m, "track", "bool", False)
    facts = {k: m[k] for k in ("hasGround", "groundType", "hasFoliage", "outdoor", "weathers", "temperature",
                               "windDefault", "timeOfDay", "toneParam", "driveLaneM")}
    assert facts == {"hasGround": True, "groundType": "grass", "hasFoliage": True, "outdoor": True,
                     "weathers": ["dry", "wet", "fog", "snow"], "temperature": "mild", "windDefault": 0.8,
                     "timeOfDay": {"param": "timeOfDay", "values": ["dawn", "golden", "dusk", "overcast"]},
                     "toneParam": None, "driveLaneM": 40.0}
    assert m["subjectSizeM"] == [0.05, 8.0] and m["costWeight"] == 3.2 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["world.nature"]
    assert m["tags"] == {"mood": ["warm", "nostalgic", "calm", "premium"], "energy": ["calm", "medium"],
                         "palette": ["warm", "golden"]}
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_drop_settle_manifest():                                    # Task 74 (+ amendments 74, 63->88)
    m = _m("motion", "drop_settle")
    _param(m, "heightFrac", "number", 0.6, 0.2, 1.5)
    _param(m, "bounces", "number", 1, 0, 3)
    _param(m, "restitution", "number", 0.35, 0.2, 0.5)
    _param(m, "timeScale", "number", 0.5, 0.3, 1.0)
    _param(m, "startS", "number", 0.3, 0.0, 8.0)
    _param(m, "tiltDeg", "number", 4.0, 0.0, 12.0)
    assert m["subjectMotion"] == {"lands": True, "stops": True} and m["physics"]["timeScaleParam"] == "timeScale"
    assert m["subjectSizeM"] == [0.02, 3.0] and m["capabilities"] == ["motion.drop"] and m["tierMax"] == "T3"
    assert m["tags"]["mood"] == ["playful", "premium"] and m["tags"]["energy"] == ["medium", "hype"]
    assert m["placement"] == "ground" and m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_float_drift_and_plinth_spin_manifests():                    # Task 75 (+ amendments motion rules, 63->88)
    m = _m("motion", "float_drift")
    _param(m, "liftFrac", "number", 0.15, 0.05, 0.4)
    _param(m, "bobFrac", "number", 0.02, 0.01, 0.03)
    _param(m, "bobHz", "number", 0.3, 0.2, 0.5)
    _param(m, "yawDegS", "number", 6.0, -20.0, 20.0)
    assert m["subjectMotion"] == {} and m["placement"] == "float" and m["capabilities"] == ["motion.float"]
    assert m["rateCap"]["degS"] == 45.0 and m.get("directorSelectable") is False and m["landsIn"] == "Task 88"
    m = _m("motion", "plinth_spin")
    _param(m, "turnDeg", "number", 90.0, 30.0, 180.0)
    _param(m, "turnS", "number", 6.0, 2.0, 10.0)
    _param(m, "startS", "number", 1.0, 0.0, 6.0)
    assert m["subjectMotion"] == {"stops": True} and m["standsOn"] == "plinth" and m["needsCameraMove"] is True
    assert m["rateCap"]["degS"] == 45.0 and m["subjectSizeM"] == [0.02, 2.5] and m["capabilities"] == ["motion.spin"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_slide_in_manifest():                                       # Task 76 (+ amendments 76, 63->88)
    m = _m("motion", "slide_in")
    _param(m, "distanceFrac", "number", 0.6, 0.1, 3.0)
    _param(m, "durationS", "number", 1.4, 0.6, 3.0)
    _param(m, "startS", "number", 0.2, 0.0, 8.0)
    _param(m, "directionDeg", "number", 0.0, -180.0, 180.0)             # amendment: 0, layer 1 varies it
    assert m["subjectMotion"] == {"translates": True, "stops": True} and m["distanceParam"] == "distanceFrac"
    assert m["capabilities"] == ["motion.slide"] and m["placement"] == "ground"
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_roll_and_topple_manifests():                                # Task 77 (+ amendments 77, 63->88)
    m = _m("motion", "roll")
    _param(m, "distanceFrac", "number", 1.5, 0.5, 4.0)
    _param(m, "direction", "enum", "right", values=["left", "right"])
    _param(m, "startS", "number", 0.5, 0.0, 6.0)
    assert m["requiresProfile"] == ["rollAxis"] and m["subjectMotion"] == {"translates": True, "stops": True}
    assert m["distanceParam"] == "distanceFrac" and m["capabilities"] == ["motion.roll"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"
    m = _m("motion", "topple")
    _param(m, "direction", "enum", "right", values=["left", "right"])
    _param(m, "startS", "number", 0.5, 0.0, 6.0)
    _param(m, "rock", "bool", False)
    assert m["requiresProfile"] == ["supportPolygon"] and m["subjectMotion"] == {"stops": True, "lands": True}
    assert m["capabilities"] == ["motion.topple"] and m.get("directorSelectable") is False


def test_toss_tumble_manifest():                                    # Task 78 (+ amendments 78, 63->88)
    m = _m("motion", "toss_tumble")
    _param(m, "arcHeightFrac", "number", 1.2, 0.5, 3.0)
    _param(m, "spins", "number", 1, 1, 3)                              # amendment 78: whole turns only
    _param(m, "timeScale", "number", 0.45, 0.3, 1.0)
    _param(m, "startS", "number", 0.4, 0.0, 6.0)
    _param(m, "direction", "enum", "right", values=["left", "right"])
    assert m["subjectMotion"] == {"translates": True, "lands": True, "stops": True}
    assert m["subjectSizeM"] == [0.02, 1.5] and m["rateCap"]["degS"] == 360.0     # amendment: perceived cap
    assert m["physics"]["timeScaleParam"] == "timeScale" and m["capabilities"] == ["motion.tumble"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_drive_manifest():                                          # Task 79 (+ amendments 79, 63->88)
    m = _m("motion", "drive")
    _param(m, "path", "enum", "straight", values=["straight", "arc_left", "arc_right", "s_curve", "stop"])
    _param(m, "accel", "enum", "cruise", values=["cruise", "launch", "brake_to_stop"])
    _param(m, "speedKmh", "number", 40.0, 5.0, 120.0)
    _param(m, "facing", "enum", "auto", values=["auto", "forward", "reverse"])
    _param(m, "startS", "number", 0.5, 0.0, 8.0)                        # amendment 79: the drive window
    _param(m, "driveS", "number", 4.0, 1.0, 10.0)
    assert m["requiresProfile"] == ["wheels"] and m["subjectSizeM"] == [0.03, 8.0]   # amendment: 0.03 m
    assert m["physics"]["taxonomy"] == ["VD-02", "VD-03", "VD-04", "VD-05", "VD-06"] and m["vehicle"] is True
    assert m["capabilities"] == ["motion.drive"] and m["tags"]["mood"] == ["cinematic", "hype", "night"]
    assert "distanceParam" not in m                   # the studio refuses a drive (path_through_world), never crawls it
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"
    assert "rollDegPerG" not in _m("realism", "suspension")["params"]   # by vehicle class, not a param (baseline)


def _camera_common(m, move, capability, framing="full", follows="anchor"):
    """Chunk 6: every camera declares framing, move, follows, constantSpeed false and tierMax T3."""
    assert m["framing"] == framing and m["move"] == move and m.get("follows", "anchor") == follows
    assert m.get("constantSpeed", False) is False and m["tierMax"] == "T3"
    assert m["capabilities"] == [capability]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_reveal_rise_manifest():                                    # Task 80
    m = _m("camera", "reveal_rise")
    _camera_common(m, "crane", "camera.crane")
    _param(m, "startHeightFrac", "number", 0.15, 0.05, 0.4)
    _param(m, "holdFrac", "number", 0.2, 0.0, 0.3)
    _param(m, "endHeightFrac", "number", 0.9, 0.4, 1.5)
    _param(m, "easing", "enum", "out_quad", values=["out_quad", "out_cubic", "in_out_cubic"])
    assert m["hookable"] is False


WEATHER_OUT = {"outdoor": True, "hasGround": True}


def test_rain_manifest():                                           # Task 64 (+ amendment 64: 0 = from intensity)
    m = _m("effect", "rain")
    _param(m, "intensity", "enum", "steady", values=["drizzle", "steady", "downpour"])
    _param(m, "rateMmH", "number", 0.0, 0.0, 50.0)
    _param(m, "dropSizeMm", "number", 0.0, 0.0, 4.0)
    _param(m, "impacts", "bool", True)
    _param(m, "backlight", "number", 0.6, 0.0, 1.0)
    ph = m["physics"]
    assert (ph["taxonomy"], ph["state"], ph["windDriven"]) == (["FL-01", "FL-02", "LM-05"], "stateless", True)
    assert ph["windCalibration"] == {"unit": "slant: atan(wind/fall)", "perMs": 1.0}
    assert ph["requiresWorld"] == WEATHER_OUT
    assert ph["couplings"] == ["wet_surface", "droplets"] and ph["excludes"] == ["snow"]      # Task 67's last step
    assert m["maxPerClip"] == 1 and m["costWeight"] == 1.8 and m["tierMax"] == "T3" and m["subjectSizeM"] == [0.05, 30.0]
    assert m["capabilities"] == ["weather.rain"]
    assert m["tags"]["mood"] == ["moody", "rainy", "night", "cinematic"] and m["tags"]["palette"] == ["cool"]
    assert m["tags"]["energy"] == ["calm", "medium", "hype"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_wet_surface_manifest():                                    # Task 65
    m = _m("effect", "wet_surface")
    _param(m, "wetness", "number", 0.8, 0.3, 1.0)
    _param(m, "puddles", "number", 0.4, 0.0, 1.0)
    _param(m, "ripples", "enum", "auto", values=["auto", "off"])
    _param(m, "drips", "bool", True)
    assert m["physics"] == {"taxonomy": ["FL-06", "FL-07", "FL-20"], "state": "stateless", "requiresWorld": WEATHER_OUT}
    assert m["maxPerClip"] == 1 and m["costWeight"] == 1.1 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["surface.wet"]
    assert m["tags"]["mood"] == ["moody", "rainy", "night", "fresh"] and m["tags"]["energy"] == ["calm", "medium", "hype"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_droplets_manifest():                                       # Task 66
    m = _m("effect", "droplets")
    _param(m, "density", "number", 0.5, 0.1, 1.0)
    _param(m, "sizeMm", "number", 1.5, 0.5, 4.0)
    _param(m, "zone", "enum", "up_facing", values=["all", "up_facing"])
    _param(m, "drips", "bool", True)
    assert m["physics"] == {"taxonomy": ["FL-03", "FL-20", "LM-04"], "state": "stateless"}   # no requiresWorld
    assert m["requiresProfile"] == ["upFacing"] and m["maxPerClip"] == 1 and m["costWeight"] == 1.2
    assert m["tierMax"] == "T3" and m["capabilities"] == ["liquid.droplets"]
    assert m["tags"]["mood"] == ["fresh", "rainy", "premium"] and m["tags"]["energy"] == ["calm", "medium"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_snow_manifest():                                           # Task 67
    m = _m("effect", "snow")
    _param(m, "rate", "number", 0.4, 0.1, 1.0)
    _param(m, "flakeMm", "number", 6.0, 2.0, 15.0)
    _param(m, "accumulationMm", "number", 5.0, 0.0, 30.0)
    _param(m, "onSubject", "bool", True)
    assert m["physics"] == {"taxonomy": ["PT-04"], "state": "stateless", "windDriven": True,
                            "windCalibration": {"unit": "drift m/s", "perMs": 0.9}, "requiresWorld": WEATHER_OUT,
                            "excludes": ["rain"]}
    assert m["maxPerClip"] == 1 and m["costWeight"] == 1.6 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["weather.snow"] and m["tags"]["palette"] == ["cool", "neutral"]
    assert m["tags"]["mood"] == ["calm", "wintry", "premium", "nostalgic"] and m["tags"]["energy"] == ["calm", "medium"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_lens_drops_manifest():                                     # Task 68
    m = _m("effect", "lens_drops")
    _param(m, "shot", "number", 0, 0, 20)
    _param(m, "amount", "number", 0.3, 0.0, 1.0)
    assert m["physics"] == {"taxonomy": ["LM-06"], "state": "stateless", "requiresWorld": {"outdoor": True}}
    assert m["maxPerClip"] == 1 and m["costWeight"] == 1.0 and m["tierMax"] == "T3"
    assert m["capabilities"] == ["camera.lens_drops"]
    assert m["tags"]["mood"] == ["cinematic", "rainy"] and m["tags"]["energy"] == ["medium", "hype"]
    assert m.get("directorSelectable") is False and m["landsIn"] == "Task 88"


def test_dice_roll_only_studio_worlds_until_task_87():
    """Amendment 63->88: dice.json 'worlds' keeps new worlds unrollable even once one is selectable."""
    import copy
    from engine.director.axes import DICE, axis_values
    from engine.tests.test_director_package import _p
    cat = Catalog.load()
    grown = copy.copy(cat)
    grown._blocks = copy.deepcopy(cat._blocks)
    grown._blocks[("world", "rain_courtyard")]["directorSelectable"] = True
    fmt = {"aspect": "9:16", "durationS": 10, "fps": 30}
    assert DICE["worlds"] == ["studio_cyc"]
    assert axis_values(_p("sports_car"), grown, fmt)["world"] == ["studio_cyc"]
    assert "rain_courtyard" in axis_values(_p("sports_car"), grown, fmt, rollable=False)["world"]


def test_courtyard_rejects_a_subject_over_6_m():
    import dataclasses
    import json
    from engine.checker import check
    from engine.tests.test_director_package import _p
    from engine.tests.test_growth_floor import T3
    p = _p("sports_car")
    k = 8.0 / p.longest
    big = dataclasses.replace(p, sizeM=[v * k for v in p.sizeM], boundsMin=[v * k for v in p.boundsMin],
                              boundsMax=[v * k for v in p.boundsMax])
    s = json.loads(json.dumps(T3))
    s["world"] = {"id": "rain_courtyard", "params": {}}
    r = check(s, big, Catalog.load())
    assert ("subject_size_unsupported", "world") in {(i.code, i.path) for i in r.issues}


def test_pending_blocks_keep_their_asks_offered():
    """A block that lands unselectable (amendment 63->88) is not a harness-only control: its tags stay in
    the unsupported enum until Task 88 switches it on."""
    from engine.director.output_schema import harness_only_tags
    cat = Catalog.load()
    pending = {("effect", "ground_fog"): "atmosphere.fog", ("world", "rain_courtyard"): "world.street",
               ("effect", "rain"): "weather.rain", ("effect", "wet_surface"): "surface.wet",
               ("effect", "droplets"): "liquid.droplets", ("effect", "snow"): "weather.snow",
               ("effect", "lens_drops"): "camera.lens_drops", ("world", "night_street"): "world.street",
               ("world", "golden_field"): "world.nature", ("lighting", "hard_sun"): "lighting.sun",
               ("lighting", "rim_neon"): "lighting.neon", ("lighting", "hdri_only"): "lighting.natural",
               ("motion", "drive"): "motion.drive",
               ("motion", "toss_tumble"): "motion.tumble",
               ("motion", "roll"): "motion.roll",
               ("motion", "topple"): "motion.topple",
               ("motion", "slide_in"): "motion.slide",
               ("motion", "float_drift"): "motion.float",
               ("motion", "plinth_spin"): "motion.spin",
               ("motion", "drop_settle"): "motion.drop",
               ("camera", "reveal_rise"): "camera.crane"}
    for (kind, bid), cap in pending.items():
        assert cat.get(kind, bid)["landsIn"] == "Task 88" and cap in cat.get(kind, bid)["capabilities"]
    assert not ({"world.nature"} | set(pending.values())) & harness_only_tags(cat)


def test_a_rain_script_gets_wet_ground_from_the_real_catalog():
    """Chunk 3 look-check (t64 downpour v2 showed dry asphalt): that render predates wet_surface (Task 65).
    With the real catalog the checker now couples wet_surface (and droplets) onto any rain script."""
    from engine.checker import check
    from engine.tests.test_director_package import _p
    from engine.tests.test_growth_floor import FLOORS
    make, model = FLOORS["effect/rain"]
    s = make()
    assert [e["id"] for e in s["effects"]].count("wet_surface") == 0
    r = check(s, _p(model), Catalog.load())
    ids = [e["id"] for e in r.script["effects"]]
    assert r.ok and ids.index("wet_surface") == ids.index("rain") + 1
