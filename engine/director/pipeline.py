"""Stage 3 of spec §3: prompt + profile (+ markers) -> a checked valora.scene/1 script.
One director call, at most MAX_REPAIR_CALLS repair calls (spec §4.9), then the fallback (spec §4.6).
Checker errors and failing TIERS [S] items are reported back; small craft items are fixed in place.
The best checker-valid script seen is kept, so a valid script is never thrown away for a worse one.

The repair conversation only grows: the system text, the schema and every earlier message are sent
again unchanged, and the model's own reply is replayed as the provider returned it
(LLMResult.assistant_content), because thinking blocks are bound to the exact earlier conversation.
A provider error ends the loop (providers already retried transient failures). The compact schema is
the default; with VALORA_DIRECTOR_SCHEMA=full an API rejection of the full schema as too complex
resends the same turn once with the compact schema.

Phase 4: variety memory is read -> rolled -> recorded under a per user+subject lock BEFORE the provider
call (the lock is never held across it); a busy lock or a failed write only costs the memory step.
Every delivery path is gated on the quality floor: a below-floor script is replaced by the direction's
fallback, else by the pin-keeping phase-3 default (floor.floor_default), which meets it by definition.
The result carries the direction and a valora.replay/1 record (variety.replay)."""
import dataclasses
import time
from dataclasses import asdict, dataclass, field

from engine.catalog import Catalog
from engine.checker import check
from engine.director.adherence import enforce_direction, should_enforce
from engine.director.axes import axis_values
from engine.director.details import vary_details
from engine.director.fallback import FallbackError, build_fallback
from engine.director.floor import _RANK, floor_default, floor_tier, make_viable, script_tier
from engine.director.job import DirectorInputError, base_job, make_job, with_direction
from engine.director.llm import LLMError
from engine.director.memory import MemoryBusy
from engine.director.output_schema import default_compact, scene_output_schema
from engine.director.repair import _ORDER, _tier, auto_fix_craft, craft_failures, problems
from engine.director.request import first_message, repair_message
from engine.director.rulebook import load_rulebook
from engine.director.sanitize import parse_output, sanitize
from engine.director.variety import replay_record, subject_key
from engine.issues import Issue, errors

MAX_REPAIR_CALLS = 2
MAX_TOKENS = 32000
BUSY_NOTE = "couldn't read your history just now, so this one may repeat a recent look"
PHASE3_NOTE = "used the standard look to keep the quality up; your direction couldn't be met at full quality"


@dataclass
class DirectorResult:
    script: dict
    source: str                      # llm | llm+repair1 | llm+repair2 | fallback
    firstPassOk: bool                # the first reply passed the checker (in-place checker repairs allowed)
    firstPassClean: bool             # ... and needed no checker repair at all
    rounds: list = field(default_factory=list)
    craftFailures: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    rulebookVersion: str = ""
    seconds: float = 0.0
    compactSchema: bool = False      # the compact schema was sent (the default, or after a full-schema rejection)
    direction: dict = field(default_factory=dict)   # {id, source, axes, pinned, flags}
    replay: dict = field(default_factory=dict)      # valora.replay/1 (variety.replay_record)
    # The unfloored path, so a regression gate can measure what the LLM loop / fallback produced before the
    # floor swapped it (substitution must never hide a drop): {need, rawTier, rawSource, rawCraftFailures,
    # substituted}. rawScript is that script when it was substituted, else None (== script).
    floor: dict = field(default_factory=dict)
    rawScript: dict | None = None

    def to_dict(self):
        return asdict(self)


def _rank(fail_ids):
    """Sort key for a valid script's craft failures (lower is better): the worst tier first (one T1
    failure caps the render at T1, worse than any number of T3 ones), then how many."""
    worst = min((_ORDER[_tier(i)] for i in fail_ids), default=_ORDER["T4"] + 1)
    return (-worst, len(fail_ids))


def _evaluate(res, job, profile, catalog):
    """Never raises: the fallback never fails, so ANY reply ends as issues, not an exception."""
    try:
        return _evaluate_reply(res, job, profile, catalog)
    except Exception as e:  # noqa: BLE001 - a hostile/malformed reply must not escape direct()
        return None, [Issue("llm_bad_reply", "", f"the reply could not be read ({type(e).__name__})", "error")], []


