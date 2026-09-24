import math
import pytest
from engine.ingest.measure import (Sample, build_profile, detail_points, gloss_share,
                                   reflection_targets, shoulder_line, wheels)

GLOSS = {"metallic": 1.0, "roughness": 0.1, "area": 1.0}
MATTE = {"metallic": 0.0, "roughness": 0.8, "area": 1.0}
LAMP = {"emission": 5.0, "area": 1.0}


def S(p, n, w=0.01, cls="glossy", gloss=True, textured=False, curv=0.0):
    return Sample(tuple(p), tuple(n), w, cls, gloss, textured, curv)


def box_car(L=4.5, W=1.9, H=1.3, step=0.1):
    """Glossy box body from z=0.35H to H, with 4 matte cylinder wheels r=0.33 touching z=0."""
    out = []
    xs = [(-L / 2) + step * (i + 0.5) for i in range(int(L / step))]
    ys = [(-W / 2) + step * (i + 0.5) for i in range(int(W / step))]
    zs = [0.35 * H + step * (i + 0.5) for i in range(int(0.65 * H / step))]
    out += [S((x, y, H), (0, 0, 1)) for x in xs for y in ys]                       # roof
    out += [S((x, sgn * W / 2, z), (0, sgn, 0)) for x in xs for z in zs for sgn in (1, -1)]  # flanks
    out += [S((sgn * L / 2, y, z), (sgn, 0, 0)) for y in ys for z in zs for sgn in (1, -1)]  # ends
    r = 0.33
    for wx in (-1.4, 1.4):
        for wy in (-0.8, 0.8):
            for k in range(72):
                a = 2 * math.pi * k / 72
                p = (wx + r * math.sin(a), wy, r - r * math.cos(a))
                out.append(S(p, (math.sin(a), 0, -math.cos(a)), cls="matte", gloss=False))
    return out


def test_gloss_share_uses_the_tiers_gloss_definition():
    assert gloss_share([GLOSS, MATTE]) == pytest.approx(0.5)
    assert gloss_share([{"metallic": 0.0, "roughness": 0.3, "area": 1.0}]) == 1.0  # roughness <= 0.3
    assert gloss_share([]) == 0.0


def test_reflection_targets_find_roof_and_flanks():
    t = {x["kind"]: x for x in reflection_targets(box_car())}
    assert {"top", "+y", "-y"} <= set(t)
    assert t["top"]["normal"] == pytest.approx([0, 0, 1], abs=1e-6)
    assert t["top"]["point"][2] == pytest.approx(1.3)
    assert t["+y"]["point"][1] == pytest.approx(0.95)
    # Every target point is a real surface sample, not an averaged point in mid-air.
    pts = {tuple(round(v, 5) for v in s.p) for s in box_car()}
    assert all(tuple(x["point"]) in pts for x in t.values())


def test_reflection_targets_ignore_matte_and_down_facing():
    samples = [S((0, 0, 0), (0, 0, -1))] * 50 + [S((0, 0, 1), (0, 0, 1), cls="matte", gloss=False)] * 50
    assert reflection_targets(samples) == []


def test_shoulder_line_follows_the_widest_point_per_flank():
    car = box_car()
    # Flare the flanks at z ~ 0.8 m: that row becomes the widest point, i.e. the shoulder.
    car = [s._replace(p=(s.p[0], s.p[1] * 1.03, s.p[2])) if abs(abs(s.p[1]) - 0.95) < 1e-9
           and abs(s.p[2] - 0.805) < 0.03 else s for s in car]
    lines = {l["side"]: l["points"] for l in shoulder_line(car, [-2.25, -0.98, 0], [2.25, 0.98, 1.3])}
    assert set(lines) == {"+y", "-y"}
    assert all(abs(p[2] - 0.805) < 0.03 for p in lines["+y"])


def test_detail_points_rank_emissive_first_and_stay_apart():
    car = box_car()
    lamp = [S((2.25, 0.6 + 0.01 * i, 0.7), (1, 0, 0), cls="emissive", gloss=False) for i in range(10)]
    badge = [S((2.25, -0.3 + 0.005 * i, 0.9), (1, 0, 0), curv=0.4) for i in range(10)]
    d = detail_points(car + lamp + badge, longest=4.5)
    assert d[0]["kind"] == "emissive" and d[0]["point"][1] == pytest.approx(0.645, abs=0.05)
    assert any(x["kind"] == "glossy_peak" for x in d)
    assert len(d) <= 8
    for i, a in enumerate(d):
        for b in d[i + 1:]:
            assert math.dist(a["point"], b["point"]) >= 0.15 * 4.5 - 1e-9


def test_detail_points_empty_for_featureless_subject():
    flat = [S((x * 0.1, 0, 0), (0, 0, 1), cls="matte", gloss=False) for x in range(50)]
    assert detail_points(flat, longest=5.0) == []


def test_detail_points_survive_zero_area_samples():
    # Degenerate (zero-area) polygons are real in uploads; a cluster made only of them must
    # not divide by zero (seen on pocket_watch, 2026-09-24).
    lamp = [S((0.01 * i, 0, 0.5), (1, 0, 0), w=0.0, cls="emissive", gloss=False) for i in range(5)]
    d = detail_points(lamp, longest=1.0)
    assert [x["kind"] for x in d] == ["emissive"]
