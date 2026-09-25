"""Pinned, licence-clean assets (ASSETS.md shipping rule; spec §4.7 same asset hashes on every worker).
Files live under assets-in/library/ (gitignored); the manifest is committed. resolve() returns a path only
when the file exists AND its sha256 matches; a missing file returns None and the block builds its
procedural fallback, so tests and farm workers never need the file. Blocks never download.
tools/assets/import_local.py fills the manifest from files already on disk (it downloads nothing).

Every manifest -- the committed one or one passed in -- goes through the ONE validator (validate_manifest):
shippable licence, a CC-BY credit that matches its CREDITS.md row, and a relative path that cannot leave the
library. A glTF is only as clean as the files it pulls in, so resolve_gltf() hashes and licence-checks its
whole dependency set (buffers + images) before a block may import it (review chunk 2 #1-#3)."""
import base64
import binascii
import hashlib
import json
import os
import re
import struct
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

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


# Blender 5's importer (io_scene_gltf2/io/imp/gltf2_io_gltf.py load_uri) decodes a URI in memory only when it
# starts with 'data:' and contains ';base64,'; every other URI -- 'data:' ones included -- goes through
# io/com/path.py uri_to_path (backslash -> '/', urllib unquote, normpath) and is opened beside the glTF. So only a
# strictly well-formed base64 data URI is treated as embedded here; everything else is a file dependency.
_DATA_URI = re.compile(r"data:(?:[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+)?"
                       r"(?:;[A-Za-z0-9!#$&^_.+-]+=[A-Za-z0-9!#$&^_.+%-]*)*;base64,([A-Za-z0-9+/]+={0,2})")


def embedded_uri(uri):
    """True only for a URI Blender decodes in memory and we accept as such: a strictly well-formed, non-empty
    base64 data: URI. Everything else (malformed data:, DATA:, percent-encoded paths...) is opened as a file."""
    if not isinstance(uri, str):
        return False
    m = _DATA_URI.fullmatch(uri)
    if not m:
        return False
    try:
        return bool(base64.b64decode(m.group(1), validate=True))
    except (binascii.Error, ValueError):
        return False


def _gltf_json(gltf_path):
    """The glTF JSON of a .gltf, or of a binary container (Blender sniffs the b'glTF' magic, not the extension)."""
    raw = Path(gltf_path).read_bytes()
    try:
        if raw[:4] == b"glTF":
            if len(raw) < 20:
                raise AssetError(f"{gltf_path}: truncated binary glTF")
            n, kind = struct.unpack_from("<I4s", raw, 12)
            if kind != b"JSON" or 20 + n > len(raw):
                raise AssetError(f"{gltf_path}: binary glTF without a JSON chunk")
            raw = raw[20:20 + n]
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise AssetError(f"{gltf_path}: not a readable glTF ({e})") from e
    if not isinstance(doc, dict):
        raise AssetError(f"{gltf_path}: glTF root is not an object")
    return doc


def gltf_dependencies(gltf_path):
    """Every external file a glTF pulls in (buffers + images), as the DECODED relative path Blender opens beside it.
    Strict base64 data: URIs are embedded and skipped; any URI that is not a plain relative path (absolute, drive,
    UNC, scheme, backslash, '..', percent-encoded variants of those, malformed data:) -> AssetError."""
    doc = _gltf_json(gltf_path)
    out = set()
    for kind in ("buffers", "images"):
        items = doc.get(kind, [])
        if not isinstance(items, list):
            raise AssetError(f"{gltf_path}: {kind} is not a list")
        for item in items:
            uri = item.get("uri") if isinstance(item, dict) else None
            if uri is None or (kind == "buffers" and uri == ""):   # GLB-stored buffer / bufferView image
                continue
            if not isinstance(uri, str):
                raise AssetError(f"{gltf_path}: {kind} uri {uri!r} is not a string")
            if embedded_uri(uri):
                continue
            rel = unquote(uri)                                # Blender unquotes before it opens
            if any(ord(c) < 32 or ord(c) == 127 for c in rel):
                raise AssetError(f"{gltf_path}: dependency {uri!r} has control characters")
            safe_relpath(rel, f"{gltf_path}: dependency {uri!r}")
            out.add(rel)
    return sorted(out)


def resolve_gltf(aid, root=None, manifest=None):
    """The glTF's CANONICAL path only when it AND every dependency it names are pinned, licensed, contained and
    hash-clean. Dependencies resolve against the canonical glTF's directory -- the exact files Blender opens
    when handed the returned path -- and each is canonicalised, held inside the library and matched to its pin
    by canonical path. Any dependency missing on disk -> None (the block builds its fallback); a dependency the
    manifest does not pin, or one that escapes the library, -> AssetError (it would import unvetted bytes)."""
    doc = _manifest(manifest)
    root = Path(root if root is not None else library_root())
    p = resolve(aid, root, doc)
    if p is None:
        return None
    base = root.resolve()
    pins = {}
    for k, a in doc["assets"].items():
        try:
            pins.setdefault(contained(root, a["path"], f"{k}: path"), (k, a))
        except AssetError:
            continue                                          # never matchable; resolve() refuses it on its own
    ok = True
    for rel in gltf_dependencies(p):
        dep = (p.parent / rel).resolve()
        if dep != base and base not in dep.parents:
            raise AssetError(f"{aid}: dependency {rel!r} resolves outside {base}")
        if dep not in pins:
            raise AssetError(f"{aid}: dependency {rel!r} ({dep}) is not pinned in the manifest")
        dk, da = pins[dep]
        if not dep.exists():
            ok = False
            continue
        if _sha(dep) != da["sha256"]:
            raise AssetError(f"{dk}: sha256 mismatch at {dep}")
    return p if ok else None
