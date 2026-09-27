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
