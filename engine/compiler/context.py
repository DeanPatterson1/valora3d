"""What a block's build(ctx) receives. Pure: Blender objects are passed in, never imported here."""
import hashlib
import random
from dataclasses import dataclass, field

from engine.targets import resolve_target


@dataclass
class BuildContext:
    scene: object            # bpy.types.Scene
    profile: object          # SubjectProfile
    script: dict             # the checked script
    params: dict             # this block's params
    seed: int                # this block's own seed (block_seed)
    rng: random.Random
    subject: object          # the placed subject root (bpy object)
    meshes: list             # subject mesh objects
    hero_pose: object        # engine.geometry.Pose the rig and world face
    camera_positions: list = field(default_factory=list)  # every camera key position (haze domain)
    catalog: object = None


def block_seed(seed, kind, bid):
    """Per-block seed so blocks never share random streams (spec §4.2 seed drives everything)."""
    return int(hashlib.sha256(f"{seed}:{kind}:{bid}".encode()).hexdigest()[:8], 16)


def hero_pose(s, profile, catalog):
    """Mid-point of the last 'hero'/'packshot' shot, else of the last shot."""
    shots = s["shots"]
    shot = next((sh for sh in reversed(shots) if sh.get("purpose") in ("hero", "packshot")), shots[-1])
    ref = shot["camera"]
    tgt = (resolve_target(shot, profile, s.get("markers", []))
           if catalog.get("camera", ref["id"])["framing"] == "detail" else None)
    return catalog.load_camera_path(ref["id"])(ref["params"], profile, 0.5, tgt)