def _evaluate_reply(res, job, profile, catalog):
    if res.stop_reason in ("refusal", "max_tokens"):
        return None, [Issue(f"llm_stop_{res.stop_reason}", "", "the model stopped without a script", "error")], []
    raw, perr = parse_output(res.text)
    if raw is None:
        return None, perr, []
    script, sissues = sanitize(raw, job, catalog, profile)
    if isinstance(script, dict) and isinstance(script.get("shots"), list) and script["shots"]:
        # The rolled direction is the brief (Task 45), then layer 1 seeds the look params the reply left
        # unset, BEFORE the checker fills defaults (so explicit params are kept, unset ones vary).
        script, dissues = enforce_direction(script, job.direction, catalog, enforce=should_enforce(job.prompt, job.direction))
        script = vary_details(script, job.seed, catalog)
        sissues = sissues + dissues
    r = check(script, profile, catalog)
    return r.script, sissues, r.issues


def _merge_avoid(stored, avoid):
    out = {a: sorted(set(stored.get(a, [])) | set((avoid or {}).get(a, []))) for a in set(stored) | set(avoid or {})}
    return {a: v for a, v in out.items() if v} or None


def _job_with_memory(prompt, profile, catalog, memory, user, subject, avoid, kw, flags):
    """read -> pick -> record atomically under the memory lock. Everything that does not depend on memory
    (the job, the floor, viability of the likely pick) is computed OUTSIDE it: a short locked peek reads
    the history, the pick is made unlocked (warming the viability cache), then the locked pass re-reads,
    re-picks from cached verdicts and records. A bad token/subject is the caller's input error; a busy
    lock or a failed write costs only the memory step (never the job)."""
    if avoid is not None and not isinstance(avoid, dict):
        raise DirectorInputError("'less like this' must name values per axis")
    base = base_job(prompt, profile, catalog, **kw)
    rolled = kw.get("direction") is None
    viable = make_viable(base, profile, catalog) if rolled else None

    def pick(history, stored):
        if not rolled:
            return base
        return with_direction(base, profile, catalog, like=kw.get("like"), avoid=_merge_avoid(stored, avoid),
                              history=history, viable=viable)
    try:
        with memory.locked(user, subject):
            peek = (memory.recent(user, subject), memory.avoided(user, subject))
        pick(*peek)                                      # unlocked: fills the viability cache
        with memory.locked(user, subject):
            job = pick(memory.recent(user, subject), memory.avoided(user, subject))
            known = axis_values(profile, catalog, job.fmt, rollable=False)
            try:
                memory.record(user, subject, job.direction, seed=job.seed, duration_s=job.fmt["durationS"],
                              known=known)
                if avoid:
                    memory.dislike(user, subject, avoid, known=known)
            except (OSError, ValueError):
                flags.append("memory_write_failed")
            return job
    except DirectorInputError:
        raise
    except ValueError as e:                              # a bad user token / subject key
        raise DirectorInputError(str(e)) from e
    except (MemoryBusy, OSError):                        # after locked()'s own backoff retries
        flags.append("memory_busy")                      # the MEMORY step fails; the job goes on
        job = pick((), {})                               # no history read, nothing written
        return dataclasses.replace(job, notes=job.notes + [BUSY_NOTE])


def _floor_gate(script, craft, source, job, profile, catalog, flags):
    """Every delivery path (LLM, repaired, fallback) meets the REQUIRED floor, or is replaced. Returns
    (script, craft, source, floor record, raw script or None)."""
    need = floor_tier(job, profile, catalog)
    raw_tier = script_tier(script, profile, catalog)
    record = {"need": need, "rawTier": raw_tier, "rawSource": source, "rawCraftFailures": list(craft),
              "substituted": False}
    if _RANK[raw_tier] >= _RANK[need]:
        return script, craft, source, record, None
    raw = script
    try:
        fb = build_fallback(job, profile, catalog)
    except FallbackError:
        fb = None
    if fb is not None and _RANK[script_tier(fb, profile, catalog)] >= _RANK[need]:
        script, source = fb, source + "+floor"
    else:                                                # meets the floor by definition (floor.py)
        script, _dropped = floor_default(job, profile, catalog, need=need)
        source = source + "+phase3"
        flags.append("floor_phase3_default")
        script["assumptions"] = list(script.get("assumptions", [])) + [PHASE3_NOTE]
    if _RANK[script_tier(script, profile, catalog)] < _RANK[need]:
        raise FallbackError("internal: a below-floor script reached delivery")   # impossible by construction
    record["substituted"] = True
    return script, [f.id for f in craft_failures(script, profile, catalog)], source, record, raw


