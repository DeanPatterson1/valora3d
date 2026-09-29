"""Outdoor fallback, small product: macro_detail's distance is radius x distance, which put a 0.3 m sneaker's lens
0.07 m from its laces (a 2.6 cm frame, camera inside the shoe's bounds; site sheets 2026-09-29). The fallback now asks
for a frame at least SMALL_MACRO_FRAME_K of the subject's length; studio and cars keep their numbers."""
import pytest

from engine import site_job
from engine.catalog import Catalog
from engine.director.fallback import SMALL_MACRO_FRAME_K
from engine.director.llm import FakeProvider
from engine.targets import resolve_target
from engine.tests.test_director_package import _p

SENSOR = 36.0


@pytest.fixture(autouse=True)
def _variety_secret(monkeypatch):
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)


def _script(name, world, seed):
    res, _ = site_job.direct_site("", _p(name), world=world, aspect="16:9", seed=seed,
                                  provider=FakeProvider([{"stop_reason": "refusal"}]))
    return res.script


def _widths(name, world, seed):
    from engine.director.site import site_catalog
    cat, p = site_catalog(), _p(name)
    s = _script(name, world, seed)
    out = []
    for sh in s["shots"]:
        if sh["camera"]["id"] != "macro_detail":
            continue
        prm = sh["camera"]["params"]
        tgt = resolve_target(sh, p, s.get("markers", []))
        for u in (0.0, 1.0):
            pose = cat.load_camera_path("macro_detail")(prm, p, u, tgt)
            d = sum((a - b) ** 2 for a, b in zip(pose.position, tgt.point)) ** 0.5
            out.append(d * SENSOR / prm["lensMm"] / p.longest)
    return out, s


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_sneaker_macro_in_the_field_frames_a_real_share_of_the_shoe(seed):
    widths, _ = _widths("sneaker", "golden_field", seed)
    assert widths and min(widths) >= SMALL_MACRO_FRAME_K - 0.01


def test_a_car_macro_is_untouched():
    widths, s = _widths("sports_car", "golden_field", 1)
    p = _p("sports_car")
    assert widths and max(widths) < 0.15          # ~9 % of the car's length, as before
