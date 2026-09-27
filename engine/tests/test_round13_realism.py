"""Round 13 realism layers, pure: the night street's practicals-only light (no rig, a stray lamp through the side
glass) and the road's mess; the field's ground (cover to the body, a dip under each tyre, irregular pressing,
weeds where the camera looks); the courtyard's depth layers and grime; the committed scripts' round-13 values."""
import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.tests.test_director_package import _p

ROOT = Path(__file__).parents[2]


def _load(s):
    return json.loads((ROOT / "harness" / "realism" / f"{s}.json").read_text(encoding="utf-8"))


def test_practicals_only_is_a_rig_free_night_street_light():
    cat = Catalog.load()
    m = cat.get("lighting", "practicals_only")
    assert m is not None and m["directorSelectable"] is False          # new blocks land off the menu
    assert set(m["params"]) == {"exposure", "straySpill"}
    assert "practicals_only" in cat.get("world", "night_street")["lightingPairs"]
    src = (ROOT / "engine" / "blocks" / "lighting" / "practicals_only" / "build.py").read_text(encoding="utf-8")
    for rig in ("location_key import build", "area_light", "rim_neon_layout", "realise(", "black_card"):   # no rig
        assert rig not in src


def test_the_stray_spill_aims_past_the_cabin_away_from_the_lamp():
    from engine.blocks.lighting.practicals_only.build import stray_aim
    c, lamp = (0.0, 0.0, 1.0), (4.0, -2.0, 4.3)
    ax, ay, az = stray_aim(c, 1.8, lamp)
    assert az == c[2]
    d0 = math.hypot(lamp[0] - c[0], lamp[1] - c[1])
    assert math.hypot(lamp[0] - ax, lamp[1] - ay) > d0                  # beyond the centre, on the far side
    assert math.isclose(math.hypot(ax, ay), 0.35 * 1.8, rel_tol=1e-9)


def test_round13_night_script_uses_the_street_alone():
    sn = _load("street_night")
    assert sn["lighting"]["id"] == "practicals_only"
    assert sn["lighting"]["params"] == {"exposure": 1.0, "straySpill": 1.0}     # round 14: lifted   # round 15: 0.8 -> 1.0
    assert sn["grade"]["params"]["grain"] == 0.8                         # KEEP: grain, the darker noir grade
    assert sn["world"]["params"]["neonAmount"] == 0.0


def test_the_committed_night_reaches_the_render_as_asked():
    """The checker keeps practicals_only on the committed night script (r12's ask was swapped to neon rims)."""
    from harness import realism_round as rr
    from engine.checker import check
    import copy
    s = rr.load_script("street_night")
    r = check(copy.deepcopy(s), rr.load_profile(), Catalog.load())
    assert r.ok and r.script["lighting"] == s["lighting"]
    assert "lighting_world_mismatch" not in {i.code for i in r.issues}


# ---- field (owner's r12 review: no bare strip round the body, a dip under each tyre, irregular pressing)
def _frame(p):
    return (p.center[0], p.center[1]), p.half[0], p.half[1]


def test_the_cover_grows_to_the_body_pressed_under_its_edge_and_never_deep_under_it():
    from engine.worlds import field_layout as F
    p = _p("sports_car")
    (cx, cy), hx, hy = _frame(p)
    assert F.body_cap(cx, cy, _frame(p)) == 0.0                                     # nothing deep under the car
    edge = F.body_cap(cx, cy - hy + 0.1, _frame(p))                                  # under the nose's overhang
    assert 0 < edge <= p.vehicle["rideHeightM"]
    assert F.body_cap(cx, cy - hy - 0.5, _frame(p)) > F.body_cap(cx, cy - hy - 0.1, _frame(p)) > edge
    lay = F.layout(p, seed=3, cameras=[(cx + 4.4, cy - 7.7, 0.84)])
    band = [g for g in lay["farGrass"] if abs(g[0] - cx) <= hx + 0.15 and abs(g[1] - cy) <= hy + 0.15]
    assert len(band) > 50                                                            # the strip is covered
    for x, y, _, h, _w in band:
        assert h <= F.body_cap(x, y, _frame(p)) + 1e-9


def test_each_tyre_sits_in_a_dip_as_deep_as_its_share_of_the_weight():
    from engine.worlds import field_layout as F
    p = _p("sports_car")
    dips = F.tyre_dips(p)
    assert len(dips) == 4 and len({round(d[4], 5) for d in dips}) > 1                 # uneven weight, uneven dips
    for (zx, zy), _, ha, hl, depth in dips:
        assert F.ground_dz(zx, zy, dips) == pytest.approx(-depth)
        assert 0.01 < depth < 0.04
    (cx, cy), hx, hy = _frame(p)
    assert F.ground_dz(cx, cy, dips) == 0.0 and F.ground_dz(cx + hx + 0.6, cy, dips) == 0.0
    assert max(F.ground_dz(dips[0][0][0] + dips[0][2] * k, dips[0][0][1], dips) for k in (1.2, 1.4, 1.6)) > 0.0
    assert F.tyre_dips(_p("mid_century_lounge_chair")) == []


