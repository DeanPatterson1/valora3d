"""Point-and-describe markers (spec §2b): user-placed anchors on the model, each with its own
instruction, fed to the director as structured hints (phase 3). Phase 2 validates them and lets
a detail shot target one. Marker text is untrusted user input: it is bounded here and is only
ever data for the director, never code."""
import math
import re

from engine.geometry import point_in_box
from engine.issues import Issue

MAX_MARKERS = 8
MAX_TEXT = 280
ANCHOR_MARGIN = 0.10
SPACES = ("placed", "gltf")
_KEYS = {"id", "anchor", "text", "timeS"}
_ID = re.compile(r"^[a-z0-9_-]{1,32}$")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(_finite(x) for x in v)


def gltf_to_placed(p, profile):
    """glTF world point (Y-up, source units) -> placed metres. Blender's glTF importer maps
    (x, y, z) -> (x, -z, y); then the SubjectProfile placement formula applies."""
    bx, by, bz = p[0], -p[2], p[1]
    c, f = profile.sourceCenter, profile.scaleFactor
    return [(bx - c[0]) * f, (by - c[1]) * f, (bz - profile.sourceMinZ) * f]


def gltf_dir_to_placed(n):
    return [n[0], -n[2], n[1]]


def _marker_errors(m, seen, duration):
    if not isinstance(m, dict) or set(m) - _KEYS:
        return [("bad_marker", f"marker must be an object with keys {sorted(_KEYS)}")]
    out = []
    mid = m.get("id")
    if not isinstance(mid, str) or not _ID.match(mid):
        out.append(("bad_marker_id", "id must match [a-z0-9_-]{1,32}"))
    elif mid in seen:
        out.append(("duplicate_marker_id", f"duplicate id {mid!r}"))
    else:
        seen.add(mid)
    text = m.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or _CTRL.search(text):
        out.append(("bad_marker_text", f"text must be 1-{MAX_TEXT} printable characters"))
    a = m.get("anchor")
    if not isinstance(a, dict) or a.get("space", "placed") not in SPACES or not _vec3(a.get("point")):
        out.append(("bad_marker_anchor", "anchor needs space placed|gltf and point [x, y, z]"))
    elif "normal" in a and (not _vec3(a["normal"]) or not any(a["normal"])):
        out.append(("bad_marker_anchor", "anchor normal must be a non-zero [x, y, z]"))
    if "timeS" in m and not (_finite(m["timeS"]) and _finite(duration) and 0 <= m["timeS"] <= duration):
        out.append(("bad_marker_time", "timeS must be inside the clip"))
    return out


def validate_shapes(markers, duration, issues):
    """Profile-free checks (script.py). Appends errors; never raises."""
    if not isinstance(markers, list):
        issues.append(Issue("bad_markers", "markers", "'markers' must be a list", "error"))
        return
    if len(markers) > MAX_MARKERS:
        issues.append(Issue("too_many_markers", "markers", f"at most {MAX_MARKERS} markers", "error"))
    seen = set()
    for i, m in enumerate(markers):
        for code, msg in _marker_errors(m, seen, duration):
            issues.append(Issue(code, f"markers[{i}]", msg, "error"))


def check_anchors(markers, profile, issues):
    """Convert glTF anchors to placed (repair) and require every anchor to sit on the subject."""
    for i, m in enumerate(markers):
        a = m["anchor"]
        if a.get("space", "placed") == "gltf":
            a["point"] = gltf_to_placed(a["point"], profile)
            if "normal" in a:
                a["normal"] = gltf_dir_to_placed(a["normal"])
            issues.append(Issue("marker_converted", f"markers[{i}].anchor", "glTF -> placed metres", "repaired"))
        a["space"] = "placed"
        if not point_in_box(a["point"], profile.boundsMin, profile.boundsMax, ANCHOR_MARGIN):
            issues.append(Issue("marker_off_subject", f"markers[{i}].anchor.point",
                                "anchor is not on the subject", "error"))
