"""Task 32 in one command (owner-gated: needs ANTHROPIC_API_KEY and spend OK):

    py -m harness director-live               # probe + live smoke + 3 recorded fixtures + cost estimate
    py -m harness director-live --full-eval   # ... then the full paid eval (9 models x 15 prompts)

Steps, stopping at the first failure:
 1. credentials: only whether ANTHROPIC_API_KEY is set is ever printed (exit 2 if not: owner item O1);
 2. schema probe: does the API accept the FULL output schema? (exit 3 on a provider error - a 403,
    connection reset or web-shield page means antivirus blocks api.anthropic.com: stop and report);
    the rest of the run uses the accepted mode (full if accepted, else compact);
 3. live smoke: py -m pytest engine/tests/test_director_live.py -m live (exit 4 if it fails);
 4. record three replies into engine/tests/fixtures/director/live-*.json (exit 3 on a provider error);
 5. offline replay: py -m pytest engine/tests/test_director_recorded.py (exit 4 if it fails);
 6. cost: measured tokens of the three recorded jobs x PRICES -> estimate for the full list;
 7. only with --full-eval: py -m harness direct --provider anthropic (spends roughly the estimate).
The report is written to <out_dir>/live.json. Commit the fixtures and the tests afterwards (plan
Task 32 Step 5); put the headline numbers in the handoff, not in code."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from engine.director.capabilities import detect
from engine.director.llm import FakeProvider, RecordingProvider
from engine.director.output_schema import SCHEMA_ENV
from engine.director.pipeline import direct
from harness.director_eval import (ECHO_CHARS, MODELS, _cost, _profile, load_prompt_set, markers_for,
                                   probe_schema, run_director_eval)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "engine" / "tests" / "fixtures" / "director"
KEY_ENV = "ANTHROPIC_API_KEY"
# The plan's three fixtures: empty prompt, an unsupported ask, and the hostile marker set.
RECORD_CASES = [
    {"id": "empty", "model": "sneaker", "prompt": "", "seed": 5, "durationS": 10, "expectUnsupported": []},
    {"id": "rainy_night", "model": "sports_car", "prompt": "rainy night", "seed": 5, "durationS": 10,
     "expectUnsupported": ["weather.rain"]},
    {"id": "hostile", "model": "pocket_watch", "prompt": "ad", "seed": 5, "durationS": 10, "markers": "hostile",
     "expectUnsupported": []},
]
BLOCKED_HINT = ("If this is HTTP 403, a connection reset or an antivirus web-shield page, antivirus "
                "(Avast/WebShield, Norton) is blocking api.anthropic.com: STOP and report it; do not "
                "work around it or disable protection.")


def fixture_path(case, fixtures_dir=FIXTURES):
    return Path(fixtures_dir) / f"live-{case['model']}-{case['id']}.json"


def _markers(case, profile):
    if not case.get("markers"):
        return None
    _, sets = load_prompt_set("v1")
    return markers_for(sets[case["markers"]], profile)


def _provider_error(res):
    return next((r["error"] for r in res.rounds if "error" in r and r.get("kind") != "schema_too_complex"), None)


def record_case(case, path, provider):
    """Run one director job through `provider`, recording every reply into a fresh fixture at `path`,
    then store the job and the expected outcome beside the replies (never the system text or a key)."""
    path = Path(path)
    if path.exists():
        path.unlink()
    profile = _profile(case["model"])
    markers = _markers(case, profile)
    res = direct(case["prompt"], profile, provider=RecordingProvider(provider, path), seed=case["seed"],
                 markers=markers, duration=case.get("durationS"))
    fx = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"replies": [], "recorded": []}
    fx["job"] = {"model": case["model"], "prompt": case["prompt"], "seed": case["seed"], "markers": markers,
                 "durationS": res.script["format"]["durationS"]}
    fx["expect"] = {"source": res.source, "unsupported": list(case.get("expectUnsupported", []))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fx, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


def verify_recorded(path):
    """Replay a recorded fixture offline. Returns a list of problems ([] = good): the script passes the
    checker, the source matches the live run, expected asks are reported, hostile text is not echoed."""
    from engine.catalog import Catalog
    from engine.checker import check
    fx = json.loads(Path(path).read_text(encoding="utf-8"))
    job, exp = fx["job"], fx["expect"]
    profile = _profile(job["model"])
    res = direct(job["prompt"], profile, provider=FakeProvider(fx["replies"]), seed=job["seed"],
                 markers=job.get("markers"), duration=job.get("durationS", 10))   # pre-phase-4 recordings are 10 s
    s, out = res.script, []
    if not check(s, profile, Catalog.load()).ok:
        out.append("the replayed script fails the checker")
    if res.source != exp["source"]:
        out.append(f"source {res.source} != recorded {exp['source']}")
    reported = {u["capability"] for u in s.get("unsupported", [])}
    out += [f"{tag} not reported in unsupported" for tag in exp.get("unsupported", []) if tag not in reported]
    said = " ".join(s.get("assumptions", []) + [u["ask"] for u in s.get("unsupported", [])]).casefold()
    for m in job.get("markers") or []:
        if not detect(m["text"]) and m["text"][:ECHO_CHARS].casefold() in said:
            out.append(f"hostile marker text echoed: {m['id']}")
    return out


def _pytest(args, env):
    return subprocess.run([sys.executable, "-m", "pytest", *args], cwd=ROOT, env=env).returncode


def _say(msg):
    print(f"director-live: {msg}", file=sys.stderr)


def run_live(env=None, provider_factory=None, out_dir=None, fixtures_dir=None, pytest_runner=None,
             full_eval=False):
    env = dict(os.environ if env is None else env)
    has_key = bool(env.get(KEY_ENV))
    _say(f"{KEY_ENV} set: {has_key}")                   # the value is never printed
    if not has_key:
        _say(f"no {KEY_ENV}: owner item O1 in the phase 3 plan (create a key, add it as a user "
             f"environment variable, reopen the terminal). Nothing was called.")
        return 2
    if provider_factory is None:
        from engine.director.providers.anthropic_provider import AnthropicProvider
        live = AnthropicProvider()
        provider_factory = lambda: live  # noqa: E731
    pytest_runner = pytest_runner or _pytest
    fixtures_dir = Path(fixtures_dir or FIXTURES)
    out_dir = Path(out_dir or ROOT / "harness" / "out" / "director" / f"live-{time.strftime('%Y%m%d-%H%M%S')}")
    report = {"steps": []}
    first = provider_factory()
    model_id = getattr(first, "model", None)
    report["model"] = model_id

    probe = probe_schema(first)
    report["probe"] = probe
    if probe["full"] == "error":
        _say(f"stopped at the schema probe: provider error: {probe['detail'][:200]}. {BLOCKED_HINT}")
        _write(out_dir, report)
        return 3
    mode = "full" if probe["full"] == "accepted" else "compact"
    _say(f"schema probe: full {probe['full']} -> this run uses the {mode} schema"
         + (" (flip output_schema.default_compact to full and commit)" if mode == "full" else ""))
    env[SCHEMA_ENV] = mode
    report["schemaMode"] = mode
    old_mode = os.environ.get(SCHEMA_ENV)
    os.environ[SCHEMA_ENV] = mode
    try:
        code = pytest_runner(["engine/tests/test_director_live.py", "-q", "-m", "live"], env)
        report["steps"].append({"liveSmoke": code})
        if code:
            _say("the live smoke failed (see the pytest output above)")
            _write(out_dir, report)
            return 4
        usages = []
        for case in RECORD_CASES:
            path = fixture_path(case, fixtures_dir)
            res = record_case(case, path, provider_factory())
            err = _provider_error(res)
            if err:
                _say(f"stopped while recording {path.name}: provider error: {err[:200]}. {BLOCKED_HINT}")
                _write(out_dir, report)
                return 3
            usages.append(res.usage)
            report["steps"].append({"recorded": str(path), "source": res.source, "usage": res.usage})
        code = pytest_runner(["engine/tests/test_director_recorded.py", "-q"], env)
        report["steps"].append({"recordedReplay": code})
        if code:
            _say("the offline replay of the recorded fixtures failed")
            _write(out_dir, report)
            return 4
        report["estimate"] = _estimate(usages, model_id)
        _say(f"measured {len(usages)} jobs; full eval estimate: {report['estimate']}")
        if full_eval:
            live_factory = lambda cid: provider_factory()  # noqa: E731
            s = run_director_eval("v1", provider_factory=live_factory, model_id=model_id,
                                  out_root=str(out_dir), run_id="eval")
            report["fullEval"] = s["metrics"]
            _say(f"full eval written to {out_dir / 'eval'}")
    finally:
        if old_mode is None:
            os.environ.pop(SCHEMA_ENV, None)
        else:
            os.environ[SCHEMA_ENV] = old_mode
    _write(out_dir, report)
    _say(f"report: {out_dir / 'live.json'}")
    return 1 if full_eval and (report["fullEval"]["errors"] or report["fullEval"]["providerErrors"]) else 0


def _estimate(usages, model_id):
    prompts, _ = load_prompt_set("v1")
    jobs = len(MODELS) * len(prompts)
    total = {}
    for u in usages:
        for k, v in u.items():
            total[k] = total.get(k, 0) + v
    per_job = _cost({k: v / max(1, len(usages)) for k, v in total.items()}, model_id) if model_id else None
    return {"jobs": jobs, "measuredJobs": len(usages), "tokens": total, "usdPerJob": per_job,
            "usdFullEval": round(per_job * jobs, 2) if per_job is not None else None}


def _write(out_dir, report):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "live.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
