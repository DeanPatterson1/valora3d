"""The studio fallback cases frozen BEFORE phase-5 Task 88 (engine/tests/fixtures/director/fallback_phase4/):
5 seeds x 3 subjects, interim directions with the opener alternated, layer 1 on. Task 88 must leave every
studio fallback byte-identical (test_director_fallback_phase5.py)."""
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures" / "director" / "fallback_phase4"
MODELS = ("pocket_watch", "sports_car", "cesium_man")
SEEDS = (0, 1, 2, 3, 4)


def case(model, seed):
    from engine.catalog import Catalog
    from engine.director.direction import direction_of, interim_direction, parse_id
    from engine.director.fallback import build_fallback
    from engine.director.job import make_job
    from engine.tests.test_director_package import _p
    cat, p = Catalog.load(), _p(model)
    axes = parse_id(interim_direction(seed, p, cat).id)
    axes["opener"] = "arc_orbit" if seed % 2 else "low_hero_push"
    d = direction_of(axes, "dice")
    job = make_job("", p, cat, seed=seed, direction=d, duration=10)
    return build_fallback(job, p, cat)


def path(model, seed):
    return FIX / f"{model}_{seed}.json"


if __name__ == "__main__":
    for m in MODELS:
        for s in SEEDS:
            path(m, s).write_text(json.dumps(case(m, s), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", len(MODELS) * len(SEEDS))
