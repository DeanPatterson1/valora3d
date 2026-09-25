from corpus.backlog import BLOCK_MAP, rank


def _rec(world, moves, motion=None, weather=None, effects=(), fam="vehicle"):
    return {"subject": {"category": fam}, "world": {"type": world, "weather": weather},
            "shots": [{"cameraMove": m, "subjectMotion": motion} for m in moves], "effects": list(effects)}


def test_rank_orders_by_frequency_times_fit_and_marks_existing():
    recs = [_rec("street", ["push", "tracking"], "drive", "rain")] * 6 + [_rec("nature", ["slide"], weather="snow")] * 2
    out = rank(recs, catalog_ids={"camera/low_hero_push", "effect/rain"})
    best = max(c["score"] for c in out["candidates"])
    tied = {c["key"] for c in out["candidates"] if c["score"] == best}
    assert tied == {"world:street", "camera:push", "camera:tracking"}      # motion/weather fit 0.9 < 1.0
    assert out["candidates"][0]["key"] in tied
    assert all(c["count"] >= 1 and 0 < c["fit"] <= 1 for c in out["candidates"])
    rain = next(c for c in out["candidates"] if c["key"] == "weather:rain")
    assert rain["block"] == "effect/rain" and rain["exists"] is True
    assert out["n"] == 8 and out["trusted"] is False            # < 30 records: ranking is advisory


def test_unknown_values_become_never_thought_of_candidates():
    out = rank([_rec("underwater", ["fpv"])] * 3, catalog_ids=set())
    keys = {c["key"]: c for c in out["candidates"]}
    assert keys["world:underwater"]["block"] is None and keys["world:underwater"]["novel"] is True


def test_block_map_targets_are_catalog_style_refs():
    assert all(v is None or v.count("/") == 1 for v in BLOCK_MAP.values())


def test_free_text_weather_and_uninformative_values_are_normalised():
    rec = {"world": {"type": "highway", "weather": "fog, snowfall", "atmosphere": ["aerial haze"]},
           "shots": [{"cameraMove": "unclear", "subjectMotion": "driving"}],
           "effects": ["steam from the cup (thin)"], "simulation": ["falling leaves"]}
    keys = {c["key"] for c in rank([rec], catalog_ids=set())["candidates"]}
    assert {"weather:fog", "weather:snow", "weather:haze", "motion:driving", "effect:steam", "effect:leaves"} <= keys
    assert not any(k.endswith(":unclear") or k.startswith("weather:fog,") for k in keys)


def test_no_records_ranks_nothing():
    assert rank([], catalog_ids=set()) == {"schema": "valora.backlog/1", "n": 0, "trusted": False, "candidates": []}
