"""Task 107: the cloth base's pure half (engine/physics/cloth.py) and the refitted wind force-field law."""
import math
from pathlib import Path

import pytest

from engine.physics import cloth as C
from engine.physics import wind_calibration as W

ENGINE = Path(__file__).resolve().parents[1]


def test_presets_are_the_plan_values_at_the_reference_spacing():
    assert C.PRESETS["silk"]["mass"] == 0.15 and C.PRESETS["silk"]["tension"] == 5 and C.PRESETS["silk"]["bending"] == 0.05
    assert C.PRESETS["silk"]["air"] == 1.5
    assert C.PRESETS["satin"]["mass"] == 0.25 and C.PRESETS["satin"]["tension"] == 10 and C.PRESETS["satin"]["bending"] == 0.2
    assert C.PRESETS["canvas"]["mass"] == 0.6 and C.PRESETS["canvas"]["tension"] == 40 and C.PRESETS["canvas"]["bending"] == 5
    s = C.settings("silk", C.REF_SPACING)
    assert s["scale"] == 1.0 and s["mass"] == 0.15 and s["tension"] == 5.0


def test_settings_scale_mass_and_forces_together_so_accelerations_hold():
    a, b = C.settings("canvas", C.REF_SPACING), C.settings("canvas", C.REF_SPACING / 4)
    assert math.isclose(b["scale"], 1 / 16)
    for k in ("tension", "compression", "shear", "bending", "air", "damping"):
        assert math.isclose(b[k] / b["mass"], a[k] / a["mass"])          # spring / damping / air per unit mass
    # the wind pushes strength x (spacing^2): its acceleration per unit strength is the same at any spacing
    assert math.isclose((C.REF_SPACING / 4) ** 2 / b["mass"], C.REF_SPACING ** 2 / a["mass"])


@pytest.mark.parametrize("w,h,sp", [(0.5, 1.0, 0.02), (7.0, 6.0, 0.0457), (0.2, 0.2, 0.00076), (1, 1, 1)])
def test_grid_dims_stay_under_the_vertex_budget(w, h, sp):
    nx, ny, s = C.grid_dims(w, h, sp)
    assert 4 <= nx * ny <= C.MAX_VERTS and nx >= 2 and ny >= 2
    assert s >= sp * 0.999 and (nx - 1) * s >= w * 0.999 - 1e-9 or (ny - 1) * s >= h * 0.999


def test_the_calibration_strip_is_51_by_26():
    assert C.grid_dims(0.5, 1.0, C.REF_SPACING)[:2] == (26, 51)


def test_sizes_follow_the_subject():
    assert math.isclose(C.spacing_m(4.57), 0.0457)
    assert math.isclose(C.distance_min(4.57), 0.01828)                      # 0.4% of a car
    assert C.distance_min(0.076) == 0.0005                                   # the floor on a watch
    assert C.quality(1000) == 8 and C.quality(8000, self_collision=True) == 12


def test_drag_model_and_fabric_wind_weights():
    assert math.isclose(C.drag_tan(2.0, 0.06), 0.5 * 1.225 * 1.2 * 4 / (0.06 * 9.81))
    assert 78 < C.drag_angle_deg(2.0, 0.06) < 79
    assert C.wind_weight("silk") == 1.0
    assert C.wind_weight("canvas") < C.wind_weight("satin") < 1.0            # heavier cloth lifts less


def test_force_field_strength_is_the_fitted_quadratic_law():
    assert W.FF_STRENGTH_PER_MS2 == 7600.0                                   # T107 fit 7638 (var/probe)
    assert W.force_field_strength(0) == 0.0 and W.force_field_strength(-3) == 0.0
    assert math.isclose(W.force_field_strength(2.0), 4 * W.FF_STRENGTH_PER_MS2)
    assert math.isclose(W.force_field_strength(10.0) / W.force_field_strength(5.0), 4.0)


def test_no_committed_block_reads_the_force_field_strength_so_no_look_moves():
    """Task 107 frozen check: the refit changes no phase-5 look, because no block builder reads the strength
    (the field itself is built by engine/blender/wind_field.py; only cloth feels it)."""
    for f in (ENGINE / "blocks").rglob("*.py"):
        t = f.read_text(encoding="utf-8")
        assert "force_field_strength" not in t and "FF_STRENGTH" not in t, f