def test_the_pressed_ring_round_a_tyre_is_irregular():
    from engine.worlds import field_layout as F
    p = _p("sports_car")
    zones = F.tyre_zones(p)
    (zx, zy), _, ha, hl = zones[0]
    assert F.trample_seeded(zx, zy, zones, 7) == pytest.approx(F.TRAMPLE_FLOOR)
    d = ha + 0.8 * F.TRAMPLE_RAMP_M
    ring = [F.trample_seeded(zx + d * math.cos(a / 20 * math.tau), zy + d * math.sin(a / 20 * math.tau), zones, 7)
            for a in range(20)]
    assert min(ring) < 0.9 and max(ring) == 1.0                                       # flat here, standing there


def test_a_few_weeds_gather_round_the_body_not_more_grass_everywhere():
    from engine.worlds import field_layout as F
    p = _p("sports_car")
    cam = (p.center[0] + 4.4, p.center[1] - 7.7, 0.84)
    lay = F.layout(p, seed=3, cameras=[cam])
    (cx, cy), hx, hy = _frame(p)
    R = F.NEAR_WEEDS["ringM"]
    w = F.near_weeds(p, 3, F._sight_lines(p, [cam]), max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest), F.tyre_zones(p))
    assert 20 < len(w) and all(abs(x - cx) <= hx + R + 1.0 and abs(y - cy) <= hy + R + 1.0 for x, y, *_ in w)
    assert set(map(tuple, w)) <= set(map(tuple, lay["flora"]["weeds"]))
    assert len(lay["blades"]) == len(F.layout(p, seed=3, cameras=[cam])["blades"])


def test_no_soil_shows_but_under_a_tyre():
    src = (ROOT / "engine" / "blocks" / "world" / "golden_field" / "build.py").read_text(encoding="utf-8")
    assert "body = 0.75" not in src and "mask.append(tyre)" in src and "ground_dz" in src


# ---- courtyard (owner's r12 review: depth layers through the fog instead of one blank wall)
def _court_hook():
    from harness import realism_round as rr
    from engine.tests.test_round11_realism import _hook
    s = rr.load_script("court")
    prm = s["shots"][0]["camera"]["params"]
    p = _p("sports_car")
    return p, _hook(p, Catalog.load(), **{k: prm[k] for k in ("azimuthDeg", "lensMm", "heightFrac")}), s["seed"]


def test_the_court_background_has_near_mid_and_far_layers_in_the_hook_frame():
    from engine.geometry import box_corners, project
    from engine.worlds import courtyard_layout as C
    p, hero, seed = _court_hook()
    lay = C.layout(p, seed, "full", 24.0, hero=hero, aspect="9:16")
    L = C.depth_layers(p, hero, "9:16", seed, lay["exclusion"], lay["props"], max_dist=150.0)
    assert L == C.depth_layers(p, hero, "9:16", seed, lay["exclusion"], lay["props"], max_dist=150.0)   # pure
    cx, cy = p.center[0], p.center[1]
    dist = lambda it: math.hypot(it[0] - cx, it[1] - cy)  # noqa: E731
    near = L["bollards"] + L["trunks"]
    assert near and len(L["railing"]) > 5 and len(L["midTrees"]) >= 6 and len(L["farBlocks"]) >= 3
    assert max(dist(i) for i in near) < min(dist(i) for i in L["midTrees"]) < min(dist(i) for i in L["farBlocks"])
    car = [project(hero, c, "9:16") for c in box_corners(p.boundsMin, p.boundsMax)]
    x0, x1 = min(c[0] for c in car), max(c[0] for c in car)
    for x, y, h in L["bollards"]:                      # near pieces stand beside the car, never in front of it
        q = project(hero, (x, y, 0.5), "9:16")
        assert q[2] > 0 and abs(q[0]) < 1.0 and (q[0] < x0 or q[0] > x1)
    e = lay["exclusion"]
    assert not any(e[0] <= x <= e[2] and e[1] <= y <= e[3] for x, y, *_ in near)
    assert len({b[4] for b in L["farBlocks"]}) >= 1 and all(b[2][2] >= 6.0 for b in L["farBlocks"])
    assert C.depth_layers(p, None, "9:16", seed, lay["exclusion"]) == {k: [] for k in L}


def test_the_court_layers_fog_grades_with_distance_and_the_ground_carries_grime():
    from engine.blocks.world.rain_courtyard import build as B
    near, mid, far = (B.LAYER_HAZE[k] for k in ("near", "mid", "far"))
    assert near[1] < mid[1] < far[1]                               # the cap rises with distance
    assert max(B.LAYER_RGB["far"][0]) < 0.06                       # far masses stay dark: silhouettes, not slabs
    assert 0.5 < B.GRIME["base"] < 1.0 and B.GRIME["stainDark"] < B.GRIME["patchDark"] < 1.0
