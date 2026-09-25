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


def test_wheels_found_on_synthetic_car():
    w = wheels(box_car(), [-2.25, -0.98, 0], [2.25, 0.98, 1.3])
    assert len(w) == 4
    for x in w:
        assert x["radius"] == pytest.approx(0.33, abs=0.02)
        assert x["center"][2] == pytest.approx(0.33, abs=0.02)
        assert x["axis"] == [0.0, 1.0, 0.0] and x["confidence"] == "high"


def test_no_wheels_on_a_bottle():
    bottle = [S((0.03 * math.cos(a / 10), 0.03 * math.sin(a / 10), z * 0.01), (math.cos(a / 10), math.sin(a / 10), 0))
              for a in range(63) for z in range(30)]
    assert wheels(bottle, [-0.03, -0.03, 0], [0.03, 0.03, 0.3]) == []


def ring(cl, cw, r, n=72, la=0, cls="matte"):
    """Samples of a wheel-like cylinder rim of radius r touching z=0 at (cl, cw), rolling along axis la."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        p, nrm = [0.0, 0.0, r - r * math.cos(a)], [0.0, 0.0, -math.cos(a)]
        p[la], p[1 - la] = cl + r * math.sin(a), cw
        nrm[la] = math.sin(a)
        out.append(S(p, nrm, cls=cls, gloss=False))
    return out


def body_only(L=4.5, W=1.9, H=1.3):
    return [s for s in box_car(L, W, H) if s.gloss]


CAR_BOUNDS = ([-2.25, -0.98, 0], [2.25, 0.98, 1.3])


def test_no_wheels_on_a_five_star_chair_base():
    # Five casters on a star: every patch votes a clean radius, but there is no axle pattern.
    base = []
    for k in range(5):
        a = 2 * math.pi * k / 5
        base += ring(0.3 * math.cos(a), 0.3 * math.sin(a), 0.03)
    seat = [S((x * 0.05, y * 0.05, 0.5), (0, 0, 1)) for x in range(-6, 7) for y in range(-6, 7)]
    assert wheels(base + seat, [-0.35, -0.35, 0], [0.35, 0.35, 1.0]) == []


def test_no_wheels_when_radii_disagree():
    car = body_only() + ring(-1.4, -0.8, 0.33) + ring(-1.4, 0.8, 0.33) + ring(1.4, -0.8, 0.15) + ring(1.4, 0.8, 0.15)
    assert wheels(car, *CAR_BOUNDS) == []


def test_no_wheels_without_a_mirrored_partner():
    # Four equal wheels, but all on one side of the centreline: no axle.
    car = body_only() + [s for x in (-1.4, 1.4) for y in (0.2, 0.8) for s in ring(x, y, 0.33)]
    assert wheels(car, *CAR_BOUNDS) == []


def test_no_wheels_when_wheelbase_is_too_short():
    car = body_only() + [s for x in (-0.5, 0.5) for y in (-0.8, 0.8) for s in ring(x, y, 0.33)]
    assert wheels(car, *CAR_BOUNDS) == []


def test_three_wheels_allow_one_on_the_centreline():
    car = body_only() + ring(-1.4, -0.8, 0.33) + ring(-1.4, 0.8, 0.33) + ring(1.4, 0.0, 0.33)
    w = wheels(car, *CAR_BOUNDS)
    assert len(w) == 3 and all(x["confidence"] == "high" for x in w)


def test_shoulder_line_is_both_flanks_or_neither():
    car = box_car()
    # Remove the -y flank: a single flank is not a shoulder line.
    one = [s for s in car if not (s.n[1] < -0.5)]
    assert shoulder_line(one, [-2.25, -0.98, 0], [2.25, 0.98, 1.3]) == []


def test_shoulder_line_needs_nine_of_twelve_bins_per_side():
    car = body_only()  # wheels would fill the cut bins
    # Bins are 0.3375 m wide from x = -2.025; cutting the -y flank at x = 0.675 leaves 8 of 12.
    part = [s for s in car if not (s.n[1] < -0.5 and s.p[0] > 0.675)]
    lines = shoulder_line(part, [-2.25, -0.98, 0], [2.25, 0.98, 1.3])
    assert lines == []


def test_shoulder_line_needs_flanks_at_the_body_width():
    # Both flanks present but only a narrow core reaches 0.3-0.9 H: widths << W.
    core = [S((x * 0.1, sgn * 0.2, z * 0.1 + 0.5), (0, sgn, 0)) for x in range(-20, 21) for z in range(7)
            for sgn in (1, -1)]
    assert shoulder_line(core, [-2.25, -0.98, 0], [2.25, 0.98, 1.3]) == []


def test_surface_points_are_a_bounded_voxel_thinning_of_the_samples():
    from engine.ingest.measure import SURFACE_CELLS, surface_points
    # A dense 1 m x 1 m plate at z = 0.5: every output point is an input point, spacing ~ 1/SURFACE_CELLS.
    pts = [S((x / 200, y / 200, 0.5), (0, 0, 1)) for x in range(201) for y in range(201)]
    out = surface_points(pts, longest=1.0, max_n=5000)
    assert set(map(tuple, out)) <= {tuple(round(v, 6) for v in s.p) for s in pts}
    assert (SURFACE_CELLS + 1) ** 2 >= len(out) >= SURFACE_CELLS ** 2
    near = max(min(math.dist(p.p, q) for q in out) for p in pts[::97])
    assert near <= 1.5 / SURFACE_CELLS  # every sample has a kept point within ~one cell
    capped = surface_points(pts, longest=1.0, max_n=200)
    assert 0 < len(capped) <= 200


def test_build_profile_records_surface_samples():
    raw = {"boundsMin": [-1, -1, 0], "boundsMax": [1, 1, 1], "polyCount": 10, "materials": [{}],
           "samples": [[x / 10, 0.0, 0.5, 0, -1, 0, 0.01, 0, 0.0] for x in range(-10, 11)]}
    p = build_profile(raw)
    assert p.surfaceSamples and all(len(q) == 3 for q in p.surfaceSamples)


def test_detail_points_skip_samples_no_camera_can_see():
    # The lamp's samples are hidden (open=0: every ray out of their cone hits the subject or the
    # floor), e.g. a surface inside a wheel arch or a cavity. A detail shot aimed there looks at
    # the part in front of it, so it must never be a detail point (t3_attempt, 2026-09-24).
    car = box_car()
    lamp = [S((2.25, 0.6 + 0.01 * i, 0.7), (1, 0, 0), cls="emissive", gloss=False)._replace(open=0.0)
            for i in range(10)]
    badge = [S((2.25, -0.3 + 0.005 * i, 0.9), (1, 0, 0), curv=0.4) for i in range(10)]
    d = detail_points(car + lamp + badge, longest=4.5)
    assert d and all(x["kind"] != "emissive" for x in d)


def test_detail_point_normal_is_the_aimed_samples_own_normal():
    # A thin glossy fin sampled on both faces: the cluster's mean normal is meaningless (the two
    # faces cancel), and a camera placed along it looks at the fin's edge or through it.
    fin = [S((0.5, 0.01 * i, 0.5), (1, 0, 0), curv=0.4) for i in range(6)]
    fin += [S((0.499, 0.01 * i + 0.005, 0.5), (-0.6, 0.8, 0), curv=0.4) for i in range(6)]
    d = detail_points(fin, longest=1.0)
    by_point = {tuple(round(v, 5) for v in s.p): s.n for s in fin}
    assert d
    for x in d:
        assert x["normal"] == pytest.approx(list(by_point[tuple(x["point"])]), abs=1e-5)


def test_build_profile_reads_the_optional_openness_column():
    lamp = {"emission": 5.0, "area": 1.0}
    rows = [[0.01 * i, 0.0, 0.5, 1, 0, 0, 0.01, 0, 0.0] for i in range(10)]
    assert build_profile({"boundsMin": [-1, -1, 0], "boundsMax": [1, 1, 1], "materials": [lamp],
                          "samples": rows}).detailPoints
    hidden = [r + [0.0] for r in rows]
    assert build_profile({"boundsMin": [-1, -1, 0], "boundsMax": [1, 1, 1], "materials": [lamp],
                          "samples": hidden}).detailPoints == []
