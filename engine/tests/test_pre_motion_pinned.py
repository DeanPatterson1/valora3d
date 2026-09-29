"""Review chunk1 #11: static scripts check and time exactly as the code BEFORE phase-5 motion did (2eed2f2).

engine/tests/fixtures/pre_motion_2eed2f2.json was produced by engine/tests/pinned/make_pre_motion.py run
against `git archive 2eed2f2`, never by the current tree. The current tree must reproduce, for all 90 frozen
phase-3 cases and for every example script + the valid fixture on three subjects: the checked script, the
checker's verdict and issues, and a digest of every camera key the compiler keyframes (frame, shot, position,
aim, lens, f-stop, focus, detail target). The only allowed difference is a param that phase 5 added to an
existing block, present at an "off" value (it changes nothing downstream)."""
import json
from pathlib import Path

import pytest

from engine.tests.pinned.make_pre_motion import collect

pytestmark = pytest.mark.usefixtures("legacy_fps30")

PINNED = json.loads((Path(__file__).parent / "fixtures" / "pre_motion_2eed2f2.json").read_text(encoding="utf-8"))
OFF = (0, 0.0, False, None, "", "none", "off")


def _same(new, old, path="", in_params=False):
    """Differences between new and old; a params key new adds is allowed only at an off value."""
    if isinstance(new, dict) and isinstance(old, dict):
        out = []
        for k in new.keys() | old.keys():
            p = f"{path}.{k}"
            if k not in old:
                if not (in_params and new[k] in OFF):
                    out.append(f"{p}: added {new[k]!r}")
            elif k not in new:
                out.append(f"{p}: removed")
            else:
                out += _same(new[k], old[k], p, k == "params")
        return out
    if isinstance(new, list) and isinstance(old, list):
        if len(new) != len(old):
            return [f"{path}: {len(old)} -> {len(new)} items"]
        return [d for i, (a, b) in enumerate(zip(new, old)) for d in _same(a, b, f"{path}[{i}]")]
    return [] if new == old and type(new) is type(old) else [f"{path}: {old!r} -> {new!r}"]


def _has_path(script, path):
    """Whether a dotted issue path (grade.params.halation, shots[0].camera...) exists in the script."""
    import re
    cur = script
    for part in path.split("."):
        m = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", part)
        if not m or not isinstance(cur, dict) or m.group(1) not in cur:
            return False
        cur = cur[m.group(1)]
        if m.group(2) is not None:
            if not isinstance(cur, list) or int(m.group(2)) >= len(cur):
                return False
            cur = cur[int(m.group(2))]
    return True


def _issues(got, want_script):
    """Issues minus a param_default for a param the old script never had (an added param filled at off)."""
    return [i for i in got if not (i["code"] == "param_default" and ".params." in i["path"]
                                   and not _has_path(want_script, i["path"])
                                   and i["message"] in (f"filled default {v}" for v in OFF))]


@pytest.fixture(scope="module")
def now(legacy_fps30):
    return collect()


def test_pinned_file_came_from_the_pre_motion_commit():
    assert PINNED["rev"] == "2eed2f2" and len(PINNED["baseline"]) == 90 and len(PINNED["checks"]) == 12


def test_the_90_frozen_scripts_and_their_camera_keys_are_unchanged(now):
    for got, want in zip(now["baseline"], PINNED["baseline"], strict=True):
        case = (want["model"], want["prompt"], want["seed"])
        assert (got["model"], got["prompt"], got["seed"]) == case
        assert not _same(got["script"], want["script"]), (case, _same(got["script"], want["script"])[:5])
        assert (got["keys"], got["nKeys"]) == (want["keys"], want["nKeys"]), case
        assert got["recheckOk"] == want["recheckOk"], case
        assert _issues(got["recheckIssues"], want["script"]) == want["recheckIssues"], case


