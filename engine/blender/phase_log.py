"""Wall-clock phase timing for one Blender compile+render, written beside render_log.json as phase_timing.json.
No look change: it only reads the clock. `phase(name)` is a context manager; nested phases are recorded flat
with their depth. Render-loop timing (first frame vs steady state) is added by render.render_frames."""
import json
import time
from contextlib import contextmanager
from pathlib import Path

_T0 = time.perf_counter()
_ROWS = []
_DEPTH = [0]


@contextmanager
def phase(name):
    t = time.perf_counter()
    depth = _DEPTH[0]
    _DEPTH[0] += 1
    try:
        yield
    finally:
        _DEPTH[0] -= 1
        _ROWS.append({"phase": name, "depth": depth, "seconds": round(time.perf_counter() - t, 3),
                      "startS": round(t - _T0, 3)})


def mark(name):
    """A zero-length event (e.g. 'first_frame_written') at the current time since the module loaded."""
    _ROWS.append({"phase": name, "depth": _DEPTH[0], "seconds": 0.0, "startS": round(time.perf_counter() - _T0, 3)})


def write(out_dir, extra=None):
    path = Path(out_dir) / "phase_timing.json"
    doc = {"sinceModuleLoadS": round(time.perf_counter() - _T0, 3), "phases": _ROWS, **(extra or {})}
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path
