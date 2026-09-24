"""Untrusted-upload intake: preflight() must reject before Blender ever sees the file."""
import json
import struct

import pytest

from engine.ingest import run
from engine.ingest.run import IngestRejected, preflight


def make_glb(doc, bin_bytes=b"", magic=b"glTF", version=2):
    """Minimal binary glTF from a JSON-able dict (+ optional BIN chunk)."""
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    if bin_bytes:
        bin_bytes += b"\0" * (-len(bin_bytes) % 4)
        body += struct.pack("<II", len(bin_bytes), 0x004E4942) + bin_bytes
    return magic + struct.pack("<II", version, 12 + len(body)) + body


def _doc(**extra):
    d = {"asset": {"version": "2.0"},
         "buffers": [{"byteLength": 36}],
         "bufferViews": [{"buffer": 0, "byteLength": 36}],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}]}
    d.update(extra)
    return d


def _write(tmp_path, data, name="m.glb"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_minimal_valid_glb_passes(tmp_path):
    preflight(_write(tmp_path, make_glb(_doc(), b"\0" * 36)))


def test_data_uri_image_is_allowed(tmp_path):
    preflight(_write(tmp_path, make_glb(_doc(images=[{"uri": "data:image/png;base64,AAAA"}]), b"\0" * 36)))


@pytest.mark.parametrize("name", ["m.gltf", "m.obj", "m.glb.exe", "m"])
def test_rejects_non_glb_extension(tmp_path, name):
    with pytest.raises(IngestRejected, match=r"\.glb"):
        preflight(_write(tmp_path, make_glb(_doc()), name))


def test_uppercase_extension_is_fine(tmp_path):
    preflight(_write(tmp_path, make_glb(_doc(), b"\0" * 36), "M.GLB"))


def test_rejects_bad_magic_and_version(tmp_path):
    with pytest.raises(IngestRejected, match="binary glTF"):
        preflight(_write(tmp_path, make_glb(_doc(), magic=b"PK\x03\x04")))
    with pytest.raises(IngestRejected, match="version 2"):
        preflight(_write(tmp_path, make_glb(_doc(), version=1)))
    with pytest.raises(IngestRejected):
        preflight(_write(tmp_path, b"glTF"))  # truncated header


def test_rejects_unparseable_json_chunk(tmp_path):
    good = make_glb(_doc())
    bad = good[:20] + b"{not json" + good[29:]
    with pytest.raises(IngestRejected, match="JSON"):
        preflight(_write(tmp_path, bad))


@pytest.mark.parametrize("uri", ["../secret.png", r"\\host\share\x.png", "file:///C:/x.png",
                                 "http://evil/x.png", "tex.png"])
@pytest.mark.parametrize("where", ["images", "buffers"])
def test_rejects_external_uris(tmp_path, uri, where):
    doc = _doc()
    if where == "images":
        doc["images"] = [{"uri": uri}]
    else:
        doc["buffers"].append({"byteLength": 4, "uri": uri})
    with pytest.raises(IngestRejected, match="external"):
        preflight(_write(tmp_path, make_glb(doc)))


def test_rejects_oversized_file(tmp_path, monkeypatch):
    p = _write(tmp_path, make_glb(_doc(), b"\0" * 36))
    monkeypatch.setattr(run, "MAX_FILE_BYTES", p.stat().st_size - 1)
    with pytest.raises(IngestRejected, match="MB"):
        preflight(p)


def test_default_limits():
    assert run.MAX_FILE_BYTES == 200 * 1024 * 1024
    assert run.MAX_VERTICES == 5_000_000
    assert run.MAX_IMAGE_BYTES == 64 * 1024 * 1024


def test_rejects_too_many_vertices_summed_over_primitives(tmp_path):
    doc = _doc(accessors=[{"count": 3_000_000}, {"count": 2_000_001}],
               meshes=[{"primitives": [{"attributes": {"POSITION": 0}}]},
                       {"primitives": [{"attributes": {"POSITION": 1, "NORMAL": 0}}]}])
    with pytest.raises(IngestRejected, match="vertices"):
        preflight(_write(tmp_path, make_glb(doc)))
    doc["accessors"][1]["count"] = 2_000_000
    preflight(_write(tmp_path, make_glb(doc)))  # exactly at the limit is fine


def test_rejects_oversized_embedded_image(tmp_path):
    doc = _doc(bufferViews=[{"buffer": 0, "byteLength": 36},
                            {"buffer": 0, "byteLength": 64 * 1024 * 1024 + 1}],
               images=[{"bufferView": 1, "mimeType": "image/png"}])
    with pytest.raises(IngestRejected, match="image"):
        preflight(_write(tmp_path, make_glb(doc)))


@pytest.mark.parametrize("doc", [
    [], {"images": {"uri": "x"}}, {"images": [5]}, {"accessors": [{"count": "lots"}],
                                                  "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}]},
    {"meshes": [{"primitives": [{"attributes": {"POSITION": 9}}]}]},
    {"images": [{"bufferView": 7}]},
])
def test_malformed_structure_is_rejected_not_crashed(tmp_path, doc):
    with pytest.raises(IngestRejected):
        preflight(_write(tmp_path, make_glb(doc)))


def test_ingest_runs_preflight_before_blender(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Blender must not be launched for a rejected file")
    monkeypatch.setattr(run.subprocess, "run", boom)
    with pytest.raises(IngestRejected):
        run.ingest(_write(tmp_path, make_glb(_doc(images=[{"uri": "../x.png"}]))), workdir=tmp_path / "w")


def test_ingest_rejected_is_a_value_error():
    assert issubclass(IngestRejected, ValueError)
