"""Phase 6 Tasks 111 / 113 (lane S), pure parts: the VDB library presets stay inside the plan's gas budget, the
smoke_sim domain sizing, playback retiming and the gas stability rule (engine/physics/gas.py)."""
import pytest

from engine.physics import gas as G
from engine.tests.test_director_package import _p


@pytest.mark.parametrize("name", sorted(G.PRESETS))
def test_every_preset_fits_the_gas_budget(name):
    p = G.PRESETS[name]
    assert p["res"] <= G.RES_CAP and p["frames"] <= G.FRAMES_CAP
    nx, ny, nz = G.cells(p["size"], p["res"])
    assert max(nx, ny, nz) == p["res"] and nx * ny * nz <= 1.2e6        # RAM: ~1M cells at most (preview tier)
    for s in p["sources"]:
        c, r = s["centre"], s["radius"]
        half = (p["size"][0] / 2, p["size"][1] / 2)
        assert abs(c[0]) + r < half[0] and abs(c[1]) + r < half[1] and 0 < c[2] < p["size"][2]
        assert s["kind"] in ("SMOKE", "FIRE", "BOTH")


def test_the_library_names_the_plans_presets():
    assert {"plume_soft", "chimney_thin", "campfire", "tyre_smoke_burst", "dust_billow"} <= set(G.PRESETS)


def test_base_is_the_domain_floor_centre_in_vdb_space():
    assert G.base_m((2.0, 4.0, 3.0)) == (1.0, 2.0, 0.0)
    assert G.voxel_m((6.0, 4.0, 2.5), 160) == pytest.approx(0.0375)


def test_retime_plays_the_library_at_real_speed():
    assert G.retime(30, 30) == 1.0 and G.retime(30, 24) == pytest.approx(1.25)
    assert G.retime(30, 30, 0.5) == 0.5


def test_smoke_domain_holds_the_subject_within_three_longest():
    p = _p("sports_car")
    lo, hi = G.smoke_domain(p, "ground")
    L = p.longest
    for i in (0, 1):
        assert hi[i] - lo[i] <= G.SMOKE_SIM_SPAN * L + 1e-9
        assert lo[i] < p.boundsMin[i] and hi[i] > p.boundsMax[i]
    assert lo[2] == 0.0 and hi[2] > p.boundsMax[2] and hi[2] <= G.SMOKE_SIM_SPAN * L


def test_a_moving_subjects_domain_follows_the_path_within_the_cap():
    p = _p("sports_car")
    L = p.longest
    path = [(x, 0.0, 0.0) for x in (-3.0, 0.0, 3.0)]
    lo, hi = G.smoke_domain(p, "tyres", path=path)
    assert hi[0] - lo[0] == pytest.approx(G.SMOKE_SIM_SPAN * L)


def test_growth_smooth_flags_a_blow_up_and_a_nan():
    assert G.growth_smooth([0, 1, 2, 3, 4, 5])
    assert G.growth_smooth([0, 1, 2, 3, 3.1, 3.2])
    assert not G.growth_smooth([0, 1, 2, 3, 40, 41])
    assert not G.growth_smooth([0, 1, float("nan")])
