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
