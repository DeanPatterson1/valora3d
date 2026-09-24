"""CLI: py -m engine check <script.json> --profile <profile.json>
        py -m engine ingest <model.glb> [--out profile.json]

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

    from engine.ingest.run import ingest  # only needs Blender for this command
    doc = json.dumps(ingest(a.model).to_dict(), indent=2)
    if a.out:
        Path(a.out).write_text(doc, encoding="utf-8")
    print(doc)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
