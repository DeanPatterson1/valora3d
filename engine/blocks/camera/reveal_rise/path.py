"""reveal_rise (phase 5 Task 80): crane rise reveal, detail -> whole (products.md P-C08, CATALOG-GAPS rank 12).

Low and tight: the camera starts at startDistance x radius, startHeightFrac x height, aimed at that detail
height. It holds for holdFrac of the shot (P-C08: hold ~0.7 s), then rises to endHeightFrac x height while
pulling back to distance x radius and lifting its aim to the subject centre, eased out (ease-out-quad), and
settles for settleFrac. `distance` is the END distance: the checker's distance repair acts on the frame that
must hold the whole subject. framed_from(params) tells the checker where full framing starts (the rise's
landing); before it the tight start overflows the frame by design."""
import math

from engine.easing import ease, settle
from engine.geometry import Pose

MIN_HEIGHT_M = 0.03   # the low_hero_push floor clearance


def progress(params, u):
    m = min(max((u - params["holdFrac"]) / (1.0 - params["holdFrac"]), 0.0), 1.0)
    return ease(params["easing"], settle(m, params["settleFrac"]))


def framed_from(params):
    """Shot progress from which the whole subject is framed: the end of the rise."""
    return 1.0 - params["settleFrac"]


def sample(params, profile, u, target=None):
    cx, cy, cz = profile.center
    h = profile.sizeM[2]
    k = progress(params, u)
    d = profile.radius * (params["startDistance"] + (params["distance"] - params["startDistance"]) * k)
    z = max(MIN_HEIGHT_M, h * (params["startHeightFrac"] + (params["endHeightFrac"] - params["startHeightFrac"]) * k))
    az = math.radians(params["azimuthDeg"])
    z0 = h * params["startHeightFrac"]
    return Pose(position=(cx + d * math.cos(az), cy + d * math.sin(az), z),
                target=(cx, cy, z0 + (cz - z0) * k), lens_mm=params["lensMm"])
