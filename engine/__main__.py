"""CLI: py -m engine check <script.json> --profile <profile.json>
        py -m engine ingest <model.glb> [--out profile.json]
        py -m engine render <script.json> --profile P --model M --out DIR [--tier T] [--frames key|all|1,2]
        py -m engine bake --script S --profile P --model M [--owner-ok]
        py -m engine direct --profile P [--prompt TEXT] [--markers M.json] [--seed N] [--duration S]
                            [--provider anthropic|fake:FIXTURE] [--record FIXTURE] [--out script.json] [--strict]
                            [--user TOKEN [--subject-id ID] [--memory-dir D]] [--like FILE_OR_ID]
                            [--less-like FILE] [--avoid AXIS=VALUE ...] [--out-replay FILE]
                            [--verbose | --json-full]
        py -m engine new-user [--memory-dir D]
        py -m engine replay RECORD.json --profile P
        py -m engine variety-report --profile P [--prompt TEXT] [--aspect 9:16] [--viable]

`direct` prints the script, direction, floor and summary; the replay record's copy of the script and the
unfloored rawScript only with --verbose / --json-full. Variety memory is on when --user is set and
--memory-dir or VALORA_VARIETY_DIR gives a root. `replay` takes no provider: it never calls one.

Exit codes: 0 ok, 3 check failed (and a stale / altered / below-floor replay), 2 usage error (argparse),
1 any other error (e.g. no VALORA_VARIETY_SECRET), 4 `direct --strict` fell back because the provider
failed (no key, no SDK, API error), 5 input rejected (bad markers file, prompt, seed, user token,
--like / --avoid this model cannot honour) before any call. Without --strict that fallback still exits
0 (spec: the fallback never fails) and prints one warning line."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile


EXIT_OK, EXIT_ERROR, EXIT_CHECK_FAILED, EXIT_FALLBACK, EXIT_BAD_INPUT = 0, 1, 3, 4, 5


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("script")
    c.add_argument("--profile", required=True)
    i = sub.add_parser("ingest")
    i.add_argument("model")
    i.add_argument("--out")
    rd = sub.add_parser("render")
    rd.add_argument("script")
    rd.add_argument("--profile", required=True)
    rd.add_argument("--model", required=True)
    rd.add_argument("--out", required=True)
    rd.add_argument("--tier", default="preview", choices=["keyframes", "preview", "final"])
    rd.add_argument("--frames", default="key", help="key | all | comma-separated frame numbers")
    rd.add_argument("--save-blend", action="store_true")
    bk = sub.add_parser("bake")          # stage 4b alone: bake every sim miss of a script (phase 6 T98)
    bk.add_argument("--script", required=True)
    bk.add_argument("--profile", required=True)
    bk.add_argument("--model", required=True)
    bk.add_argument("--owner-ok", action="store_true", help="a bake over the bake budget, approved by the owner")
    d = sub.add_parser("direct")
    d.add_argument("--profile", required=True)
    d.add_argument("--prompt", default="")
    d.add_argument("--markers")
    d.add_argument("--seed", type=int)
    d.add_argument("--provider", default="anthropic", help="anthropic | fake:<fixture.json>")
    d.add_argument("--record", help="append live replies to this fixture file")
    d.add_argument("--out")
    d.add_argument("--strict", action="store_true", help="exit 4 if a provider error forced the fallback")
    d.add_argument("--duration", type=float, help="clip length in seconds (default: rolled 8/10/12)")
    d.add_argument("--user", help="a user token from `new-user` (turns variety memory on)")
    d.add_argument("--subject-id", help="memory subject key (default: derived from the profile)")
    d.add_argument("--memory-dir", help="variety memory root (default: VALORA_VARIETY_DIR)")
    d.add_argument("--like", help="more like this: a replay record, a script file or a direction id")
    d.add_argument("--less-like", help="less like this: a replay record or script file")
    d.add_argument("--avoid", action="append", default=[], metavar="AXIS=VALUE", help="repeatable")
    d.add_argument("--out-replay", help="write the signed valora.replay/1 record here")
    d.add_argument("--verbose", action="store_true", help="print the full result (as --json-full)")
    d.add_argument("--json-full", action="store_true", help="print the full result incl. replay and rawScript")
    nu = sub.add_parser("new-user")
    nu.add_argument("--memory-dir")
    rp = sub.add_parser("replay")
    rp.add_argument("record")
    rp.add_argument("--profile", required=True)
    rp.add_argument("--verbose", action="store_true")
    rp.add_argument("--json-full", action="store_true")
    vr = sub.add_parser("variety-report")
    vr.add_argument("--profile", required=True)
    vr.add_argument("--prompt", default="")
    vr.add_argument("--aspect")
    vr.add_argument("--viable", action="store_true", help="also count directions that meet the quality floor")
    a = ap.parse_args(argv)
    try:
        return _run(a)
    except subprocess.TimeoutExpired as e:
        _fail(f"Blender timed out after {e.timeout:g} s")
    except Exception as e:  # noqa: BLE001 - one user-facing line, never a traceback
        _fail(str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__)
    return EXIT_ERROR


def _fail(msg):
    print(f"engine: error: {msg}", file=sys.stderr)


def _run(a):
    if a.cmd == "check":
        script = json.loads(Path(a.script).read_text(encoding="utf-8"))
        prof = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
        r = check(script, prof, Catalog.load())
        print(json.dumps({"ok": r.ok, "issues": [x.to_dict() for x in r.issues], "script": r.script}, indent=2))
        return EXIT_OK if r.ok else EXIT_CHECK_FAILED

    if a.cmd == "render":
        return _render(a)

    if a.cmd == "bake":
        return _bake(a)

    if a.cmd == "direct":
        return _direct(a)

    if a.cmd == "new-user":
        from engine.director.memory import VarietyMemory
        print(VarietyMemory(a.memory_dir).issue_user_token())
        return EXIT_OK

    if a.cmd == "replay":
        return _replay(a)

    if a.cmd == "variety-report":
        return _variety_report(a)

    from engine.ingest.run import ingest  # only needs Blender for this command
    doc = json.dumps(ingest(a.model).to_dict(), indent=2)
    if a.out:
        Path(a.out).write_text(doc, encoding="utf-8")
    print(doc)
    return EXIT_OK


def _frames(spec):
    if spec in ("key", "all"):
        return spec
    return [int(x) for x in spec.split(",") if x.strip()]


def _render(a):
    from engine.compiler import run  # attribute lookup, so tests can monkeypatch compile_scene
    script = json.loads(Path(a.script).read_text(encoding="utf-8"))
    prof = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
    try:
        res = run.compile_scene(script, prof, a.model, a.out, tier=a.tier, frames=_frames(a.frames),
                                save_blend=a.save_blend)
    except run.CheckFailed as e:
        _fail(f"check failed: {str(e).strip().splitlines()[0]}")
        return EXIT_CHECK_FAILED
    print(json.dumps({"ok": True, "out": a.out, "compile": res}, indent=2))
    return EXIT_OK


def _bake(a):
    from engine.bake.run import bake_sims
    from harness.budget import BakeBudget
    script = json.loads(Path(a.script).read_text(encoding="utf-8"))
    prof = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
    try:
        out = bake_sims(script, prof, a.model, catalog=Catalog.load(), budget=BakeBudget(owner_ok=a.owner_ok))
    except ValueError as e:
        _fail(f"check failed: {str(e).strip().splitlines()[0]}")
        return EXIT_CHECK_FAILED
    print(json.dumps({"ok": True, "bakes": out}, indent=2))
    return EXIT_OK


def _provider(spec, record=None):
    from engine.director.llm import FakeProvider, RecordingProvider
    if spec.startswith("fake:"):
        p = FakeProvider.from_fixture(spec[5:])
    elif spec == "anthropic":
        from engine.director.providers.anthropic_provider import AnthropicProvider
        p = AnthropicProvider()
    else:
        raise ValueError(f"unknown provider {spec!r}")
    return RecordingProvider(p, record) if record else p


def _profile(path):
    return SubjectProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _print_result(res, full):
    """Default output: the script, direction, floor and summary. The replay record repeats the whole
    script and rawScript is the unfloored one, so both only with --verbose / --json-full."""
    d = res.to_dict()
    if not full:
        d.pop("rawScript", None)
        rec = d.pop("replay", None) or {}
        d["replay"] = {k: rec[k] for k in ("schema", "seed", "rulebookVersion") if k in rec}
    print(json.dumps(d, indent=2))


def _read_json_arg(value, what):
    from engine.director.job import DirectorInputError
    p = Path(value)
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DirectorInputError(f"{what} file is not JSON: {p.name}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("direction"), dict):
        raise DirectorInputError(f"{what} file is not a saved script or replay record: {p.name}")
    return doc


def _like(value):
    """A replay record or script file (its dict, so its duration carries over), else a direction id."""
    if value is None:
        return None
    doc = _read_json_arg(value, "--like")
    return doc if doc is not None else value


def _avoid(a, prof, catalog):
    """--avoid AXIS=VALUE (repeatable) plus --less-like FILE (its mood and opener, and its world when the
    subject has more than one). None when neither is given."""
    from engine.director.axes import axis_values
    from engine.director.direction import parse_id
    from engine.director.job import DirectorInputError
    out = {}
    for item in a.avoid:
        axis, sep, value = item.partition("=")
        if not sep or not axis.strip() or not value.strip():
            raise DirectorInputError(f"--avoid wants AXIS=VALUE, got {item!r}")
        out.setdefault(axis.strip(), []).append(value.strip())
    if a.less_like:
        doc = _read_json_arg(a.less_like, "--less-like")
        if doc is None:
            raise DirectorInputError("--less-like wants a saved script or replay record file")
        try:
            axes = parse_id(doc["direction"]["id"])
        except (KeyError, TypeError, ValueError):
            raise DirectorInputError("--less-like file has no valid direction") from None
        worlds = axis_values(prof, catalog, {"aspect": "9:16", "durationS": 10, "fps": 24}, rollable=False)["world"]
        for axis in ("mood", "opener") + (("world",) if len(worlds) > 1 else ()):
            out.setdefault(axis, []).append(axes[axis])
    return {k: list(dict.fromkeys(v)) for k, v in out.items()} or None


def _direct(a):
    import os

    from engine.director.job import DirectorInputError
    from engine.director.memory import MEMORY_ENV, VarietyMemory
    from engine.director.pipeline import direct
    prof = _profile(a.profile)
    catalog = Catalog.load()
    markers = json.loads(Path(a.markers).read_text(encoding="utf-8")) if a.markers else None
    root = a.memory_dir or os.environ.get(MEMORY_ENV)
    if a.user and not root:
        _fail(f"input rejected: --user needs --memory-dir or {MEMORY_ENV}")
        return EXIT_BAD_INPUT
    memory = VarietyMemory(root) if a.user else None
    try:
        res = direct(a.prompt, prof, provider=_provider(a.provider, a.record), seed=a.seed, markers=markers,
                     catalog=catalog, duration=a.duration, like=_like(a.like), avoid=_avoid(a, prof, catalog),
                     user=a.user if memory else None, subject_id=a.subject_id, memory=memory)
    except DirectorInputError as e:
        _fail(f"input rejected: {e}")
        return EXIT_BAD_INPUT
    if a.out:
        Path(a.out).write_text(json.dumps(res.script, indent=2), encoding="utf-8")
    if a.out_replay:
        Path(a.out_replay).write_text(json.dumps(res.replay, indent=2), encoding="utf-8")
    _print_result(res, a.verbose or a.json_full)
    err = _provider_error(res)
    if err:
        print(f"engine: warning: the AI director was unavailable ({err}); used the built-in fallback script",
              file=sys.stderr)
        return EXIT_FALLBACK if a.strict else EXIT_OK
    return EXIT_OK


def _replay(a):
    from engine.director.variety import ReplayStale, replay
    try:
        record = json.loads(Path(a.record).read_text(encoding="utf-8"))
    except ValueError:
        _fail("replay: the record is not JSON")
        return EXIT_CHECK_FAILED
    try:
        res = replay(record, _profile(a.profile), Catalog.load())
    except ReplayStale as e:
        _fail(f"replay refused: {e}")
        return EXIT_CHECK_FAILED
    _print_result(res, a.verbose or a.json_full)
    return EXIT_OK


def _variety_report(a):
    import dataclasses

    from engine.catalog import ASPECTS
    from engine.director.job import base_job
    from engine.director.variety import reachable
    if a.aspect is not None and a.aspect not in ASPECTS:
        _fail(f"input rejected: --aspect must be one of {', '.join(ASPECTS)}")
        return EXIT_BAD_INPUT
    prof, catalog = _profile(a.profile), Catalog.load()
    job = base_job(a.prompt or "a 10 second clip", prof, catalog, seed=0)
    if a.aspect:                                         # the same format for enumeration AND viability
        job = dataclasses.replace(job, fmt={**job.fmt, "aspect": a.aspect})
    print(json.dumps(reachable(prof, catalog, job.fmt, job=job if a.viable else None, prompt=a.prompt), indent=2))
    return EXIT_OK


def _provider_error(res):
    """The first provider error's one-line message when it is why the fallback was used, else None."""
    if res.source != "fallback":
        return None
    msg = next((r["error"] for r in res.rounds if "error" in r), None)
    return (msg.strip().splitlines() or ["provider error"])[0][:200] if msg is not None else None


if __name__ == "__main__":
    sys.exit(main())
