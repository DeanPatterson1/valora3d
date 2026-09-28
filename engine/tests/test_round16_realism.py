"""Round 16 realism passes, pure: the wheel close-up's low worn kerb (rain_courtyard fg_style), the rain capture's
glare that tracks a lamp's broad sources and not its LED bars (grade_plan CAPTURE wet) and the wheel
shot's own script change. The field's round-16 damp floor was reverted (the owner kept round 15's field)."""
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
