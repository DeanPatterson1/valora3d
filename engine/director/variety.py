"""Stage 2 of spec §3: the job's direction. Order:
1. 'more like this': keep a validated direction with a new seed, so only layer 1 changes;
2. the dice: pins from the prompt, history rotated over the viable pool, dislikes avoided, the floor
   enforced;
3. the interim direction with the prompt's pins applied (pins are never dropped).
Pure: the caller holds the memory lock and reads/writes memory (pipeline.py).
Replay never comes here: replay() returns the saved checked script (no provider call)."""
import hashlib
import hmac
import json
from dataclasses import dataclass

from engine.director.axes import axis_values, validate_axes
from engine.director.baseline_phase3 import profile_key
from engine.director.dice import candidates, roll
from engine.director.direction import AXES, Direction, direction_of, interim_direction, parse_id
from engine.director.family import family
from engine.director.floor import _RANK, floor_tier, make_viable, script_tier
from engine.director.pins import read_direction_pins
from engine.director.taste import STATS

REPLAY_SCHEMA = "valora.replay/1"
FLAG_NOTES = {"avoid_relaxed": "every option was on your 'less like this' list; relaxed it to find one",
              "repeat_after_rotation": "every direction for this model has been used once; starting a new round"}


class DirectionIncompatible(ValueError):
    """A 'more like this' / 'less like this' request this model or catalog cannot honour (plain words)."""


@dataclass(frozen=True)
class Choice:
    direction: Direction
    notes: tuple = ()
    flags: tuple = ()


def subject_key(profile):
    return profile_key(profile)


