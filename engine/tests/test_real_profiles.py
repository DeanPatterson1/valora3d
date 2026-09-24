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
MODELS = ["camera_01", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "toycar",
          "vintage_microscope"]


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
