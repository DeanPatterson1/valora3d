"""Rulebook part 1 (spec §4.4): the menu, generated from block.json, so what the AI reads and what the
code builds cannot disagree (spec §4.3). Non-selectable blocks (harness controls, always-on realism)
are left out."""
import json

KIND_ORDER = ("world", "lighting", "camera", "motion", "effect", "grade", "edit", "field")   # field: wind (Task 58)
_FLAGS = ("framing", "hasGround", "studio", "atmosphere", "environment", "linearByDesign", "requiresProfile")
_EDIT_RULES = ("shotsPer10s", "shotLenS", "medianLenS", "hookMaxS", "lastShotMinS")


def _f(v):
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _param(name, spec):
    t = spec["type"]
    if t == "number":
        return f"    - {name}: number {_f(spec['min'])}..{_f(spec['max'])} (default {_f(spec['default'])})"
    if t == "enum":
        return f"    - {name}: one of {', '.join(_f(v) for v in spec['values'])} (default {_f(spec['default'])})"
    return f"    - {name}: true or false (default {str(spec['default']).lower()})"


def block_card(m):
    lo, hi = m["subjectSizeM"]
    lines = [f"### {m['kind']}/{m['id']}  (reaches up to {m['tierMax']})", m["description"],
             f"  subject size {_f(lo)}-{_f(hi)} m; aspects {', '.join(m['aspects'])}; cost x{_f(m['costWeight'])}"]
    flags = [f"{k}={json.dumps(m[k])}" for k in _FLAGS if k in m]
    if flags:
        lines.append("  " + "; ".join(flags))
    if m.get("capabilities"):
        lines.append(f"  capabilities: {', '.join(m['capabilities'])}")
    tags = "; ".join(f"{k}: {', '.join(v)}" for k, v in m["tags"].items() if v)
    if tags:
        lines.append(f"  tags: {tags}")
    if m["params"]:
        lines.append("  params:")
        lines += [_param(k, s) for k, s in m["params"].items()]
    if m["kind"] == "edit":
        for k in _EDIT_RULES:
            if k in m:
                lines.append(f"  {k}: {json.dumps(m[k])}")
        for fam, slots in m.get("templates", {}).items():
            desc = " -> ".join(f"{s['purpose']} {s['lenS'][0]:g}-{s['lenS'][1]:g}s [{'/'.join(s['cameras'])}]"
                               for s in slots)
            lines.append(f"  template {fam}: {desc}")
    return "\n".join(lines)


def render_menu(catalog):
    parts = ["# 1. Menu: every block you may use",
             "Generated from the catalog. Ids, parameter names and ranges are exact; use nothing else."]
    for kind in KIND_ORDER:
        ids = catalog.selectable_ids(kind)
        if ids:
            parts.append(f"\n## {kind}")
            parts += [block_card(catalog.get(kind, b)) for b in ids]
    return "\n".join(parts) + "\n"