def test_checker_verdicts_issues_and_keys_are_unchanged(now):
    for got, want in zip(now["checks"], PINNED["checks"], strict=True):
        case = (want["name"], want["profile"])
        assert (got["name"], got["profile"], got["ok"]) == (want["name"], want["profile"], want["ok"]), case
        assert _issues(got["issues"], want["script"]) == want["issues"], case
        assert not _same(got["script"], want["script"]), (case, _same(got["script"], want["script"])[:5])
        assert (got.get("keys"), got.get("nKeys")) == (want.get("keys"), want.get("nKeys")), case


def test_the_comparison_sees_a_moved_value():
    want = PINNED["baseline"][0]["script"]
    import copy
    bad = copy.deepcopy(want)
    bad["shots"][0]["camera"]["params"]["distance"] += 0.001
    assert _same(bad, want)
    grown = copy.deepcopy(want)
    grown["grade"]["params"]["zzHalation"] = 0.0          # an added param at its off value is allowed
    assert not _same(grown, want)
    grown["grade"]["params"]["zzHalation"] = 0.4          # ... turned on, it is not
    assert _same(grown, want)


def _close(new, old, path=""):
    """_same for compiled values: floats within 1e-9 relative (the same Blender, the same inputs)."""
    if isinstance(new, float) or isinstance(old, float):
        ok = isinstance(new, (int, float)) and isinstance(old, (int, float)) and new == pytest.approx(old, rel=1e-9, abs=1e-12)
        return [] if ok else [f"{path}: {old!r} -> {new!r}"]
    if isinstance(new, dict) and isinstance(old, dict):
        if new.keys() != old.keys():
            return [f"{path}: keys {sorted(old.keys() ^ new.keys())}"]
        return [d for k in new for d in _close(new[k], old[k], f"{path}.{k}")]
    if isinstance(new, list) and isinstance(old, list):
        if len(new) != len(old):
            return [f"{path}: {len(old)} -> {len(new)} items"]
        return [d for i, (a, b) in enumerate(zip(new, old)) for d in _close(a, b, f"{path}[{i}]")]
    return [] if new == old else [f"{path}: {old!r} -> {new!r}"]


@pytest.mark.blender
def test_a_static_compile_matches_the_pre_motion_commit(tmp_path):
    """The Blender side: one static compile (toycar, script_realism, probe frames 1/45/90) gives the same
    placement, blocks, motion events, realism facts, clearance, per-frame projection, objects and camera
    positions as 2eed2f2. A probe frame's motionMatrix (added by Task 56) is the only new key, and it must
    be the identity for a static subject; the wind-field empty (Task 59) the only new object."""
    import os
    from engine.ingest.run import BLENDER
    from engine.tests.pinned.make_pre_motion import COMPILE_KEYS, collect_compile
    glb = Path(__file__).resolve().parents[2] / "assets-in" / "models" / "toycar" / "toycar.glb"
    if not os.path.exists(BLENDER) or not glb.exists():
        pytest.skip("Blender or the toycar model is not present (local-only)")
    want = json.loads((Path(__file__).parent / "fixtures" / "pre_motion_2eed2f2_compile.json").read_text(encoding="utf-8"))
    got = collect_compile(glb, tmp_path)
    for rec in got["probe"].values():
        m = rec.pop("motionMatrix", None)
        assert m is None or m == [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    # Task 59 adds the one WIND force-field empty to every clip (hand-off H4): never rendered, the only new object
    field = [o for o in got["objects"] if o["name"] == "valora_wind_field"]
    assert len(field) == 1 and field[0]["type"] == "EMPTY" and field[0]["block"] == "field/wind"
    got["objects"] = [o for o in got["objects"] if o is not field[0]]
    old_keys = set(want["objects"][0])          # Task 60/63 added report-only keys (block, ground, ...): not compared
    got["objects"] = [{k: v for k, v in o.items() if k in old_keys} for o in got["objects"]]
    diffs = [d for k in COMPILE_KEYS for d in _close(got[k], want[k], k)]
    assert not diffs, diffs[:10]
