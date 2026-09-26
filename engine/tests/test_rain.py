"""Task 64: rain maths (pure)."""
import math

import pytest

from engine.physics import rain as R


def test_fall_speed_matches_render_studio():
    assert R.fall_speed(2.0) == pytest.approx(6.5, abs=0.05)            # render-studio's 6.5 m/s
    assert R.fall_speed(0.8) < R.fall_speed(2.0) < R.fall_speed(3.0) < 9.65
    assert R.fall_speed(0.01) == 0.5                                      # floor


def test_streak_length_is_speed_times_the_shutter():
    assert R.streak_len(6.5) == pytest.approx(0.108, abs=5e-4)           # METHODS' 11 cm example


def test_drop_position_is_periodic_in_the_box_height():
    d, v, h = R.slant_vector((0.0, 0.0), 6.5), 6.5, 3.0
    a = R.drop_position((0.0, 0.0, 3.0), 0.2, 0.7, d, v, h)
    b = R.drop_position((0.0, 0.0, 3.0), 0.2, 0.7 + h / v, d, v, h)
    assert a == pytest.approx(b, abs=1e-9)


def test_counts_grow_with_intensity_and_cap():
    box = 10.0 * 10.0 * 4.0 / 100.0                                       # 4 m3
    counts = [R.drop_count(R.INTENSITY[k]["rateMmH"], box) for k in ("drizzle", "steady", "downpour")]
    assert counts[0] < counts[1] < counts[2]
    assert R.drop_count(50.0, 1e6) == R.MAX_DROPS


def test_slant_follows_the_wind():
    assert R.slant_vector((0.0, 0.0), 6.5) == pytest.approx((0.0, 0.0, -1.0))
    d = R.slant_vector((6.5, 0.0), 6.5)
    assert math.degrees(math.atan2(d[0], -d[2])) == pytest.approx(45.0)
    assert R.slant_deg(6.5, 6.5) == pytest.approx(45.0)


def test_shelter_is_the_footprint():
    lo, hi = (-1.0, -2.0, 0.0), (1.0, 2.0, 1.2)
    assert R.sheltered((0.5, 1.9), lo, hi) and not R.sheltered((1.2, 0.0), lo, hi, margin=0.1)
    assert R.sheltered((1.05, 0.0), lo, hi, margin=0.1)


def test_intensity_presets_and_explicit_values():
    assert R.resolve({"intensity": "drizzle", "rateMmH": 0.0, "dropSizeMm": 0.0}) == (1.0, 0.8)
    assert R.resolve({"intensity": "downpour", "rateMmH": 12.0, "dropSizeMm": 0.0}) == (12.0, 3.0)


def test_box_covers_the_view_and_the_subject():
    side, h = R.box_size(4.5, 1.3, 8.0, 35.0)
    assert side >= 1.5 * 8.0 and side >= 1.5 * (2 * 8.0 * 18 / 35) - 1e-9 and h >= 1.5 * 1.3
    assert R.box_size(0.07, 0.05, 0.4, 100.0) == (R.BOX_MIN_M, R.BOX_H_MIN_M)       # a watch: the 1 m floor
    assert R.box_size(30.0, 5.0, 60.0, 24.0) == (R.BOX_CAP_M, R.BOX_H_CAP_M)


def test_impacts_scale_with_rate_and_area():
    a = R.impact_slots(4.0, 2.0, 1.0)
    assert 30 <= a <= 50                                                  # ~265 drops/m2/s x 0.15 s
    assert R.impact_slots(25.0, 3.0, 1.0) > a and R.impact_slots(4.0, 2.0, 1e6) == R.IMPACT_CAP


# review chunk3 #1: hostile values that pass [min, max] but break the maths
@pytest.mark.parametrize("size", [1e-200, 1e-9, 0.2, float("inf"), float("nan"), -1.0, "x", None])
def test_hostile_drop_size_never_reaches_the_maths(size):
    rate, mm = R.resolve({"intensity": "steady", "rateMmH": 0.0, "dropSizeMm": size})
    assert R.SIZE_RANGE_MM[0] <= mm <= R.SIZE_RANGE_MM[1] and rate == 4.0
    assert R.impact_slots(rate, mm, 100.0) >= 0                           # no ZeroDivisionError
    assert R.impact_slots(4.0, 1e-200, 1.0) == 0                          # the maths guards itself too


def test_hostile_rate_is_held_to_the_physical_range():
    assert R.resolve({"intensity": "drizzle", "rateMmH": 1e-200, "dropSizeMm": 0.0})[0] == R.RATE_RANGE_MM_H[0]
    assert R.resolve({"intensity": "drizzle", "rateMmH": 1e9, "dropSizeMm": 0.0})[0] == R.RATE_RANGE_MM_H[1]


