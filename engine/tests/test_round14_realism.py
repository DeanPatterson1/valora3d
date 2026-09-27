"""Round 14 realism layers, pure: the night street round the photographer (a lamp behind the camera and a lit shop
window beside it, on the car's shadow side, out of the hook frame) and the road's hand-span mottle."""
import json
from pathlib import Path

from engine.geometry import Pose, project

ROOT = Path(__file__).parents[2]


def _load(s):
    return json.loads((ROOT / "harness" / "realism" / f"{s}.json").read_text(encoding="utf-8"))


def _night():
    from harness import realism_round as rr
    from engine.worlds.street_layout import hero_lamp, layout
    prof = rr.load_profile()
    hero = Pose((1.48, -6.97, 0.4), (0.0, 0.0, 0.55), 40)
    lay = layout(prof, 7, 30.0, hero=hero, aspect="9:16", cameras=[hero.position])
    return prof, lay, hero, hero_lamp(prof, lay, hero, "9:16")


def test_the_street_round_the_camera_lights_the_shadow_side_from_out_of_frame():
    from engine.worlds.street_layout import SHOP_SIZE, SHOP_Z, camera_practicals
    prof, lay, hero, hl = _night()
    cp = camera_practicals(prof, lay, hero, "9:16", hl)
    lamp, shop = cp["lamp"], cp["shop"]
    assert lamp is not None and shop is not None
    assert lamp[0] * hl[0] < 0 and shop["at"][0] * hl[0] < 0          # the pavement opposite the hero lamp
    assert lamp[1] < hero.position[1] < 0                               # behind the camera, down the street
    for p in (lamp, (lamp[0], lamp[1], 0.0)):
        x, y, d = project(hero, p, "9:16")
        assert d <= 0 or abs(x) > 1.1 or abs(y) > 1.1
    face = lay["road"]["faceU"]
    assert abs(abs(shop["at"][0]) - (face - 0.3)) < 1e-9 and shop["at"][2] == SHOP_Z
    assert shop["normal"][0] == -1.0 * (1 if shop["at"][0] > 0 else -1)    # faces into the street
    assert tuple(shop["size"]) == SHOP_SIZE


def test_no_hero_pose_no_camera_practicals():
    from engine.worlds.street_layout import camera_practicals
    prof, lay, _, _ = _night()
    assert camera_practicals(prof, lay, None, "9:16") == {"lamp": None, "shop": None}


def test_the_road_mess_carries_a_hand_span_mottle():
    from engine.blocks.world.night_street.build import MESS
    lo, hi = MESS["mottleAlbedo"]
    assert lo < 1.0 < hi and MESS["mottleRough"][0] < 1.0 < MESS["mottleRough"][1]
    assert 1.5 <= MESS["mottleScale"] <= 4.0                             # tens of cm: seen in the foreground


def test_round14_night_script_is_lifted_but_still_the_street_alone():
    sn = _load("street_night")
    assert sn["lighting"] == {"id": "practicals_only", "params": {"exposure": 1.0, "straySpill": 0.8}}
    assert sn["world"]["params"]["neonAmount"] == 0.0


# ---- field (owner's r13 review: "exposed soil reads as a layout artifact - tiling, even spacing")
def test_the_clump_field_does_not_repeat_on_a_lattice():
    from engine.worlds import field_plants as P
    pts = [(i * 0.05, j * 0.05) for i in range(60) for j in range(60)]
    a = [P.clump(x, y, 7) for x, y in pts]
    for lam in P.CLUMP_WAVES_M:                                  # shifted by a wavelength it is a different field
        b = [P.clump(x + lam, y, 7) for x, y in pts]
        assert sum(abs(p - q) for p, q in zip(a, b)) / len(a) > 0.08


def test_a_plant_in_a_gap_becomes_low_cover_rooted_at_the_ground():
    from engine.worlds import field_plants as P
    kinds = set()
    for k in range(300):
        pick = (k + 0.5) / 300
        kinds.add(P.COVER[P.cover_kind(pick)][0])
        v, polys, u, cols = P.cover(1.0, 2.0, 30.0, 0.4, pick)
        assert min(z for *_, z in v) == 0.0 and max(z for *_, z in v) <= max(c[2] for c in P.COVER) + 1e-9
        assert len(u) == len(v) and len(cols) == len(polys)
        assert all(u[i] == 0.0 for i, p in enumerate(v) if p[2] == 0.0 and i == 0)
    assert kinds == {c[0] for c in P.COVER}


def test_left_out_plants_are_the_meadow_floor():
    from harness import realism_round as rr
    from engine.worlds import field_layout as F
    lay = F.layout(rr.load_profile(), 7, 0.45, cameras=[(4.4, -7.7, 0.84)])
    assert lay["floor"] and all(b[3] >= 0.004 for b in lay["floor"])


# ---- courtyard (owner's r13 review: far buildings barely read; the trunk at the frame's edge read as accidental)
def test_the_far_structures_rise_over_the_cars_roofline_and_no_bare_trunk_stands_at_the_edge():
    from engine.geometry import box_corners, project
    from engine.tests.test_round13_realism import _court_hook
    from engine.worlds import courtyard_layout as C
    p, hero, seed = _court_hook()
    lay = C.layout(p, seed, "full", 24.0, hero=hero, aspect="9:16")
    L = C.depth_layers(p, hero, "9:16", seed, lay["exclusion"], lay["props"], max_dist=150.0)
    assert L["trunks"] == []
    roof = max(project(hero, c, "9:16")[1] for c in box_corners(p.boundsMin, p.boundsMax))
    tops = [project(hero, (x, y, h), "9:16")[1] for x, y, (w, d, h), *_ in L["farBlocks"]]
    assert sum(1 for t in tops if t > roof) >= 2                     # at least two roofs clear the car
    from engine.blocks.world.rain_courtyard import build as B
    assert B.LAYER_HAZE["far"][1] <= 0.65                            # a darker silhouette than r13's 0.72 cap
