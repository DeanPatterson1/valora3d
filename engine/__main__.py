"""CLI: py -m engine check <script.json> --profile <profile.json>
        py -m engine ingest <model.glb> [--out profile.json]
        py -m engine render <script.json> --profile P --model M --out DIR [--tier T] [--frames key|all|1,2]

Exit codes: 0 ok, 3 check failed, 2 usage error (argparse), 1 any other error."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile


EXIT_OK, EXIT_ERROR, EXIT_CHECK_FAILED = 0, 1, 3


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


if __name__ == "__main__":
    sys.exit(main())
