"""render_frames bookkeeping without Blender: a fake bpy records what was rendered. The render log
is the harness's frame list, so the animation path must log every frame it wrote."""
import importlib
import json
import sys
import types


class _Render:
    def __init__(self):
        self.filepath = ""
        self.resolution_x, self.resolution_y = 144, 256


class _Scene:
    def __init__(self, start, end):
        self.frame_start, self.frame_end = start, end
        self.render = _Render()
        self.current = None

    def frame_set(self, f):
        self.current = f

    def get(self, key, default=None):     # ID-property lookup (render_frames reads valora_grain)
        return default


def _fake_bpy(scene, written):
    def render(**kw):
        written.append((scene.current, scene.render.filepath, kw))

    bpy = types.ModuleType("bpy")
    bpy.app = types.SimpleNamespace(version_string="fake")
    bpy.ops = types.SimpleNamespace(render=types.SimpleNamespace(render=render))
    return bpy


def _render_module(monkeypatch, scene, written):
    monkeypatch.setitem(sys.modules, "bpy", _fake_bpy(scene, written))
    sys.modules.pop("engine.blender.render", None)
    return importlib.import_module("engine.blender.render")


def test_all_frames_path_logs_every_frame(tmp_path, monkeypatch):
    scene, written = _Scene(1, 4), []
    render = _render_module(monkeypatch, scene, written)
    try:
        log = render.render_frames(scene, "all", tmp_path, "keyframes", "CPU")
    finally:
        sys.modules.pop("engine.blender.render", None)
    assert [e["frame"] for e in log["frames"]] == [1, 2, 3, 4]
    assert [w[0] for w in written] == [1, 2, 3, 4]
    assert written[0][1].endswith("0001.png")
    assert json.loads((tmp_path / "render_log.json").read_text())["frames"] == log["frames"]


def test_a_close_detail_frame_renders_and_logs_its_own_sample_cap(tmp_path, monkeypatch):
    scene, written = _Scene(1, 3), []
    scene.cycles = types.SimpleNamespace(samples=0)
    seen = []
    render = _render_module(monkeypatch, scene, written)
    orig = sys.modules["bpy"].ops.render.render
    sys.modules["bpy"].ops.render.render = lambda **kw: (seen.append(scene.cycles.samples), orig(**kw))
    try:
        log = render.render_frames(scene, [1, 3], tmp_path, "final", "CPU", samples_by_frame={1: 1024, 3: 2048})
    finally:
        sys.modules.pop("engine.blender.render", None)
    assert seen == [1024, 2048]
    assert "samples" not in log["frames"][0] and log["frames"][1]["samples"] == 2048
