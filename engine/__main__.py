"""CLI: py -m engine check <script.json> --profile <profile.json>
        py -m engine ingest <model.glb> [--out profile.json]
        py -m engine render <script.json> --profile P --model M --out DIR [--tier T] [--frames key|all|1,2]
        py -m engine direct --profile P [--prompt TEXT] [--markers M.json] [--seed N]
                            [--provider anthropic|fake:FIXTURE] [--record FIXTURE] [--out script.json] [--strict]

Exit codes: 0 ok, 3 check failed, 2 usage error (argparse), 1 any other error,
4 `direct --strict` fell back because the provider failed (no key, no SDK, API error),
5 `direct` input rejected (bad markers file, prompt, seed) before any call. Without
--strict that fallback still exits 0 (spec: the fallback never fails) and prints one warning line."""
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
    d = sub.add_parser("direct")
    d.add_argument("--profile", required=True)
    d.add_argument("--prompt", default="")
    d.add_argument("--markers")
    d.add_argument("--seed", type=int)
    d.add_argument("--provider", default="anthropic", help="anthropic | fake:<fixture.json>")
    d.add_argument("--record", help="append live replies to this fixture file")
    d.add_argument("--out")
    d.add_argument("--strict", action="store_true", help="exit 4 if a provider error forced the fallback")
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

    if a.cmd == "direct":
        return _direct(a)

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


def _direct(a):
    from engine.director.job import DirectorInputError
    from engine.director.pipeline import direct
    prof = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
    markers = json.loads(Path(a.markers).read_text(encoding="utf-8")) if a.markers else None
    try:
        res = direct(a.prompt, prof, provider=_provider(a.provider, a.record), seed=a.seed, markers=markers)
    except DirectorInputError as e:
        _fail(f"input rejected: {e}")
        return EXIT_BAD_INPUT
    if a.out:
        Path(a.out).write_text(json.dumps(res.script, indent=2), encoding="utf-8")
    print(json.dumps(res.to_dict(), indent=2))
    err = _provider_error(res)
    if err:
        print(f"engine: warning: the AI director was unavailable ({err}); used the built-in fallback script",
              file=sys.stderr)
        return EXIT_FALLBACK if a.strict else EXIT_OK
    return EXIT_OK


def _provider_error(res):
    """The first provider error's one-line message when it is why the fallback was used, else None."""
    if res.source != "fallback":
        return None
    msg = next((r["error"] for r in res.rounds if "error" in r), None)
    return (msg.strip().splitlines() or ["provider error"])[0][:200] if msg is not None else None


if __name__ == "__main__":
    sys.exit(main())
