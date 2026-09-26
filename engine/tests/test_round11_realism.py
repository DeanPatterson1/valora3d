"""Round 11 realism layers, pure: the camera's capture glow, the courtyard's camera-aware anchors, the night street's
hook dressing, the field's layered horizon and the committed shot scripts' loaded tyres."""
import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.geometry import project
from engine.tests.test_director_package import _p

HOOK = {"id": "low_hero_push", "params": {"azimuthDeg": -58, "distance": 6.5, "lensMm": 40, "heightFrac": 0.33,
                                          "pushFrac": 0.0}}


def _hook(p, cat, **over):
    m = cat.get("camera", "low_hero_push")
    params = {k: v["default"] for k, v in m["params"].items()}
    params.update({**HOOK["params"], **over})
    return cat.load_camera_path("low_hero_push")(params, p, 0.5, None)


def test_capture_glow_is_wider_and_lower_after_dark():
    from engine.grade_plan import CAPTURE, with_capture
    day = with_capture({"x": 1}, {"world": {"id": "rain_courtyard", "params": {"timeOfDay": "overcast_day"}}})
    night = with_capture({"x": 1}, {"world": {"id": "night_street", "params": {"timeOfDay": "night"}}})
    assert day["x"] == 1 and day["capture"] is CAPTURE["day"] and night["capture"] is CAPTURE["night"]
    assert "mist" in night["capture"] and "mist" not in day["capture"]
    # by day the glow stays above an overcast sky's own radiance (~2.5-3.5 scene-linear): emitters only
    assert day["capture"]["glow"]["threshold"] > 3.5 > night["capture"]["glow"]["threshold"]


def test_court_anchors_stand_in_the_hook_frame_and_off_the_subject():
    from engine.worlds import courtyard_layout as C
    cat = Catalog.load()
    p = _p("sports_car")
    hero = _hook(p, cat)
    lay = C.layout(p, 7, "full", 24.0, hero=hero, aspect="9:16")
    a = C.court_anchors(p, hero, "9:16", 7, lay["exclusion"])
    assert a == C.court_anchors(p, hero, "9:16", 7, lay["exclusion"])            # seeded, pure
    assert a["lamps"] and a["blocks"] and len(a["leaves"]) == C.ANCHOR_LEAVES
    for x, y in a["lamps"]:
        tx, ty, d = project(hero, (x, y, C.ANCHOR_LAMP_H), "9:16")
        assert d > 0 and abs(tx) < 0.9                                          # its head is in frame
    e = lay["exclusion"]
    assert not any(e[0] <= lf["xy"][0] <= e[2] and e[1] <= lf["xy"][1] <= e[3] for lf in a["leaves"])
    assert C.court_anchors(p, None, "9:16", 7, e) == {"lamps": [], "blocks": [], "bench": None, "leaves": []}


def test_hero_dressing_is_seen_and_never_blocks_the_subject():
    from engine.worlds import street_layout as S
    cat = Catalog.load()
    p = _p("sports_car")
    hero = _hook(p, cat, azimuthDeg=-78)
    cams = [tuple(hero.position)]
    lay = S.layout(p, 5, hero=hero, aspect="9:16", cameras=cams)
    extra = S.hero_dressing(p, lay, hero, "9:16", 5, cams)
    assert extra == S.hero_dressing(p, lay, hero, "9:16", 5, cams)
    assert extra and all(S.seen(hero, it, "9:16") for it in extra)
    pts = S._sight(p)
    for it in extra:
        assert not any(S.segment_hits(c, q, it["min"], it["max"]) for c in cams for q in pts)
    assert S.hero_dressing(p, lay, None, "9:16", 5) == []


def test_the_field_horizon_is_layered_behind_the_fence():
    from engine.worlds import field_layout as F
    p = _p("sports_car")
    cam = (4.4, -7.7, 0.8)
    L = F.horizon_layers(p, 5, [cam])
    assert L == F.horizon_layers(p, 5, [cam]) and F.horizon_layers(p, 5, []) == {"hedge": []}
    cx, cy = p.center[0], p.center[1]
    assert len(L["hedge"]) > 30
    assert min(math.hypot(x - cx, y - cy) for x, y, *_ in L["hedge"]) > F.FENCE_DIST_M
    lo, hi = F.HEDGE_H
    assert all(0.8 * lo <= h <= 1.2 * hi for _, _, h, _, _ in L["hedge"])


@pytest.mark.parametrize("shot", ["court", "field_golden", "street_night", "rear"])
def test_the_shot_scripts_pin_the_loaded_tyre(shot):
    """The bigger contact patch stays opt-in (the pre-motion pin freezes tyre_contact's defaults): the realism
    round's scripts pin 0.55 / 0.4 so the checker keeps them."""
    s = json.loads((Path(__file__).parents[2] / "harness" / "realism" / f"{shot}.json").read_text(encoding="utf-8"))
    tc = next(r for r in s["realism"] if r["id"] == "tyre_contact")
    assert tc["params"] == {"patchLenFrac": 0.55, "bulgeFrac": 0.4}
    assert set(tc["pinned"]) == {"patchLenFrac", "bulgeFrac"}
    m = Catalog.load().get("realism", "tyre_contact")["params"]
    assert (m["patchLenFrac"]["default"], m["bulgeFrac"]["default"]) == (0.45, 0.25)     # the defaults stay
