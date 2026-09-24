"""CLI: py -m engine check <script.json> --profile <profile.json>
        py -m engine ingest <model.glb> [--out profile.json]"""
import argparse
import json
import sys
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile


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

    if a.cmd == "check":
        script = json.loads(Path(a.script).read_text(encoding="utf-8"))
        prof = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
        r = check(script, prof, Catalog.load())
        print(json.dumps({"ok": r.ok, "issues": [x.to_dict() for x in r.issues], "script": r.script}, indent=2))
        return 0 if r.ok else 2

    from engine.ingest.run import ingest  # only needs Blender for this command
    doc = json.dumps(ingest(a.model).to_dict(), indent=2)
    if a.out:
        Path(a.out).write_text(doc, encoding="utf-8")
    print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
