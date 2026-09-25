"""One director job: everything the system decides before the LLM is called."""
import copy
import dataclasses
import secrets
from dataclasses import dataclass, field

from engine.director.capabilities import detect, unsupported
from engine.director.direction import Direction, interim_direction
from engine.director.dice import roll_duration
from engine.director.family import family
from engine.director.intent import format_notes, make_format, read_pins
from engine.issues import errors
from engine.markers import _bad_chars, check_anchors, validate_shapes
from engine.script import DURATION_RANGE

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
    notes: list = field(default_factory=list)      # system assumption lines (format, direction)
    varietyFlags: list = field(default_factory=list)  # dice flags (avoid_relaxed, repeat_after_rotation, ...)


def _duration(value, what):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not             DURATION_RANGE[0] <= value <= DURATION_RANGE[1]:
        raise DirectorInputError(f"{what} must be a number of seconds from {DURATION_RANGE[0]} to "
                                 f"{DURATION_RANGE[1]}")
    return value


def make_job(prompt, profile, catalog, seed=None, markers=None, direction=None, *, like=None, avoid=None,
             history=(), duration=None, stats=None):
    """direction given: used verbatim (replay, harness, phase-3 baseline). Otherwise choose_direction:
    'more like this' -> dice (pins, history, avoid, the floor) -> interim with pins.
    Duration order: a prompt pin > explicit `duration` > the liked script's duration > rolled; with a
    given direction and no duration the phase-3 10 s default stands."""
    job = base_job(prompt, profile, catalog, seed=seed, markers=markers, direction=direction, like=like,
                   duration=duration)
    if direction is not None:
        return job
    return with_direction(job, profile, catalog, like=like, avoid=avoid, history=history, stats=stats)


def base_job(prompt, profile, catalog, seed=None, markers=None, direction=None, *, like=None, duration=None):
    """Everything make_job decides that does not depend on variety memory (validation, format, markers,
    asks). Its direction is `direction` or the interim one until with_direction() rolls it."""
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
    duration = _duration(duration, "duration")
    if "durationS" not in pins and duration is None:
        liked = like.get("format", {}).get("durationS") if isinstance(like, dict)             and isinstance(like.get("format"), dict) else None
        duration = _duration(liked, "the liked clip's duration")
        if duration is None and direction is None:
            duration = roll_duration(seed)
    fmt = make_format(pins, seed, duration=duration)
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
    job = Job(prompt=prompt, seed=seed, fmt=fmt, direction=direction or interim_direction(seed, profile, catalog),
              family=family(profile), pins=pins, markers=markers,
              detected=unsupported(asks, catalog, profile), asks=asks, notes=format_notes(pins, fmt))
    return job


def with_direction(job, profile, catalog, *, like=None, avoid=None, history=(), stats=None, viable=None):
    """The job with its chosen direction (variety.choose_direction). `viable`: a prepared
    make_viable(job), so a caller holding the memory lock only pays cached viability checks."""
    from engine.director.variety import DirectionIncompatible, choose_direction  # lazy: variety -> floor
    try:
        c = choose_direction(job.prompt, profile, catalog, job.seed, job.fmt, job=job, like=like, avoid=avoid,
                             history=history, stats=stats, viable=viable)
    except DirectionIncompatible as e:
        raise DirectorInputError(str(e)) from e
    return dataclasses.replace(job, direction=c.direction, notes=job.notes + list(c.notes),
                               varietyFlags=list(c.flags))
