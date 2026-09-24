"""Point-and-describe markers (spec §2b): user-placed anchors on the model, each with its own
instruction, fed to the director as structured hints (phase 3). Phase 2 validates them and lets
a detail shot target one. Marker text is untrusted user input: it is bounded here and is only
ever data for the director, never code."""
import math
import re
import unicodedata

from engine.geometry import point_in_box
from engine.issues import Issue

MAX_MARKERS = 8
MAX_TEXT = 280
ANCHOR_MARGIN = 0.10
SPACES = ("placed", "gltf")
SNAP_FRAC = 0.05  # an anchor must be within this x the subject's longest side of a surface sample
_KEYS = {"id", "anchor", "part", "text", "timeS"}
_ANCHOR_KEYS = {"space", "point", "normal"}
_ID = re.compile(r"^[a-z0-9_-]{1,32}$")
# Rejected Unicode categories: controls (Cc: C0, DEL, C1), format characters (Cf: zero-width, bidi
# embeddings and isolates, BOM FEFF, 2060-2064, 061C, soft hyphen 00AD, tags), line and paragraph
# separators (Zl, Zp) and lone surrogates (Cs).
_BAD_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp", "Cs"})


def _bad_chars(text):
    return any(unicodedata.category(c) in _BAD_CATEGORIES for c in text)


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
    x, y, z = n[0], -n[2], n[1]
    length = math.sqrt(x * x + y * y + z * z)
    return [x / length, y / length, z / length]


def _part_shape_ok(p):
    if isinstance(p, bool):
        return False
    if isinstance(p, int):
        return p >= 0
    return isinstance(p, str) and bool(_ID.match(p))


def _near_box(p, lo, hi, tol):
    return all(lo[i] - tol <= p[i] <= hi[i] + tol for i in range(3))


def _part_error(part, point, profile, tol):
    """None, or (code, message) when `part` names nothing in the profile or the anchor is not on it."""
    if isinstance(part, int):
        box = next((q for q in profile.parts if q.get("index") == part), None)
        if box is None:
            return "bad_marker_part", f"part {part} is not in the profile ({len(profile.parts)} parts)"
        if not _near_box(point, box["boundsMin"], box["boundsMax"], tol):
            return "marker_part_mismatch", f"anchor is not on part {part}"
        return None
    zones = {m.get("class") for m in profile.materials}
    if part not in zones:
        return "bad_marker_part", f"material zone {part!r} is not in the profile ({sorted(z for z in zones if z)})"
    return None


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
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or _bad_chars(text):
        out.append(("bad_marker_text", f"text must be 1-{MAX_TEXT} printable characters"))
    a = m.get("anchor")
    if (not isinstance(a, dict) or set(a) - _ANCHOR_KEYS or a.get("space", "placed") not in SPACES
            or not _vec3(a.get("point"))):
        out.append(("bad_marker_anchor", "anchor needs only space placed|gltf and point [x, y, z]"))
    elif "normal" in a and (not _vec3(a["normal"]) or not any(a["normal"])):
        out.append(("bad_marker_anchor", "anchor normal must be a non-zero [x, y, z]"))
    if "part" in m and not _part_shape_ok(m["part"]):
        out.append(("bad_marker_part", "part must be a profile part index (int >= 0) or a material-zone id"))
    if "timeS" in m and _finite(duration) and not (_finite(m["timeS"]) and 0 <= m["timeS"] <= duration):
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
    """Convert glTF anchors to placed (repair) and require every anchor to sit on the subject's
    surface: within SNAP_FRAC x longest of a profile surface sample, snapped onto it (repair), else
    marker_off_surface. Profiles from before surface sampling fall back to the bounds check. An
    optional `part` must exist in the profile and, for a part index, contain the anchor."""
    tol = SNAP_FRAC * profile.longest
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
            continue
        if profile.surfaceSamples:
            near = min(profile.surfaceSamples, key=lambda q: math.dist(q, a["point"]))
            d = math.dist(near, a["point"])
            if d > tol:
                issues.append(Issue("marker_off_surface", f"markers[{i}].anchor.point",
                                    f"anchor is {d:.3g} m from the subject's surface (tolerance {tol:.3g} m)",
                                    "error"))
                continue
            if d > 0:
                a["point"] = [float(v) for v in near]
                issues.append(Issue("marker_snapped", f"markers[{i}].anchor.point",
                                    f"snapped {d:.3g} m onto the nearest surface sample", "repaired"))
        if "part" in m:
            err = _part_error(m["part"], a["point"], profile, tol)
            if err:
                issues.append(Issue(err[0], f"markers[{i}].part", err[1], "error"))
