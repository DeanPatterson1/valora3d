"""perShot drive vs the wheel_roll and suspension realism blocks (follow-up to review chunk5 #11). With
perShot every shot replays the drive, so the subject track jumps back at each cut. The realism blocks read
that track per frame; a block that differentiates straight across the cut sees a teleport: the wheels spin a
blur of turns in one frame, a spurious stop pitches the body and the lateral g of the jump rolls it. Each shot
is its own take: never differentiate across a cut, restart the state at each shot."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from engine.physics import events, suspension as S, wheel_spin as WS
from engine.tests.conftest import requires_blender

ROOT = Path(__file__).resolve().parents[2]


# ---- pure: the physics helpers take the per-frame shot list ------------------------------------------------

def _jump_track(n=40, cut=20, v=0.4):
    """A straight track at v m/frame that jumps back 6 m at index `cut` (a perShot replay), then waits."""
    pos = [(v * i, 0.0, 0.0) for i in range(cut)] + [(-6.0, 0.0, 0.0)] * 5 + \
          [(-6.0 + v * i, 0.0, 0.0) for i in range(1, n - cut - 4)]
    shots = [0] * cut + [1] * (len(pos) - cut)
    return pos, shots


def test_frame_shots_is_none_without_per_shot():
    from engine.motion_path import frame_shots
    s = {"format": {"fps": 30}, "shots": [{"startS": 0.0, "endS": 1.0}, {"startS": 1.0, "endS": 2.0}],
         "subject": {"motion": {"id": "drive", "params": {"perShot": False}}}}
    assert frame_shots(s, [1, 30, 31, 60]) is None
    s["subject"]["motion"]["params"]["perShot"] = True
    assert frame_shots(s, [0, 1, 30, 31, 60]) == [0, 0, 0, 1, 1]      # frame f shows time (f - 1) / fps


def test_wheel_angles_never_integrate_the_cut_jump():
    pos, shots = _jump_track()
    yaw = [0.0] * len(pos)
    ang = WS.wheel_angles(pos, yaw, (0.0, 1.0, 0.0), 0.3, shots)
    steps = [b - a for a, b in zip(ang, ang[1:])]
    inshot = [s for i, s in enumerate(steps, start=1) if shots[i] == shots[i - 1]]
    assert min(inshot) - 1e-12 <= steps[19] <= max(inshot) + 1e-12      # the cut step (index 19 -> 20)
    assert WS.wheel_angles(pos, yaw, (0.0, 1.0, 0.0), 0.3) == WS.wheel_angles(pos, yaw, (0.0, 1.0, 0.0), 0.3, None)
    assert WS.slip([a for a in ang], pos, 0.3, shots) < 1e-9             # rolled == travelled, per take


def test_no_spurious_stop_or_lateral_g_at_a_cut():
    pos, shots = _jump_track()
    assert events.stops(pos, 30, 1.0)                                   # the jump reads as a stop without shots
    assert events.stops(pos, 30, 1.0, shots) == []
    yaw = [0.0] * 20 + [0.3] * (len(pos) - 20)                          # the replay also turns back
    assert max(abs(g) for g in S.lateral_g(pos, yaw, 30, (1.0, 0.0, 0.0), shots)) < 1e-12
    roll = S.body_roll([1.0] * 20 + [0.0] * (len(pos) - 20), 5.0, 30, shots=shots)
    assert roll[20] == 0.0                                              # the lag state restarts with the take


# ---- Blender: the compiled wheel and body drivers at each cut ------------------------------------------------

_READ = r'''
import sys, json
sys.path.insert(0, r"{root}")
import bpy
bpy.ops.wm.open_mainfile(filepath=r"{blend}")
from engine.blender.realism_rig import fcurves
scene = bpy.context.scene
n = scene.frame_end
out = {{}}
for name, idx, key in (("valora_rz_wheel_0", 0, "wheel"), ("valora_rz_body", 0, "pitch"), ("valora_rz_body", 1, "roll")):
    ob = bpy.data.objects.get(name)
    c = next((c for c in fcurves(ob.animation_data.action) if c.data_path == "location" and c.array_index == idx),
             None) if ob and ob.animation_data else None
    out[key] = [float(c.evaluate(f)) if c else float(ob.location[idx]) if ob else 0.0 for f in range(1, n + 1)]
print("DRV " + json.dumps(out))
'''


@pytest.mark.blender
@requires_blender
def test_per_shot_drive_wheels_and_body_stay_in_their_in_shot_range_at_each_cut(tmp_path):
    from engine.catalog import Catalog
    from engine.checker import check
    from engine.compiler.run import compile_scene
    from engine.ingest.run import BLENDER
    from engine.tests.test_blocks_phase5_blender import _glb
    from engine.tests.test_director_package import _p
    from engine.tests.test_growth_floor import FLOORS
    make, model = FLOORS["camera/rolling_track"]
    s = make()
    s.pop("edit", None)
    # the courtyard: an arc_left side-tracked on night_street's 7.3 m road puts the tracking camera behind the
    # pavement slab (camera_view_blocked); this test is about the wheels at the cuts, not the street
    s["world"], s["lighting"] = {"id": "rain_courtyard", "params": {}}, {"id": "hdri_only", "params": {}}
    prm = s["subject"]["motion"]["params"]
    # still moving (and turning) when each 2.5 s shot cuts, waiting 0.5 s at the start of the next
    prm.update(perShot=True, path="arc_left", startS=0.5, driveS=4.0, speedKmh=20.0)
    track = copy.deepcopy(s["shots"][0])
    s["shots"] = [dict(copy.deepcopy(track), startS=a, endS=a + 2.5) for a in (0.0, 2.5, 5.0, 7.5)]
    p = _p(model)
    r = check(s, p, Catalog.load())
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]
    sc = r.script
    assert sc["subject"]["motion"]["params"]["perShot"] is True
    res = compile_scene(sc, p, _glb(model), tmp_path / "c", render=False, skip_kinds=("grade",), save_blend=True)
    assert {"wheel_roll", "suspension"} <= set(res["realism"]), res["realism"]
    py = tmp_path / "read.py"
    py.write_text(_READ.format(root=ROOT, blend=tmp_path / "c" / "scene.blend"), encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(py)],
                          capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    got = json.loads(next(ln[4:] for ln in proc.stdout.splitlines() if ln.startswith("DRV ")))
    fps = sc["format"]["fps"]
    cuts = [int(round(sh["startS"] * fps)) + 1 for sh in sc["shots"][1:]]     # frame f opens a shot
    near = {c + d for c in cuts for d in (-1, 0)}                            # frames either side of a cut
    wheel = got["wheel"]
    rate = {f: wheel[f - 1] - wheel[f - 2] for f in range(2, len(wheel) + 1)}     # radians over frames f-1 -> f
    lo_r = min(v for f, v in rate.items() if f not in cuts)
    hi_r = max(v for f, v in rate.items() if f not in cuts)
    assert hi_r - lo_r > 0.05                                                 # the wheels really roll in-shot
    for c in cuts:
        assert lo_r - 1e-6 <= rate[c] <= hi_r + 1e-6, (c, rate[c], lo_r, hi_r)
    for key in ("pitch", "roll"):
        v = got[key]
        inshot = [v[f - 1] for f in range(1, len(v) + 1) if f not in near]
        for f in sorted(near):
            assert min(inshot) - 1e-6 <= v[f - 1] <= max(inshot) + 1e-6, (key, f, v[f - 1], min(inshot), max(inshot))
