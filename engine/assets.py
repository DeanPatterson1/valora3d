"""Pinned, licence-clean assets (ASSETS.md shipping rule; spec §4.7 same asset hashes on every worker).
Files live under assets-in/library/ (gitignored); the manifest is committed. resolve() returns a path only
when the file exists AND its sha256 matches; a missing file returns None and the block builds its
procedural fallback, so tests and farm workers never need the file. Blocks never download.
tools/assets/import_local.py fills the manifest from files already on disk (it downloads nothing).

Every manifest -- the committed one or one passed in -- goes through the ONE validator (validate_manifest):
shippable licence, a CC-BY credit that matches its CREDITS.md row, and a relative path that cannot leave the
library. A glTF is only as clean as the files it pulls in, so resolve_gltf() hashes and licence-checks its
whole dependency set (buffers + images) before a block may import it (review chunk 2 #1-#3)."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("assets") / "manifest.json"
CREDITS = Path(__file__).with_name("assets") / "CREDITS.md"
LIBRARY = ROOT / "assets-in" / "library"
ALLOWED_LICENCES = ("CC0-1.0", "owned", "CC-BY-4.0")
LIBRARY_ENV = "VALORA_ASSET_LIBRARY"   # tests point this at an empty dir to prove every fallback builds


class AssetError(RuntimeError):
    pass


def safe_relpath(rel, what="path"):
    """A relative POSIX path with no absolute root, drive, backslash or '..' part; else AssetError."""
    if not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel:
        raise AssetError(f"{what} {rel!r} is not a plain relative path")
    p = PurePosixPath(rel)
    if p.is_absolute() or any(part in ("..", "") for part in rel.split("/")):
        raise AssetError(f"{what} {rel!r} is absolute or escapes its root")
    return p


def contained(root, rel, what="path"):
    """root / rel, refused unless the symlink-resolved result stays under the resolved root."""
    safe_relpath(rel, what)
    base = Path(root).resolve()
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise AssetError(f"{what} {rel!r} resolves outside {base}")
    return p


def credit_rows(path=CREDITS):
    """{asset id: author} from the CREDITS.md table (header and separator rows skipped)."""
    rows = {}
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
        if len(cells) >= 2 and cells[0] not in ("Asset id", "") and not set(cells[0]) <= set("-: "):
            rows[cells[0].strip("`")] = cells[1]
    return rows


def validate_manifest(doc, credits=None):
    credits = credit_rows() if credits is None else credits
    for aid, a in doc["assets"].items():
        if a.get("licence") not in ALLOWED_LICENCES:
            raise AssetError(f"{aid}: licence {a.get('licence')!r} is not shippable (allowed {ALLOWED_LICENCES})")
        if a["licence"] == "CC-BY-4.0":
            if not a.get("credit"):
                raise AssetError(f"{aid}: CC-BY needs a credit (and a row in engine/assets/CREDITS.md)")
            if credits.get(aid) != a["credit"]:
                raise AssetError(f"{aid}: CC-BY credit {a['credit']!r} has no matching CREDITS.md row")
        safe_relpath(a.get("path"), f"{aid}: path")
        if not (isinstance(a.get("sha256"), str) and len(a["sha256"]) == 64):
            raise AssetError(f"{aid}: sha256 is not pinned")
    return doc


def load_manifest(path=MANIFEST, credits=None):
    return validate_manifest(json.loads(Path(path).read_text(encoding="utf-8")), credits)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def library_root():
    return Path(os.environ.get(LIBRARY_ENV) or LIBRARY)


def _manifest(manifest):
    return load_manifest() if manifest is None else validate_manifest(manifest)


def _check(aid, a, root):
    p = contained(root, a["path"], f"{aid}: path")
    if not p.exists():
        return None
    if _sha(p) != a["sha256"]:
        raise AssetError(f"{aid}: sha256 mismatch at {p}")
    return p


def resolve(aid, root=None, manifest=None):
    doc = _manifest(manifest)
    a = doc["assets"].get(aid)
    if a is None:
        raise AssetError(f"unknown asset {aid}")
    return _check(aid, a, root if root is not None else library_root())


def gltf_dependencies(gltf_path):
    """Relative URIs of every external file a .gltf pulls in (buffers + images); data: URIs are embedded."""
    doc = json.loads(Path(gltf_path).read_text(encoding="utf-8"))
    uris = [b.get("uri") for b in doc.get("buffers", [])] + [i.get("uri") for i in doc.get("images", [])]
    return sorted({u for u in uris if u and not u.startswith("data:")})


def resolve_gltf(aid, root=None, manifest=None):
    """The glTF's path only when it AND every dependency it names are pinned, licensed, contained and
    hash-clean. Any dependency missing on disk -> None (the block builds its fallback); a dependency the
    manifest does not pin, or one that escapes the library, -> AssetError (it would import unvetted bytes)."""
    doc = _manifest(manifest)
    root = root if root is not None else library_root()
    p = resolve(aid, root, doc)
    if p is None:
        return None
    by_path = {a["path"]: (k, a) for k, a in doc["assets"].items()}
    base = PurePosixPath(doc["assets"][aid]["path"]).parent
    ok = True
    for uri in gltf_dependencies(p):
        from urllib.parse import unquote
        safe_relpath(unquote(uri), f"{aid}: dependency")
        rel = str(base / unquote(uri))
        if rel not in by_path:
            raise AssetError(f"{aid}: dependency {uri!r} is not pinned in the manifest")
        dk, da = by_path[rel]
        ok = _check(dk, da, root) is not None and ok
    return p if ok else None
