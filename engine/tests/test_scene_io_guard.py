"""scene_io.import_subject is the ONE place a model reaches Blender's glTF importer (ingest's blender_extract and
the compiler's blender_main both call it). It re-runs the upload preflight on the exact path it imports, so a
job.json or argv that names a file never preflighted -- or one swapped after the host-side check -- is refused
before bpy.ops.import_scene.gltf opens it. bpy is stubbed: the guard must fire before any bpy call."""
import importlib
import sys
import types

import pytest

from engine.ingest.run import IngestRejected
from engine.tests.test_preflight import _doc, make_glb


@pytest.fixture
def scene_io(monkeypatch):
    calls = []
    bpy = types.ModuleType("bpy")
    bpy.ops = types.SimpleNamespace(
        wm=types.SimpleNamespace(read_factory_settings=lambda **k: calls.append(("reset", k))),
        import_scene=types.SimpleNamespace(gltf=lambda **k: (calls.append(("gltf", k)), (_ for _ in ()).throw(
            RuntimeError("stub: import reached")))[0]))
    bpy.data = types.SimpleNamespace(objects=[])
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.delitem(sys.modules, "engine.blender.scene_io", raising=False)
    mod = importlib.import_module("engine.blender.scene_io")
    mod._calls = calls
    yield mod
    sys.modules.pop("engine.blender.scene_io", None)


@pytest.mark.parametrize("uri", ["data:x/../../secret", "%2e%2e/secret.png", "file:///C:/x.png",
                                 r"\host\share\x.png", "DATA:image/png;base64,AAAA", "tex.png%00"])
@pytest.mark.parametrize("where", ["images", "buffers"])
def test_import_subject_refuses_hostile_uris_before_bpy(tmp_path, scene_io, uri, where):
    doc = _doc()
    if where == "images":
        doc["images"] = [{"uri": uri}]
    else:
        doc["buffers"].append({"byteLength": 4, "uri": uri})
    p = tmp_path / "m.glb"
    p.write_bytes(make_glb(doc))
    with pytest.raises(IngestRejected):
        scene_io.import_subject(p)
    assert scene_io._calls == []


def test_import_subject_refuses_non_glb_and_disguised_files(tmp_path, scene_io):
    g = tmp_path / "m.gltf"
    g.write_bytes(make_glb(_doc(), b"\0" * 36))
    j = tmp_path / "j.glb"
    j.write_text('{"asset":{"version":"2.0"},"images":[{"uri":"../secret.png"}]}', encoding="utf-8")
    for p in (g, j):
        with pytest.raises(IngestRejected):
            scene_io.import_subject(p)
    assert scene_io._calls == []


def test_import_subject_imports_a_clean_glb(tmp_path, scene_io):
    p = tmp_path / "m.glb"
    p.write_bytes(make_glb(_doc(images=[{"uri": "data:image/png;base64,AAAA"}]), b"\0" * 36))
    with pytest.raises(RuntimeError, match="import reached"):
        scene_io.import_subject(p)
    assert [c[0] for c in scene_io._calls] == ["reset", "gltf"]
    assert scene_io._calls[1][1]["filepath"] == str(p)
