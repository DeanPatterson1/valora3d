"""Pinned, licence-clean assets (ASSETS.md shipping rule; spec §4.7 same asset hashes on every worker).
Files live under assets-in/library/ (gitignored); the manifest is committed. resolve() returns a path only
when the file exists AND its sha256 matches; a missing file returns None and the block builds its
procedural fallback, so tests and farm workers never need the file. Blocks never download.
tools/assets/import_local.py fills the manifest from files already on disk (it downloads nothing)."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("assets") / "manifest.json"
LIBRARY = ROOT / "assets-in" / "library"
ALLOWED_LICENCES = ("CC0-1.0", "owned", "CC-BY-4.0")
LIBRARY_ENV = "VALORA_ASSET_LIBRARY"   # tests point this at an empty dir to prove every fallback builds


class AssetError(RuntimeError):
    pass


def load_manifest(path=MANIFEST):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    for aid, a in doc["assets"].items():
        if a.get("licence") not in ALLOWED_LICENCES:
            raise AssetError(f"{aid}: licence {a.get('licence')!r} is not shippable (allowed {ALLOWED_LICENCES})")
        if a["licence"] == "CC-BY-4.0" and not a.get("credit"):
            raise AssetError(f"{aid}: CC-BY needs a credit (and a row in engine/assets/CREDITS.md)")
    return doc


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def library_root():
    return Path(os.environ.get(LIBRARY_ENV) or LIBRARY)


def resolve(aid, root=None, manifest=None):
    a = (manifest or load_manifest())["assets"].get(aid)
    if a is None:
        raise AssetError(f"unknown asset {aid}")
    p = Path(root if root is not None else library_root()) / a["path"]
    if not p.exists():
        return None
    if _sha(p) != a["sha256"]:
        raise AssetError(f"{aid}: sha256 mismatch at {p}")
    return p
