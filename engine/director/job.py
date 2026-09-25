"""One director job: everything the system decides before the LLM is called."""
import copy
import secrets
from dataclasses import dataclass, field

from engine.director.capabilities import detect, unsupported
from engine.director.direction import Direction, interim_direction
from engine.director.family import family
from engine.director.intent import format_notes, make_format, read_pins
from engine.issues import errors
from engine.markers import _bad_chars, check_anchors, validate_shapes

MAX_PROMPT = 2000
SEED_LIMIT = 2 ** 31


class DirectorInputError(ValueError):
    """The request itself is invalid (bad marker, prompt too long). The caller shows it; no LLM call."""


@dataclass
class Job:
    prompt: str
    seed: int
    fmt: dict
    direction: Direction
    family: str
    pins: dict
    markers: list = field(default_factory=list)
    detected: list = field(default_factory=list)   # unsupported asks found deterministically
    asks: list = field(default_factory=list)       # every ask found, supported or not
    notes: list = field(default_factory=list)      # system assumption lines (format)


def make_job(prompt, profile, catalog, seed=None, markers=None, direction=None):
    prompt = "" if prompt is None else prompt
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT:
        raise DirectorInputError(f"prompt must be text of at most {MAX_PROMPT} characters")
    prompt = " ".join(prompt.split())  # newlines and tabs -> single spaces
    if _bad_chars(prompt):
        raise DirectorInputError("prompt contains control or formatting characters")
    seed = secrets.randbelow(SEED_LIMIT) if seed is None else seed
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < SEED_LIMIT:
        raise DirectorInputError(f"seed must be a whole number from 0 to {SEED_LIMIT - 1}")
    pins = read_pins(prompt)
    fmt = make_format(pins, seed)
    if markers is not None and not isinstance(markers, list):
        raise DirectorInputError("markers must be a list of marker objects")
    markers = copy.deepcopy(markers or [])
    if markers:
        issues = []
        validate_shapes(markers, fmt["durationS"], issues)
        if not errors(issues):
            check_anchors(markers, profile, issues)  # glTF -> placed, surface snap, on-subject
        if errors(issues):
            raise DirectorInputError("; ".join(f"{i.code} at {i.path}: {i.message}" for i in errors(issues)))
    asks = detect(prompt) + [a for m in markers for a in detect(m["text"], source=f"marker:{m['id']}")]
    return Job(prompt=prompt, seed=seed, fmt=fmt, direction=direction or interim_direction(seed, profile, catalog),
               family=family(profile), pins=pins, markers=markers,
               detected=unsupported(asks, catalog, profile), asks=asks, notes=format_notes(pins, fmt))
