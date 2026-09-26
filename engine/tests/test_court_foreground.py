"""Round 9: the courtyard's out-of-focus foreground kerb for a low long-lens shot (pure planning)."""
from types import SimpleNamespace as NS

from engine.blocks.world.rain_courtyard import build as C
from engine.tests.test_director_package import _p


def _key(shot, frame, pos, tgt, lens):
    return NS(shot=shot, frame=frame, pose=NS(position=pos, target=tgt, lens_mm=lens), target=tgt)


def test_a_low_long_lens_shot_looks_across_a_kerb_between_lens_and_car():
    car = _p("sports_car")
    tgt = (car.boundsMax[0], car.center[1], 0.6)
    cam = (tgt[0] + 4.5, tgt[1] - 1.5, 0.12)
    shots = {0: (1, 60), 1: (61, 105)}
    keys = [_key(0, 30.5, (6.0, 0.0, 1.2), car.center, 40.0), _key(1, 83.0, cam, tgt, 85.0)]
    out = C.fg_kerbs(keys, car, shots)
    assert [o[0] for o in out] == [1]                                  # the hero (40 mm, 1.2 m up) gets none
    _, c, along = out[0]
    d = ((tgt[0] - cam[0]) ** 2 + (tgt[1] - cam[1]) ** 2) ** 0.5
    assert abs(((c[0] - cam[0]) ** 2 + (c[1] - cam[1]) ** 2) ** 0.5 - C.FG["at"] * d) < 1e-6
    assert abs(along[0] * (tgt[0] - cam[0]) + along[1] * (tgt[1] - cam[1])) < 1e-6   # square to the view
    near = _key(1, 83.0, (tgt[0] + 0.9, tgt[1], 0.12), tgt, 85.0)                    # the kerb would touch the car
    assert C.fg_kerbs([near], car, shots) == []


def test_a_few_leaves_lie_on_the_subjects_level_top_faces():
    car = _p("sports_car")
    sites = C.car_leaf_sites(car, 7)
    mid = 0.5 * (car.boundsMin[2] + car.boundsMax[2])
    assert 0 < len(sites) <= C.CAR_LEAVES and sites == C.car_leaf_sites(car, 7)
    for (x, y), z, yaw, hw, ln in sites:
        assert z > mid and car.boundsMin[0] <= x <= car.boundsMax[0] and car.boundsMin[1] <= y <= car.boundsMax[1]
        assert 0.03 <= ln <= 0.07 and hw < ln
