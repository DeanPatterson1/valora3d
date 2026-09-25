"""The subject does not move: every sample is the identity pose (engine/motion_path.py)."""
from engine.motion_path import IDENTITY


def sample(params, profile, t, duration):
    return IDENTITY


def still(params):
    """The explicit identity contract (engine/motion_path.is_moving): static never moves."""
    return True


def flags(params):
    return {}
