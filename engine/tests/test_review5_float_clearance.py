"""Review chunk5 #5: float_drift keeps the tilted subject's lowest point above the floor."""
import dataclasses
import math

import pytest

from engine.motion_path import posed_bounds
from engine.tests.motion_helpers import defaults, module
from engine.tests.test_director_package import _p

FLOAT = module("float_drift")


def _flat(p):
    """A supported 1 x 1 x 0.02 m tile standing on the ground (the size range allows 0.02-2 m)."""
    return dataclasses.replace(p, sizeM=[1.0, 1.0, 0.02], boundsMin=[-0.5, -0.5, 0.0], boundsMax=[0.5, 0.5, 0.02])


@pytest.mark.parametrize("prm_over", [{}, {"liftFrac": 0.05, "bobFrac": 0.03}, {"bobHz": 0.5, "yawDegS": -20.0}])
def test_a_flat_tile_never_dips_below_its_clearance(prm_over):
    p = _flat(_p("pocket_watch"))
    prm = {**defaults("float_drift"), **prm_over}
    clearance = (prm["liftFrac"] - prm["bobFrac"]) * p.sizeM[2]      # the designed gap under the lowest point
    lows = [posed_bounds(p, FLOAT.sample(prm, p, k / 60, 20.0))[0][2] for k in range(0, 1201)]
    assert min(lows) >= clearance - 1e-9, (min(lows), clearance)


def test_a_tall_subject_floats_as_before():
    p = _p("pocket_watch")
    tall = dataclasses.replace(p, sizeM=[0.07, 0.07, 0.3], boundsMin=[-0.035, -0.035, 0.0], boundsMax=[0.035, 0.035, 0.3])
    prm = defaults("float_drift")
    for k in range(0, 601):
        pose = FLOAT.sample(prm, tall, k / 60, 10.0)
        assert posed_bounds(tall, pose)[0][2] >= (prm["liftFrac"] - prm["bobFrac"]) * 0.3 - 1e-9
        t = k / 60
        old = prm["liftFrac"] * 0.3 + prm["bobFrac"] * 0.3 * math.sin(2 * math.pi * prm["bobHz"] * t)
        assert 0.0 <= pose.offset[2] - old < 0.002          # raised by under 2 mm: the look is unchanged
