"""Collision-shell rules (phase 6 Task 97, pure): the voxel a proxy is built at, its wall thickness, its triangle
cap, and its cache key. engine/blender/collision_proxy.py builds the shell; every sim collides with the shell,
never with the uploaded mesh (METHODS R6/R8).

Purposes: "shell" (a closed voxel shell for cloth, gas and GN point collisions), "liquid" (finer, for Mantaflow
obstacles, so a pour does not leak through a thin wall), "bullet" (a coarse passive collider) and "bullet_hull"
(<= 16 convex hulls for an active subject). All numbers are (eng; METHODS R5/R6) until T97's coverage and
watertight measurements on 4 subjects calibrate them (plan register)."""
import hashlib
import json
from pathlib import Path

PURPOSES = ("shell", "liquid", "bullet", "bullet_hull")
_VOXEL = {  # purpose: (share of longest, floor m, ceiling m)
    "shell": (0.006, 0.001, 0.05),
    "liquid": (0.004, 0.0008, 0.03),
    "bullet": (0.01, 0.002, 0.08),
}
_TRIS = {"shell": 20000, "liquid": 60000, "bullet": 20000}
MAX_HULLS = 16
HULL_FILL = 1.3          # (eng) split a part until its hull volume <= 1.3 x its voxel volume
BUILDER = Path(__file__).resolve().parents[1] / "blender" / "collision_proxy.py"


def _base(purpose):
    if purpose not in PURPOSES:
        raise ValueError(f"unknown proxy purpose {purpose!r}; expected one of {PURPOSES}")
    return "bullet" if purpose == "bullet_hull" else purpose


def voxel_m(profile, purpose):
    """clamp(share x longest, floor, ceiling) metres."""
    share, lo, hi = _VOXEL[_base(purpose)]
    return min(max(share * profile.longest, lo), hi)


def thickness_m(profile):
    """The shell is thickened by one shell voxel, so single-sided glass becomes a wall."""
    return voxel_m(profile, "shell")


def max_tris(purpose):
    return _TRIS[_base(purpose)]


def max_hulls():
    return MAX_HULLS


def _builder_sha():
    try:
        return hashlib.sha256(BUILDER.read_bytes()).hexdigest()
    except OSError:
        return "missing"


def proxy_key(model_sha, purpose, voxel, blender=None):
    """The BakeStore key of a cached proxy: 'proxy-' + sha256 of (model sha256, purpose, voxel, Blender version,
    builder source). A store key is a directory name, so the plan's 'proxy:<modelSha>:<purpose>:<voxel>' is hashed
    (':' is not a legal Windows path character)."""
    if blender is None:
        from engine.blender_pin import PINNED_BLENDER
        blender = PINNED_BLENDER
    _base(purpose)                                     # validates the purpose
    raw = json.dumps([model_sha, purpose, round(float(voxel), 9), blender, _builder_sha()], separators=(",", ":"))
    return "proxy-" + hashlib.sha256(raw.encode()).hexdigest()[:48]