def _load_stats():
    try:
        return json.loads(STATS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def prompt_pins(prompt, profile, catalog, fmt):
    known = axis_values(profile, catalog, fmt, rollable=False)
    return {a: v for a, v in read_direction_pins(prompt).items() if v in known[a]}


def like_axes(like, profile, catalog, fmt):
    """The axes of a 'more like this' reference: a Direction, a direction id, a saved script or result
    ({"direction": {"id": ...}}), or {"id": ...}. Every value must be one this subject knows."""
    try:
        if isinstance(like, Direction):
            axes = like.axes()
        elif isinstance(like, dict):
            axes = parse_id((like.get("direction") or like)["id"])
        else:
            axes = parse_id(like)
    except (KeyError, TypeError, ValueError):
        raise DirectionIncompatible("that 'more like this' reference can't be used for this model: "
                                    "it is not a saved direction") from None
    bad = validate_axes(axes, profile, catalog, fmt)
    if bad:
        raise DirectionIncompatible(f"that direction can't be used for this model: {', '.join(bad)} "
                                    "is not available here")
    return axes


def check_avoid_shape(avoid):
    """{axis name: [value, ...]} with text only; anything else (null, nested, mixed types) is refused
    before any set()/sorted() touches it."""
    if avoid is None:
        return None
    if not isinstance(avoid, dict) or any(
            not isinstance(a, str) or not isinstance(v, (list, tuple)) or not all(isinstance(x, str) for x in v)
            for a, v in avoid.items()):
        raise DirectionIncompatible("'less like this' must name values per axis, e.g. mood: [clean]")
    return avoid


def check_avoid(avoid, profile, catalog, fmt):
    if not check_avoid_shape(avoid):
        return None
    known = axis_values(profile, catalog, fmt, rollable=False)
    bad = [f"{a}={v}" for a, vals in avoid.items() for v in vals if a not in AXES or v not in known[a]]
    if bad:
        raise DirectionIncompatible(f"'less like this' names things this model doesn't have: {', '.join(map(str, bad))}")
    return {a: list(v) for a, v in avoid.items() if v}


def _line(d):
    words = f"{d.mood}, {d.pace} pace, {d.tone} backdrop, opens with {d.opener}"
    kept = f"; kept from the prompt: {', '.join(d.pinned)}" if d.pinned else ""
    return f"dice direction: {words}{kept}"


def choose_direction(prompt, profile, catalog, seed, fmt, *, job=None, like=None, avoid=None, history=(),
                     stats=None, viable=None):
    """`viable`: a prepared make_viable(job) (the pipeline builds it once, outside the memory lock);
    otherwise it is built here from `job`. The dice test it lazily (dice.roll)."""
    pins = prompt_pins(prompt, profile, catalog, fmt)
    avoid = check_avoid(avoid, profile, catalog, fmt)
    if viable is None and job is not None:
        viable = make_viable(job, profile, catalog)
    if like is not None:
        axes = {**like_axes(like, profile, catalog, fmt), **pins}
        if viable is not None and not viable(axes):
            raise DirectionIncompatible("that direction doesn't meet the quality bar for this model; "
                                        "try 'new direction' instead")
        d = direction_of(axes, "more_like_this", pinned=pins)
        return Choice(d, (f"more like this: kept the direction ({d.mood}, {d.pace} pace); only details change",))
    r = roll(seed, axis_values(profile, catalog, fmt), pins=pins, history=history, avoid=avoid, viable=viable,
             family_name=family(profile), stats=_load_stats() if stats is None else stats)
    if r.axes is None:
        base = parse_id(interim_direction(seed, profile, catalog).id)
        d = direction_of({**base, **pins}, "interim", pinned=pins)
        return Choice(d, ("no rolled direction met the quality floor; used the default direction",), r.flags)
    d = direction_of(r.axes, "dice", pinned=pins)
    return Choice(d, (_line(d),) + tuple(FLAG_NOTES[f] for f in r.flags if f in FLAG_NOTES), r.flags)


def reachable(profile, catalog, fmt, job=None, prompt=""):
    """Catalog-size honesty (spec §6 'honest limit') for THIS prompt: the same pins, format and
    viability rules the dice use."""
    pins = prompt_pins(prompt, profile, catalog, fmt)
    vals = axis_values(profile, catalog, fmt)
    cands = candidates(vals, pins)
    out = {"pins": pins, "perAxis": vals, "combinations": len(cands),
           "singleValued": [a for a in AXES if a not in pins and len(vals[a]) == 1]}
    if job is not None:
        v = make_viable(job, profile, catalog)
        out["viable"], out["floor"] = sum(1 for c in cands if v(c)), v.floor
    n = out.get("viable", out["combinations"])
    out["distinctBeforeRepeat"] = n
    out["note"] = (f"{n} distinct directions for this model and prompt; axes with one value: "
                   f"{', '.join(out['singleValued']) or 'none'}. Perceived variety is capped by the catalog.")
    return out


class ReplayStale(ValueError):
    """The saved script no longer checks against today's catalog, misses the floor, or the record was altered."""


REPLAY_KEY_LABEL = b"valora-replay/1"


_REPLAY_KEYS = {}


def _replay_key():
    """Derived from the server secret (memory.py: VALORA_VARIETY_SECRET, or the dev key file), separated
    from the user-token key by its label. Cached per secret source."""
    import os

    from engine.director.memory import MEMORY_ENV, SECRET_ENV, VarietyMemory
    src = (os.environ.get(SECRET_ENV), os.environ.get(MEMORY_ENV))
    if src not in _REPLAY_KEYS:
        _REPLAY_KEYS[src] = hmac.new(VarietyMemory()._key_bytes(), REPLAY_KEY_LABEL, hashlib.sha256).digest()
    return _REPLAY_KEYS[src]


def _canonical(record):
    body = {k: v for k, v in record.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _signature(record):
    return hmac.new(_replay_key(), _canonical(record), hashlib.sha256).hexdigest()


def replay_record(result, job):
    """valora.replay/1: the delivered checked script plus what produced it, HMAC-signed with the server
    secret over its canonical JSON. replay() returns the script byte-identical; the rest is provenance
    (seed, prompt, the DELIVERED direction with pins and flags, format, markers, rulebook version)."""
    rec = json.loads(json.dumps(
        {"schema": REPLAY_SCHEMA, "script": result.script, "seed": job.seed, "prompt": job.prompt,
         "direction": dict(result.direction), "format": dict(job.fmt), "pins": dict(job.pins),
         "assumptions": list(result.script.get("assumptions", [])), "markers": list(job.markers),
         "rulebookVersion": result.rulebookVersion}))
    rec["signature"] = _signature(rec)
    return rec


_HEX64 = frozenset("0123456789abcdef")


def _signed(record):
    sig = record.get("signature")
    if not isinstance(sig, str) or len(sig) != 64 or not set(sig) <= _HEX64:
        return False                             # compare_digest raises on non-ASCII text: check the shape first
    try:
        want = _signature(record)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(sig, want)


def replay(record, profile, catalog, provider=None):
    """Return the saved checked script as a DirectorResult. Never calls `provider` (kept in the
    signature only so callers can pass one and a test can prove it is unused). Refused (ReplayStale),
    never substituted: an unsigned or altered record, a script today's checker rejects or would change,
    and a script below today's quality floor for its job."""
    import copy

    from engine.checker import check
    from engine.director.job import DirectorInputError, base_job
    from engine.director.pipeline import DirectorResult
    s = record.get("script") if isinstance(record, dict) else None
    sd, rd = (s.get("direction"), record.get("direction")) if isinstance(s, dict) else (None, None)
    if (not isinstance(s, dict) or record.get("schema") != REPLAY_SCHEMA or s.get("seed") != record.get("seed")
            or s.get("format") != record.get("format") or s.get("assumptions") != record.get("assumptions")
            or not isinstance(rd, dict) or not isinstance(sd, dict) or not isinstance(sd.get("id"), str)
            or sd["id"] != rd.get("id")):
        raise ReplayStale("this replay record does not match its script")
    if not _signed(record):
        raise ReplayStale("this replay record was not issued by this server or has been altered")
    try:
        r = check(copy.deepcopy(s), profile, catalog)
    except Exception as e:  # noqa: BLE001 - a malformed saved script is stale, never a crash
        raise ReplayStale(f"the saved script could not be checked ({type(e).__name__})") from None
    if not r.ok:
        raise ReplayStale("the saved script no longer passes today's checker: "
                          + ", ".join(sorted({i.code for i in r.issues if i.severity == "error"})))
    if r.script != s:
        raise ReplayStale("today's checker would change the saved script, so it cannot replay exactly")
    try:
        job = base_job(record.get("prompt"), profile, catalog, seed=record.get("seed"),
                       markers=record.get("markers"),
                       direction=direction_of(parse_id(s["direction"]["id"]), "replay"),
                       duration=s["format"].get("durationS"))
    except (DirectorInputError, ValueError, KeyError, TypeError):
        raise ReplayStale("the replay record's job can no longer be rebuilt") from None
    if job.fmt != s["format"]:
        raise ReplayStale("the replay record's format no longer matches its prompt")
    need = floor_tier(job, profile, catalog)
    if _RANK[script_tier(s, profile, catalog)] < _RANK[need]:
        raise ReplayStale(f"the saved script is below today's quality floor ({need}) for this model")
    return DirectorResult(script=s, source="replay", firstPassOk=True, firstPassClean=True,
                          rulebookVersion=record.get("rulebookVersion", ""),
                          direction={**record["direction"], "source": "replay"}, replay=record)