def direct(prompt, profile, *, provider, catalog=None, seed=None, markers=None, direction=None, rulebook=None,
           duration=None, like=None, avoid=None, user=None, subject_id=None, memory=None):
    t0 = time.perf_counter()
    catalog = catalog or Catalog.load()
    flags = []
    kw = dict(seed=seed, markers=markers, direction=direction, like=like, duration=duration)
    if memory is not None and user is not None:
        subject = subject_key(profile) if subject_id is None else subject_id
        job = _job_with_memory(prompt, profile, catalog, memory, user, subject, avoid, kw, flags)
    else:
        job = make_job(prompt, profile, catalog, avoid=avoid, **kw)
    system, version = rulebook or load_rulebook()
    compact = default_compact()
    schema = scene_output_schema(catalog, compact=compact)
    messages = [{"role": "user", "content": first_message(fmt=job.fmt, direction=job.direction, profile=profile,
                                                          prompt=job.prompt, markers=job.markers,
                                                          detected=job.detected)}]
    rounds, usage, best = [], {}, None
    first_ok = first_clean = False
    call = 0
    while True:
        try:
            res = provider.generate(system=system, messages=messages, schema=schema, max_tokens=MAX_TOKENS)
        except LLMError as e:
            rounds.append({"call": call, "error": str(e), "retryable": e.retryable, "kind": e.kind})
            if e.kind == "schema_too_complex" and not compact:
                schema, compact = scene_output_schema(catalog, compact=True), True
                continue
            break
        for k, v in (res.usage or {}).items():
            usage[k] = usage.get(k, 0) + v
        script, sissues, cissues = _evaluate(res, job, profile, catalog)
        issues = sissues + cissues
        ok = script is not None and not errors(issues)
        fails = craft_failures(script, profile, catalog) if ok else []
        if ok and fails:
            fixed, fix_issues = auto_fix_craft(script, fails, profile, catalog)
            if fix_issues:
                r2 = check(fixed, profile, catalog)
                if r2.ok:
                    script, issues = r2.script, issues + fix_issues + r2.issues
                    fails = craft_failures(script, profile, catalog)
        if call == 0:
            first_ok = ok
            first_clean = ok and not any(i.severity == "repaired" for i in cissues)
        rounds.append({"call": call, "stop": res.stop_reason, "ok": ok,
                       "errors": sorted({i.code for i in errors(issues)}),
                       "repaired": sorted({i.code for i in issues if i.severity == "repaired"}),
                       "craftFailures": [f.id for f in fails]})
        if ok and (best is None or _rank([f.id for f in fails]) < _rank(best[1])):
            best = (script, [f.id for f in fails], call)
        if (ok and not fails) or res.stop_reason == "refusal" or call == MAX_REPAIR_CALLS:
            break
        messages = messages + [{"role": "assistant", "content": res.assistant_content},
                               {"role": "user", "content": repair_message(problems(issues, fails))}]
        call += 1
    if best is not None:
        script, craft, call = best
        source = "llm" if call == 0 else f"llm+repair{call}"
    else:
        script = build_fallback(job, profile, catalog)
        craft, source = [f.id for f in craft_failures(script, profile, catalog)], "fallback"
    script, craft, source, floor, raw = _floor_gate(script, craft, source, job, profile, catalog, flags)
    d = job.direction
    res = DirectorResult(script=script, source=source, firstPassOk=first_ok, firstPassClean=first_clean,
                         rounds=rounds, craftFailures=craft, usage=usage, rulebookVersion=version,
                         seconds=round(time.perf_counter() - t0, 3), compactSchema=compact,
                         direction={"id": d.id, "source": d.source, "axes": d.axes(), "pinned": list(d.pinned),
                                    "flags": flags + list(job.varietyFlags)},
                         floor=floor, rawScript=raw)
    res.replay = replay_record(res, job)
    return res
