"""Launch Blender headless to extract raw facts, then build the SubjectProfile."""
import json
import struct
import subprocess
import tempfile
from pathlib import Path

from engine.blender_cli import BLENDER, blender_argv  # noqa: F401  (BLENDER re-exported)
from engine.ingest.measure import build_profile

EXTRACT = Path(__file__).with_name("blender_extract.py")
TIMEOUT_S = 300

MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_VERTICES = 5_000_000
MAX_IMAGE_BYTES = 64 * 1024 * 1024
_GLB_MAGIC = b"glTF"
_CHUNK_JSON = 0x4E4F534A


class IngestRejected(ValueError):
    """An uploaded file refused before Blender opens it. The message is safe to show the user."""


def _is_index(v, seq):
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(seq)


def _list(doc, key):
    v = doc.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
        raise IngestRejected(f"The model file is malformed ('{key}' is not a list of objects).")
    return v


def preflight(path):
    """Cheap stdlib-only checks on an UNTRUSTED upload, before any Blender launch.
    Only self-contained binary glTF 2 passes: external URIs could read local files
    (../) or leak credentials over SMB (UNC host/share paths); size caps bound Blender's work."""
    path = Path(path)
    if path.suffix.lower() != ".glb":
        raise IngestRejected("Only .glb (binary glTF) models are accepted.")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise IngestRejected(f"The model is larger than the {MAX_FILE_BYTES // (1024 * 1024)} MB limit.")
    with open(path, "rb") as f:
        head = f.read(20)
        if len(head) < 20 or head[:4] != _GLB_MAGIC:
            raise IngestRejected("The file is not a binary glTF (.glb) model.")
        version, _total, json_len, json_type = struct.unpack("<IIII", head[4:20])
        if version != 2:
            raise IngestRejected("Only glTF version 2 models are accepted.")
        if json_type != _CHUNK_JSON or json_len > size - 20:
            raise IngestRejected("The model file is malformed (bad JSON chunk).")
        chunk = f.read(json_len)
    try:
        doc = json.loads(chunk.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise IngestRejected("The model file is malformed (its JSON chunk does not parse).") from None
    if not isinstance(doc, dict):
        raise IngestRejected("The model file is malformed (its JSON chunk is not an object).")

    images, buffers = _list(doc, "images"), _list(doc, "buffers")
    for kind, items in (("image", images), ("buffer", buffers)):
        for item in items:
            uri = item.get("uri")
            if uri is not None and not (isinstance(uri, str) and uri.startswith("data:")):
                raise IngestRejected(f"The model references an external {kind} file; "
                                     "only self-contained .glb files are accepted.")

    accessors, views = _list(doc, "accessors"), _list(doc, "bufferViews")
    verts = 0
    for mesh in _list(doc, "meshes"):
        prims = mesh.get("primitives", [])
        if not isinstance(prims, list):
            raise IngestRejected("The model file is malformed (bad mesh primitives).")
        for prim in prims:
            attrs = prim.get("attributes", {}) if isinstance(prim, dict) else None
            if not isinstance(attrs, dict):
                raise IngestRejected("The model file is malformed (bad mesh primitive).")
            if "POSITION" not in attrs:
                continue
            idx = attrs["POSITION"]
            count = accessors[idx].get("count") if _is_index(idx, accessors) else None
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise IngestRejected("The model file is malformed (bad vertex accessor).")
            verts += count
    if verts > MAX_VERTICES:
        raise IngestRejected(f"The model has more than {MAX_VERTICES:,} vertices.")

    for img in images:
        if "bufferView" not in img:
            continue
        bv = img["bufferView"]
        length = views[bv].get("byteLength") if _is_index(bv, views) else None
        if not isinstance(length, int) or isinstance(length, bool) or length < 0:
            raise IngestRejected("The model file is malformed (bad image data).")
        if length > MAX_IMAGE_BYTES:
            raise IngestRejected(f"The model contains an image larger than "
                                 f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB.")


def _tail(text, n=2000):
    return (text or "").strip()[-n:] or "(empty)"


def ingest(model_path, workdir=None):
    """Preflight, then extract raw facts in headless Blender and build the SubjectProfile.
    Without a workdir, a temporary one is used and removed afterwards."""
    preflight(model_path)
    if workdir is None:
        with tempfile.TemporaryDirectory(prefix="valora-ingest-") as tmp:
            return _extract(model_path, Path(tmp))
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    return _extract(model_path, workdir)


def _extract(model_path, workdir):
    raw_path = workdir / "raw.json"
    cmd = blender_argv(EXTRACT, [model_path, raw_path])
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TIMEOUT_S)
    if proc.returncode != 0 or not raw_path.exists():
        lines = [ln for ln in (proc.stderr or proc.stdout or "").splitlines() if ln.strip()]
        last = lines[-1].strip() if lines else "no output"
        raise RuntimeError(f"Blender extract failed (exit {proc.returncode}): {last}\n"
                           f"--- stdout tail ---\n{_tail(proc.stdout)}\n"
                           f"--- stderr tail ---\n{_tail(proc.stderr)}")
    return build_profile(json.loads(raw_path.read_text(encoding="utf-8")))