@pytest.mark.parametrize("key,bad,want", [("dropSizeMm", 1e-200, 0.5), ("dropSizeMm", 0.3, 0.5),
                                          ("rateMmH", 1e-200, 0.1), ("dropSizeMm", 0.0, 0.0), ("dropSizeMm", 2.0, 2.0)])
def test_the_checker_lifts_a_tiny_explicit_value_to_zero_or_min(key, bad, want):
    import copy
    import json
    from pathlib import Path
    from engine.catalog import Catalog
    from engine.checker import check
    from engine.tests.test_director_package import _p
    s = copy.deepcopy(json.loads((Path(__file__).parent / "fixtures" / "script_t3.json").read_text(encoding="utf-8")))
    s["world"] = {"id": "rain_courtyard", "params": {}}
    s["lighting"] = {"id": "hdri_only", "params": {}}
    s["effects"] = [{"id": "rain", "params": {"intensity": "steady", key: bad}}]
    r = check(s, _p("sports_car"), Catalog.load())
    got = next(e for e in r.script["effects"] if e["id"] == "rain")["params"][key]
    assert got == want
    assert any(i.code == "param_clamped" for i in r.issues) is (bad != want)


def test_catalog_validates_zero_or_min(tmp_path):
    import json as _json
    from engine.catalog import Catalog, CatalogError
    for spec, ok in (({"min": 0.0, "max": 4.0, "default": 0.0, "zeroOrMin": 0.5}, True),
                     ({"min": 0.1, "max": 4.0, "default": 0.1, "zeroOrMin": 0.5}, False),
                     ({"min": 0.0, "max": 4.0, "default": 0.2, "zeroOrMin": 0.5}, False),
                     ({"min": 0.0, "max": 4.0, "default": 0.0, "zeroOrMin": 5.0}, False)):
        root = tmp_path / str(len(list(tmp_path.iterdir())))
        d = root / "world" / "a"
        d.mkdir(parents=True)
        (d / "block.json").write_text(_json.dumps({
            "id": "a", "kind": "world", "description": "x", "params": {"x": {"type": "number", **spec}},
            "subjectSizeM": [0.1, 1.0], "aspects": ["9:16"], "costWeight": 1.0,
            "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T2"}))
        if ok:
            Catalog.load(root)
        else:
            with pytest.raises(CatalogError, match="zeroOrMin"):
                Catalog.load(root)


def test_velocity_keeps_the_full_wind_and_the_full_fall():                  # review chunk3 #3
    v = R.velocity((6.5, 0.0, 0.0), 6.5)
    assert v == (6.5, 0.0, -6.5)
    d = R.slant_vector((6.5, 0.0, 0.0), 6.5)                                 # the orientation agrees with it
    n = math.hypot(*v)
    assert d == pytest.approx(tuple(c / n for c in v))


def test_the_impact_lattice_keeps_the_density_and_the_alive_count():                  # review chunk3 #6
    lat = R.impact_lattice(4.0, 2.0, 10.0, seed=7)
    cells = (10.0 / lat["cellM"]) ** 2
    assert cells * lat["lifeS"] / lat["periodS"] == pytest.approx(R.impact_slots(4.0, 2.0, 100.0), rel=1e-9)
    per = (4.0 / 3.6e6) / (4.0 / 3.0 * math.pi * 0.001 ** 3)                         # drops per m2 per s
    assert 1.0 / (lat["cellM"] ** 2 * lat["periodS"]) == pytest.approx(per, rel=0.01)  # the true landing rate
    assert lat["across"] * lat["cellM"] >= 10.0 and lat["periodS"] > lat["lifeS"]
    assert R.impact_lattice(4.0, 2.0, 10.0, seed=7) == lat and R.impact_lattice(4.0, 2.0, 10.0, seed=8)["offset"] != lat["offset"]
    assert R.impact_lattice(4.0, 1e-200, 10.0, seed=7) is None
    assert R.impact_age(0.0, 0.3, 0.25) == pytest.approx(0.25) and R.impact_age(0.3, 0.3, 0.25) == pytest.approx(0.25)


def test_streaks_are_cut_to_half_and_further_in_close_ups():
    """Critique mat-v2 #3: the streak contribution ~50%; 25-50% in a close-up."""
    from engine.physics import rain as R
    assert R.streak_share(False) == 0.5
    assert 0.25 <= R.streak_share(True) <= 0.5 and R.streak_share(True) < R.streak_share(False)
