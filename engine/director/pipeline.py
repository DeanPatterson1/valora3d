"""Stage 3 of spec §3: prompt + profile (+ markers) -> a checked valora.scene/1 script.
One director call, at most MAX_REPAIR_CALLS repair calls (spec §4.9), then the fallback (spec §4.6).
Checker errors and failing TIERS [S] items are reported back; small craft items are fixed in place.
The best checker-valid script seen is kept, so a valid script is never thrown away for a worse one.

The repair conversation only grows: the system text, the schema and every earlier message are sent
again unchanged, and the model's own reply is replayed as the provider returned it
(LLMResult.assistant_content), because thinking blocks are bound to the exact earlier conversation.
A provider error ends the loop (providers already retried transient failures). The compact schema is
the default; with VALORA_DIRECTOR_SCHEMA=full an API rejection of the full schema as too complex
resends the same turn once with the compact schema."""
import time
from dataclasses import asdict, dataclass, field

from engine.catalog import Catalog
from engine.checker import check
from engine.director.fallback import build_fallback
from engine.director.job import make_job
from engine.director.llm import LLMError
from engine.director.output_schema import default_compact, scene_output_schema
from engine.director.repair import auto_fix_craft, craft_failures, problems
from engine.director.request import first_message, repair_message
from engine.director.rulebook import load_rulebook
from engine.director.sanitize import parse_output, sanitize
from engine.issues import Issue, errors

MAX_REPAIR_CALLS = 2
MAX_TOKENS = 32000


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

    def to_dict(self):
        return asdict(self)


def _evaluate(res, job, profile, catalog):
    if res.stop_reason in ("refusal", "max_tokens"):
        return None, [Issue(f"llm_stop_{res.stop_reason}", "", "the model stopped without a script", "error")], []
    raw, perr = parse_output(res.text)
    if raw is None:
        return None, perr, []
    script, sissues = sanitize(raw, job, catalog, profile)
    r = check(script, profile, catalog)
    return r.script, sissues, r.issues


def direct(prompt, profile, *, provider, catalog=None, seed=None, markers=None, direction=None, rulebook=None):
    t0 = time.perf_counter()
    catalog = catalog or Catalog.load()
    job = make_job(prompt, profile, catalog, seed=seed, markers=markers, direction=direction)
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
        if ok and (best is None or len(fails) < len(best[1])):
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
    return DirectorResult(script=script, source=source, firstPassOk=first_ok, firstPassClean=first_clean,
                          rounds=rounds, craftFailures=craft, usage=usage, rulebookVersion=version,
                          seconds=round(time.perf_counter() - t0, 3), compactSchema=compact)
