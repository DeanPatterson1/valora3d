"""Plan 'Done when': every reference model, as ingested, passes check() on the default script.

Profiles were produced by `py -m engine ingest assets-in/models/<m>/<m>.glb --out ...`
(2026-09-24). A model that the default script cannot frame gets its own script in
fixtures/scripts/<model>.json with the reason recorded here; none needs one today
(camera_01 and toycar pass after the checker's own low_hero_push distance repair)."""
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.issues import errors
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
PROFILES = sorted((FIX / "profiles").glob("*.json"))
MODELS = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope"]
VEHICLES = {"sports_car"}  # real-scale vehicle eval subject (local-only GLB, Task 30)


def test_all_reference_models_have_profiles():
    assert [p.stem for p in PROFILES] == MODELS


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_default_script_frames_every_reference_model(path):
    profile = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    per_model = FIX / "scripts" / path.name
    script = json.loads((per_model if per_model.exists() else FIX / "script_valid.json").read_text(encoding="utf-8"))
    r = check(script, profile, Catalog.load())
    assert r.ok, errors(r.issues)
    assert profile.boundsMin[2] == 0.0 and profile.scaleFactor > 0


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_reference_profiles_carry_ingest_extensions(path):
    p = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert 0.0 <= p.glossShare <= 1.0
    assert p.parts, "every model has at least one mesh part"
    for d in p.detailPoints:
        assert all(lo - 1e-6 <= v <= hi + 1e-6 for v, lo, hi in zip(d["point"], p.boundsMin, p.boundsMax))
    assert len(p.detailPoints) <= 8
    if p.wheels:  # best effort: if found, they must be plausible
        assert 3 <= len(p.wheels) <= 8
        assert all(w["radius"] < 0.6 * p.sizeM[2] for w in p.wheels)


def test_glossy_reference_models_have_reflection_targets():
    for name in ("pocket_watch", "camera_01"):
        p = SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))
        if p.glossShare >= 0.1:
            assert p.reflectionTargets, name


@pytest.mark.parametrize("path", [p for p in PROFILES if p.stem not in VEHICLES], ids=lambda p: p.stem)
def test_no_reference_model_reports_wheels(path):
    # None of the six is a wheeled vehicle standing on its wheels (toycar sits on a cloth).
    # Before the axle-pattern gate, flighthelmet reported 7 "wheels" and the lounge chair's
    # base 5 (review of 4d8bca5..76767a2).
    p = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert p.wheels == []


def test_real_scale_subjects_ingest_at_true_size():
    size = {m: max(SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{m}.json").read_text(
        encoding="utf-8"))).sizeM) for m in ("sports_car", "sneaker", "cesium_man")}
    assert 3.5 <= size["sports_car"] <= 5.5 and 0.25 <= size["sneaker"] <= 0.35 and 0.2 <= size["cesium_man"] <= 2.0


def test_the_vehicle_reports_four_wheels():
    p = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "sports_car.json").read_text(encoding="utf-8")))
    assert len(p.wheels) == 4


def test_one_sided_flank_is_not_a_shoulder_line():
    # camera_01 used to report a lone +x flank (6 bins). Both flanks or neither.
    # Note: the lounge chair and pocket watch DO pass the both-flanks / 9-of-12 / width gates
    # (two full sides at ~W apart), so they keep a shoulder line; only camera_01 is pinned here.
    p = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "camera_01.json").read_text(encoding="utf-8")))
    assert p.shoulderLine == []


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_reference_profiles_carry_surface_samples_that_anchor_their_own_details(path):
    import math
    from engine.ingest.measure import SURFACE_MAX
    from engine.markers import SNAP_FRAC
    p = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert 0 < len(p.surfaceSamples) <= SURFACE_MAX
    tol = SNAP_FRAC * p.longest
    for d in p.detailPoints:  # detail points lie on the surface, so a marker there must be accepted
        assert min(math.dist(d["point"], q) for q in p.surfaceSamples) <= tol


def _prof(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def test_sports_car_carries_the_realism_facts():
    p = _prof("sports_car")
    assert len(p.wheels) == 4 and all(w["confidence"] == "high" for w in p.wheels)
    for w in p.wheels:
        assert 0.15 <= w["width"] <= 0.40, w           # a GT3 RS tyre is 0.275-0.335 m wide
        assert 0.5 <= w["tyreBand"][0] <= 0.8, w      # 20-21 in rims on ~0.35 m tyres
        assert w["contact"][2] == 0.0 and w["separable"] is True
    assert p.vehicle["vehicleClass"] == "sport" and p.vehicle["bodySeparable"] is True
    assert 2.3 <= p.vehicle["wheelbaseM"] <= 2.7      # 992 GT3 RS: 2.457 m


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_every_profile_has_ground_contacts(path):
    p = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert p.groundContacts and all(g["center"][2] == 0.0 for g in p.groundContacts)


def test_only_small_unrigged_fabric_subjects_are_soft():
    # Measured 2026-09-25 (profiles regenerated after the phase-3.5 ingest facts): only the sneaker.
    high = {path.stem for path in PROFILES
            if any(s["confidence"] == "high" for s in _prof(path.stem).softParts)}
    assert high == {"sneaker"}, high


def test_no_reference_model_has_a_high_confidence_dangling_part():
    # None of the nine has a strap or cord. Measured 2026-09-25: flighthelmet and vintage_microscope
    # each carry one LOW candidate (a rigid horizontal piece; a glossy metal pillar), never high:
    # a false high would make a rigid part sway.
    high = {path.stem for path in PROFILES
            if any(d["confidence"] == "high" for d in _prof(path.stem).danglingParts)}
    assert high == set(), high
