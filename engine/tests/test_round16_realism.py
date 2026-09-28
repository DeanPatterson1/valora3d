"""Round 16 realism passes, pure: the wheel close-up's low worn kerb (rain_courtyard fg_style), the rain capture's
glare that tracks a lamp's broad sources and not its LED bars (grade_plan CAPTURE wet), the field's damp floor
(golden_field FLOOR / field_layout DAMP_FLOOR / litter_sites), and the scripts' own shot changes."""
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]


def _prof():
    from harness import realism_round as rr
    return rr.load_profile()


def _key(shot, frame, pos, tgt, lens):
    return NS(shot=shot, frame=frame, pose=NS(position=pos, target=tgt, lens_mm=lens), target=tgt)


def test_a_camera_looking_down_on_its_kerb_gets_a_low_worn_one_nearer_the_lens():
    from engine.blocks.world.rain_courtyard import build as C
    low, high = C.fg_style(0.16), C.fg_style(0.61)
    assert low == dict(C.FG, worn=False)                                  # the rear quarter's kerb is round 9's
    assert high["worn"] and high["at"] < C.FG["at"]
    assert max(high["tall"]) <= 0.6 * min(C.FG["tall"])                   # much lower
    assert high["topJitterM"] > 0 and high["yawDeg"] > 0 and high["wobbleM"] > 0   # not perfectly straight
    prof = _prof()
    tgt = (prof.boundsMax[0], prof.center[1], 0.35)
    shots = {1: (61, 105)}
    for z in (0.16, 0.61):
        cam = (tgt[0] + 4.5, tgt[1] - 1.5, z)
        (_, c, _), = C.fg_kerbs([_key(1, 83.0, cam, tgt, 85.0)], prof, shots)
        d = math.hypot(tgt[0] - cam[0], tgt[1] - cam[1])
        assert abs(math.hypot(c[0] - cam[0], c[1] - cam[1]) - C.fg_style(z)["at"] * d) < 1e-6


def test_the_wheel_close_up_opens_its_aperture_for_a_soft_foreground():
    s = json.loads((ROOT / "harness" / "realism" / "court.json").read_text(encoding="utf-8"))
    wheel, lamp = s["shots"][1]["camera"]["params"], s["shots"][2]["camera"]["params"]
    assert wheel["fstop"] <= 2.8 and wheel["lensMm"] == 85                 # framing kept, focus softer
    assert lamp["fstop"] == 5.6                                            # the headlight shot keeps its own


def test_the_rain_glare_tracks_a_lamps_broad_sources_not_its_bars():
    from engine.grade_plan import CAPTURE
    wet, night = CAPTURE["wet"], CAPTURE["night"]
    for k in ("glow", "halo"):
        assert wet[k]["openPx"] >= 4 and 0.1 <= wet[k]["thin"] <= 0.3 and wet[k]["hotLum"] > 4.0
    assert wet["veil"]["threshold"] == 0.0 and 2.0 < wet["veil"]["maximum"] <= 6.0   # the sky keeps its veil
    for spec in night.values():                                            # night is frozen: no round-16 keys
        assert not {"openPx", "thin", "hotLum", "maximum"} & set(spec)


def test_the_golden_meadow_is_a_damp_floor_and_other_crops_are_not():
    from engine.blocks.world.golden_field import build as B
    fl = B._floor("golden", "grass")
    assert fl is not None and B._floor("golden", "wheat") is None and B._floor("dusk", "grass") is None
    assert fl["dry"] < 0.5 * B.DRY_SHARE["golden"] and fl["green"] > B.GREEN_SHARE["golden"]
    tip, old = fl["tip"], B.BLADE_TIP["grass"]
    assert tip[1] > tip[0] and old[0] > old[1]                             # green-olive, not straw
    assert 0.4 <= fl["keep"] <= 0.7 and fl["matted"]["fine"] < 0.6
    assert all(v <= B.COVER_LOOK[k][0] for k, v in fl["coverDry"].items())
    assert B._tip("grass", "golden", fl) == tip and B._tip("grass", "overcast", None) is None


def test_the_damp_floor_grows_wider_moss_and_fine_grass_and_rare_sorrel():
    from engine.worlds import field_layout as FL
    prof = _prof()
    cam = (prof.center[0] - 2.4, prof.center[1] - 1.4, 0.8)
    a = FL.field_cover(prof, 7, 11.4, [], 1.0, cameras=[cam])
    b = FL.field_cover(prof, 7, 11.4, [], 1.0, cameras=[cam], floor=FL.DAMP_FLOOR)
    assert len(b["moss"]) > 1.3 * len(a["moss"]) and len(b["fine"]) > 1.1 * len(a["fine"])
    assert len(b["clover"]) < 0.2 * len(a["clover"])                       # pink sorrel flowers: rare
    assert b["broadleaf"] == a["broadleaf"] and set(b) == set(a)           # no species added or re-weighted
    lay = FL.layout(prof, 7, 0.25, "grass", cameras=[cam], cover=FL.DAMP_FLOOR)
    assert len(lay["flora"]["clover"]) < 0.2 * len(FL.layout(prof, 7, 0.25, "grass", cameras=[cam])["flora"]["clover"])


def test_wet_leaves_and_thatch_lie_under_the_green_round_the_low_cameras():
    from engine.blocks.world.golden_field import build as B
    prof = _prof()
    (cx, cy), hx, hy = (prof.center[0], prof.center[1]), 0.5 * (prof.boundsMax[0] - prof.boundsMin[0]), \
        0.5 * (prof.boundsMax[1] - prof.boundsMin[1])
    lay = {"centre": [cx, cy], "footprint": [hx, hy]}
    cams = [(cx - 4.0, cy - 6.0, 0.8), (cx - 4.1, cy - 6.1, 0.8), (cx + 3.0, cy + 5.0, 3.5)]
    sites = B.litter_sites(lay, cams, 7)
    assert sites == B.litter_sites(lay, cams, 7)
    leaves = [s for s in sites if s[4] > 0.01]
    stems = [s for s in sites if s[4] <= 0.01]
    assert leaves and stems and len(sites) <= B.LITTER["cap"]
    for x, y, yaw, ln, w, pick in sites:
        assert not (abs(x - cx) <= hx and abs(y - cy) <= hy)              # never under the body
        assert math.hypot(x - (cx - 4.0), y - (cy - 6.0)) < B.LITTER["reachM"] + 1.0   # the high camera gets none
    assert B.LITTER_RGB[0][0] > B.LITTER_RGB[0][1] > B.LITTER_RGB[0][2]     # brown, not green


def test_the_field_script_lowers_its_grass():
    s = json.loads((ROOT / "harness" / "realism" / "field_golden.json").read_text(encoding="utf-8"))
    assert 0.18 <= s["world"]["params"]["grassHeightM"] <= 0.27            # 0.45 -> ~0.25 (-40..60%)
