import pytest

from engine.catalog import Catalog
from engine.craft_rules import score_script
from engine.director.fallback import FallbackError, build_fallback
from engine.director.job import make_job
from engine.tests.test_director_package import _p

MODELS = ["camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope"]


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("prompt", ["", "square 12 s", "cinematic 16:9, 8 seconds", "4 second loop", "30 s film"])
def test_fallback_checks_on_every_subject_format_and_duration(model, prompt):
    cat = Catalog.load()
    for seed in (1, 2, 3):
        job = make_job(prompt, _p(model), cat, seed=seed)
        s = build_fallback(job, _p(model), cat)          # raises FallbackError if the checker fails it
        assert s["format"] == job.fmt and s["seed"] == seed and "used the safe fallback" in s["assumptions"][-1]


@pytest.mark.parametrize("model", MODELS)
def test_default_fallback_meets_the_t2_t3_script_items(model):
    cat = Catalog.load()
    for seed in (1, 2, 3, 4):
        for prompt in ("", "square 12 s", "30 s film", "4 second loop", "3 s", "5.5 seconds"):
            s = build_fallback(make_job(prompt, _p(model), cat, seed=seed), _p(model), cat)
            assert len(s["shots"]) >= (3 if s["format"]["durationS"] >= 6 else 2), "too few shots"
            assert "edit" in s or s["format"]["durationS"] < 6, "a long fallback lost its sequence edit"
            fails = [x.id for x in score_script(s, _p(model), cat)
                     if x.status == "fail" and x.id[:2] in ("T1", "T2", "T3", "V-")]
            assert fails == [], (seed, prompt, fails)


def test_fallback_targets_markers_and_carries_unsupported():
    cat, watch = Catalog.load(), _p("pocket_watch")
    markers = [{"id": f"m{i}", "text": "look here", "anchor": {"space": "placed", "point": watch.detailPoints[i]["point"]}}
               for i in range(2)]
    job = make_job("add rain", watch, cat, seed=3, markers=markers)
    s = build_fallback(job, watch, cat)
    targets = [sh.get("target") for sh in s["shots"] if sh["purpose"] == "detail"]
    assert targets[:2] == [{"marker": "m0"}, {"marker": "m1"}]
    assert [u["capability"] for u in s["unsupported"]] == ["weather.rain"]


@pytest.mark.parametrize("model", MODELS)
def test_fallback_gives_every_marker_its_own_detail_shot(model):
    """Each marker gets a detail shot targeting it, whatever pace the seeded direction picks, while the
    plan stays inside T3-01 (3-7 shots per 10 s) and the other script items stay clean."""
    cat, prof = Catalog.load(), _p(model)
    n = min(2, len(prof.detailPoints))
    if n < 2:
        pytest.skip("needs two detail points to anchor two markers")
    bare = [{"id": f"m{i}", "text": "look here", "anchor": {"space": "placed", "point": prof.detailPoints[i]["point"]}}
            for i in range(n)]
    normal = [{**m, "anchor": {**m["anchor"], "normal": prof.detailPoints[i]["normal"]}} for i, m in enumerate(bare)]
    for seed in range(1, 9):
        markers = normal if seed % 2 else bare   # with and without a surface normal (the harness sends one)
        for prompt in ("", "30 s film"):
            s = build_fallback(make_job(prompt, prof, cat, seed=seed, markers=markers), prof, cat)
            targeted = [(sh.get("target") or {}).get("marker") for sh in s["shots"]]
            assert all(f"m{i}" in targeted for i in range(n)), (seed, prompt, targeted)
            assert not any("markers got their own detail shot" in a for a in s["assumptions"])
            fails = [x.id for x in score_script(s, prof, cat)
                     if x.status == "fail" and x.id[:2] in ("T1", "T2", "T3", "V-")]
            assert fails == [], (seed, prompt, fails)


def test_short_fallback_notes_markers_it_cannot_fit():
    cat, watch = Catalog.load(), _p("pocket_watch")
    markers = [{"id": f"m{i}", "text": "look here", "anchor": {"space": "placed", "point": watch.detailPoints[i]["point"]}}
               for i in range(3)]
    s = build_fallback(make_job("4 second loop", watch, cat, seed=1, markers=markers), watch, cat)
    per10 = len(s["shots"]) / (s["format"]["durationS"] / 10)
    assert 3 <= per10 <= 7
    assert any("markers got their own detail shot" in a for a in s["assumptions"])


def test_fallback_error_is_raised_not_swallowed(monkeypatch):
    import engine.director.fallback as fb
    cat = Catalog.load()
    job = make_job("", _p("sneaker"), cat, seed=1)
    monkeypatch.setattr(fb, "_script", lambda *a, **k: {"schema": "nope"})
    with pytest.raises(FallbackError):
        fb.build_fallback(job, _p("sneaker"), cat)


def test_fallback_plays_the_clip_a_movement_ask_wants():
    cat = Catalog.load()
    man = _p("cesium_man")
    s = build_fallback(make_job("character walks", man, cat, seed=2), man, cat)
    assert s["subject"]["motion"]["id"] == "play_clip" and s["subject"]["motion"]["params"]["clip"] == 0
    assert not any(u["capability"] == "motion.character_clip" for u in s.get("unsupported", []))
    watch = _p("pocket_watch")
    s = build_fallback(make_job("character walks", watch, cat, seed=2), watch, cat)
    assert s["subject"]["motion"]["id"] == "static"
    assert "motion.character_clip" in [u["capability"] for u in s["unsupported"]]
